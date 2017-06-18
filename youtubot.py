from banned_subreddits import BannedSubreddits
from comment import get_age, get_score
from inbox import get_new_pms
from config import DEFAULT_CONFIG
import logging
import time
import requests
import re
from pprint import pprint
import prawcore, praw
import collections
from greplin import scales
from greplin.scales import meter
import googleapiclient


version = '1.1.4b'


RATELIM_RE = re.compile(r'(\d+) (minutes|seconds)')


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class YoutuBot(object):
    def __init__(self, reddit, responder, **config_overrides):
        self.bot_config = DEFAULT_CONFIG
        self.bot_config.update(config_overrides)
        self.r = reddit
        self.responder = responder
        self.banned_subreddits = BannedSubreddits(filename=self.bot_config['banned_subreddits_filename'])
        self.read_only = False
        self.read_only_expiry_time = time.time()
        self.next_review_of_comments = self.read_only_expiry_time
        self.task_list = collections.deque(maxlen=self.bot_config['max_queue_size'])
        # List of comment IDs we have already replied to (so we don't reply twice)
        self.already_done = []

        self.youtubot = self.r.user.me()
        self.do_not_reply = [self.youtubot] + self.bot_config['do_not_reply_to_users']

        self.metrics = scales.collection('/web',
            meter.MeterStat('comments'),
            scales.Stat('karma.comment', lambda: self.r.user.me().comment_karma)
        )

    def can_comment(self):
        return not self.read_only and self.can_make_changes()

    def can_make_changes(self):
        return not self.bot_config['ghost_mode']

    def max_comments_per_iteration(self):
        return self.bot_config['max_comments_per_iteration']

    def should_respond(self, comment):
        # If we haven't done the comment, we're not the author and the comment isn't in a subreddit we're banned from
        return comment.id not in self.already_done and comment.author not in self.do_not_reply and not self.banned_subreddits.contains(str(comment.subreddit))

    def queue_response(self, comment, response):
        self.task_list.append((comment, response))

    def comment_stream(self):
        subreddit = self.bot_config['subreddit']
        logger.debug('Opening stream from subreddit={}'.format(subreddit))
        return self.r.subreddit(subreddit).stream.comments()

    def run(self):
        logger.info("Starting YoutuBot")
        if not self.can_make_changes():
            logger.info("YoutuBot will not make any changes to the Reddit state this run.")
        logger.info("YoutuBot will not reply to these users: {}".format(self.do_not_reply))
        # todo: maybe handle this with signal instead of try/except. See:
        # https://stackoverflow.com/questions/18499497/how-to-process-sigterm-signal-gracefully
        try:
            while True:
                try:
                    self._main_loop()
                except Exception as e:
                    logger.exception("Encountered unexpected error during main loop!")
        except KeyboardInterrupt:
            self.banned_subreddits.save()
            logger.info('Received KeyboardInterrupt. Exiting.')

    def _main_loop(self):
        # First, check for new comments to reply to
        self._generate_responses()
        # Second, check if there are any tasks in the task_list
        self._submit_responses()
        # Third, check for any of our comments that are more than 1 hour old and have a score < 1. Delete them.
        self._delete_downvoted()
        # Fourth, check the inbox for any unread PMs
        self._handle_messages()
        # Fifth, check if the read_only time has expired
        self._switch_mode()

    def _generate_responses(self):
        logger.info('STEP 1 - Retrieving Comments and Generating Responses')
        try:
            comment_iter = self.comment_stream()
            for i in range(self.max_comments_per_iteration()):
                comment = next(comment_iter)
                if self.should_respond(comment):
                    self.already_done.append(comment.id)
                    response = self.responder.get_comment_response(comment.body, comment.author)
                    if response:
                        logger.info('Queuing response for comment: {}'.format(comment.id))
                        self.queue_response(comment, response)
        except (requests.exceptions.HTTPError, googleapiclient.errors.HttpError, ConnectionResetError) as e:
            logger.exception("Recoverable exception while attempting to generate responses. Skipping to next step.")

    def _submit_responses(self):
        logger.info('STEP 2 - Submitting Responses (if in Write Mode. Can make changes: %s, Can comment: %s, Task List Len: %d)' % (self.can_make_changes(), self.can_comment(), len(self.task_list)))
        while len(self.task_list) > 0 and (not self.can_make_changes() or self.can_comment()):
            # Pop one out, make sure it's less than 1.5 hours old, and submit the response
            task = self.task_list.pop()
            comment = task[0]
            response = task[1]
            logger.info('\tPopping comment out of task list (length %d)' % len(self.task_list))
            if get_age(comment) < 5400.0:
                self.submit_response(comment, response)

    def _delete_downvoted(self):
        logger.info('STEP 3 - Deleting Downvoted Comments')
        # Only do this every 10 minutes
        if time.time() > self.next_review_of_comments:
            for comment in self.youtubot.comments.new():
                if get_age(comment) > 3600.0 and get_score(comment) < 1:
                    logger.info('\tDeleting comment %s in /r/%s' % (comment.id, comment.subreddit))
                    comment.delete()
            self.next_review_of_comments = time.time() + 600

    def _handle_messages(self):
        logger.info('STEP 4 - Checking PMs and Responding Accordingly')
        messages = get_new_pms(self.r)
        for m in messages:
            if m.subject == 'delete comment':
                body = m.body.split('\n\n', 1)
                comment_id = body[0]
                comment = None
                try:
                    # This will return None if no comment exists with comment_id
                    comment = self.r.comment(comment_id)
                    if comment.is_root:
                        continue
                    try:
                        parent = comment.parent()
                        # If there is such a comment belonging to us, and the sender of the message is the parent commentor
                        if comment and comment.author == self.youtubot and parent.author == m.author:
                            logger.info('\tDeleting comment %s' % comment_id)
                            if len(body) > 1:
                                logger.info('\t%s' % body[1])
                            comment.delete()
                    except AttributeError as e:
                        logger.warning('\tCould not delete requested comment %s' % comment_id)
                        logger.warning('\t%s' % e)
                except praw.exceptions.PRAWException as e:
                    logger.warning('\tCould not delete requested comment %s' % comment_id)
                    logger.warning('\t%s' % e)
            m.mark_read()

    def _switch_mode(self):
        if self.read_only:
            logger.info('STEP 5 - Check if it\'s Time to Switch to Write Mode')
            seconds_remaining = int(self.read_only_expiry_time - time.time())
            if seconds_remaining <= 0:
                logger.info('\tSwitching to write mode...')
                self.read_only = False
            else:
                logger.info('\tWill switch to write mode in {} seconds'.format(seconds_remaining))

    # Takes a praw comment object and a response string and attempts to reply to the comment.
    # If the reply fails, responds accordingly by either switching to read_only mode or adding
    # the comment's subreddit to the list of banned subreddits
    def submit_response(self, comment, response):
        if self.can_make_changes():
            try:
                sub = comment.submission.subreddit
                reply = comment.reply(response)
                logger.info('\tCommenting on %s in /r/%s' % (comment.permalink, sub))
                # Edit the reply to replace the comment_id placeholder
                new_response = reply.body.replace('$comment_id', reply.id)
                # Also replace the format quote placeholder
                new_response = new_response.replace('$quote', '>')
                reply.edit(new_response)
                self.metrics.comments.mark()
            except praw.exceptions.APIException as e:
                # We are commenting too much. Switch to read_only mode
                m = RATELIM_RE.search(str(e))
                try:
                    sleep_duration = int(m.group(1))
                    sleep_unit = m.group(2)
                except (AttributeError, TypeError) as e:
                    logger.warning('\tRatelimit exceeded but time until next allowed post could not be retrieved')
                    logger.warning('\t%s' % e)
                    sleep_duration = 1
                    sleep_unit = 'minutes'
                if sleep_unit == "minutes":
                    sleep_duration = sleep_duration * 60
                logger.info('\tComment rate limit exceeded. Switching to read-only mode for %d seconds.' % sleep_duration)
                self.read_only = True
                self.read_only_expiry_time = time.time() + sleep_duration
                self.queue_response(comment, response)
            # except praw.errors.APIException as e:
            #     # The comment was deleted before we could reply so just move on
            #     logger.warning('\tTried to reply but encountered APIException.')
            #     logger.warning('\t%s' % e)
            except prawcore.exceptions.Forbidden as e:
                # We are banned from this subreddit
                logger.warning('\tTried to reply but encountered Forbidden.')
                logger.warning('\t%s' % e)
                subreddit_name = str(sub)
                if subreddit_name:
                    logger.warning('\tAdding /r/%s to the list of banned subreddits' % subreddit_name)
                    self.banned_subreddits.add(subreddit_name)
            except prawcore.exceptions.ServerError as e:
                # Temporary 500 error
                logger.exception("Recoverable exception while trying to submit a response. Response will be re-queued.")
                self.queue_response(comment, response)
        else:
            logger.info('Ghost mode response:\n{}'.format(response))
