from banned_subreddits import BannedSubreddits
from response import get_comment_response
from comment import get_age, get_score
from inbox import get_new_pms
from config import DEFAULT_CONFIG
import logging
import time
import requests
import re


RATELIM_RE = re.compile(r'(\d+) (minutes|seconds)')


class YoutuBot(object):
    def __init__(self, reddit, **config_overrides):
        self.bot_config = DEFAULT_CONFIG
        self.bot_config.update(config_overrides)
        self.r = reddit
        self.banned_subreddits = BannedSubreddits(filename=self.bot_config['banned_subreddits_filename'])
        self.read_only = False
        self.read_only_expiry_time = time.time()
        self.next_review_of_comments = self.read_only_expiry_time
        self.task_list = []
        # List of comment IDs we have already replied to (so we don't reply twice)
        self.already_done = []

        self.youtubot = self.r.user.me()

    def can_comment(self):
        return not self.read_only and not self.can_make_changes()

    def can_make_changes(self):
        return not self.bot_config['ghost_mode']

    def max_comments_per_iteration(self):
        return self.bot_config['max_comments_per_iteration']

    def should_respond(self, comment):
        # If we haven't done the comment, we're not the author and the comment isn't in a subreddit we're banned from
        return comment.id not in self.already_done and not comment.author == self.youtubot and not self.banned_subreddits.contains(str(comment.subreddit))

    def queue_response(self, comment, response):
        self.task_list.append((comment, response))

    def run(self):
        logging.info("Starting YoutuBot")
        if not self.can_make_changes():
            logging.info("YoutuBot will not make any changes to the Reddit state this run.")
        # todo: maybe handle this with signal instead of try/except. See:
        # https://stackoverflow.com/questions/18499497/how-to-process-sigterm-signal-gracefully
        try:
            while True:
                self._main_loop()
        except KeyboardInterrupt:
            self.banned_subreddits.save()
            logging.info('Received KeyboardInterrupt. Exiting.')

    def _main_loop(self):
        # First, check for new comments to reply to
        logging.info('STEP 1 - Retrieving Comments and Submitting/Storing Responses')
        try:
            comment_iter = self.r.subreddit('all').stream.comments()
            for i in range(self.max_comments_per_iteration()):
                comment = next(comment_iter)
                try:
                    if self.should_respond(comment):
                        self.already_done.append(comment.id)
                        # Start a timer
                        # timer_start = time.time()
                        response = get_comment_response(comment)
                        if response:
                            logging.info('Queuing response for comment: {}'.format(comment.id))
                            self.queue_response(comment, response)
                            # logging.info(response)
                            # if not self.can_comment():
                                # # Add the comment and response to a list to process later
                                # task_list.append((comment, response))
                                # logging.info('\tAppending comment to task list (length %d)' % len(task_list))
                            # else:
                            #     # Submit the response as a comment to Reddit
                            #     if self.can_make_changes():
                            #         submit_response(comment, response)
                            #     timer_total = time.time() - timer_start
                except requests.exceptions.HTTPError as e:
                    logging.warning('\tHTTP Error')
                    logging.warning('\t%s' % e)
        except requests.exceptions.HTTPError as e:
            logging.warning('\tHTTP Error when getting all comments')
            logging.warning('\t%s' % e)

        # Second, check if there are any tasks in the task_list
        # Caution: this hasn't been tested as youtubot now has enough karma to comment constantly
        logging.info('STEP 2 - Checking on Task List (if in Write Mode. Read-only: %s, Task List Len: %d)' % (self.read_only, len(self.task_list)))
        while len(self.task_list) > 0 and (not self.can_make_changes() or self.can_comment()):
            # Pop one out, make sure it's less than 1.5 hours old, and submit the response
            task = self.task_list.pop(0)
            comment = task[0]
            response = task[1]
            logging.info('\tPopping comment out of task list (length %d)' % len(self.task_list))
            if get_age(comment) < 5400.0:
                self.submit_response(comment, response)

        # Third, check for any of our comments that are more than 1 hour old and have a score < 1
        # Delete them.
        logging.info('STEP 3 - Deleting Downvoted Comments')
        # Only do this every 10 minutes
        if time.time() > self.next_review_of_comments:
            for comment in self.youtubot.comments.new():
                if get_age(comment) > 3600.0 and get_score(comment) < 1:
                    logging.info('\tDeleting comment %s in /r/%s' % (comment.id, comment.subreddit))
                    comment.delete()
            self.next_review_of_comments = time.time() + 600

        # Fourth, check the inbox for any unread PMs
        logging.info('STEP 4 - Check PMs and Respond Accordingly')
        messages = get_new_pms(self.r)
        for m in messages:
            if m.subject == 'delete comment':
                body = m.body.split('\n\n', 1)
                comment_id = body[0]
                # This will return None if no comment exists with comment_id
                comment = self.r.comment(comment_id)
                if comment.is_root:
                    continue
                try:
                    parent = comment.parent()
                    # If there is such a comment belonging to us, and the sender of the message is the parent commentor
                    if comment and comment.author == youtubot and parent.author == m.author:
                        logging.info('\tDeleting comment %s' % comment_id)
                        if len(body) > 1:
                            logging.info('\t%s' % body[1])
                        comment.delete()
                except AttributeError as e:
                    logging.warning('\tCould not delete requested comment %s' % comment_id)
                    logging.warning('\t%s' % e)
                m.mark_as_read()

        # Fifth, check if the read_only time has expired
        logging.info('STEP 5 - Check if it\'s Time to Switch to Write Mode')
        if self.read_only and time.time() > self.read_only_expiry_time:
            logging.info('\tSwitching to write mode...')
            self.read_only = False

    # Takes a praw comment object and a response string and attempts to reply to the comment.
    # If the reply fails, responds accordingly by either switching to read_only mode or adding
    # the comment's subreddit to the list of banned subreddits
    def submit_response(self, comment, response):
        if self.can_make_changes():
            sub = comment.submission.subreddit
            try:
                reply = comment.reply(response)
                logging.info('\tCommenting on %s in /r/%s' % (comment.permalink, sub))
                # Edit the reply to replace the comment_id placeholder
                new_response = reply.body.replace('$comment_id', reply.name)
                # Also replace the format quote placeholder
                new_response = new_response.replace('$quote', '>')
                reply.edit(new_response)
            except praw.errors.RateLimitExceeded as e:
                # We are commenting too much. Switch to read_only mode
                m = RATELIM_RE.search(str(e))
                try:
                    sleep_duration = int(m.group(1))
                    sleep_unit = m.group(2)
                except (AttributeError, TypeError) as e:
                    logging.warning('\tRatelimit exceeded but time until next allowed post could not be retrieved')
                    logging.warning('\t%s' % e)
                    sleep_duration = 1
                    sleep_unit = 'minutes'
                if sleep_unit == "minutes":
                    sleep_duration = sleep_duration * 60
                # Go to read-only mode for an extra 30 seconds, just to be safe
                sleep_duration += 30
                logging.info('\tComment rate limit exceeded. Switching to read-only mode for %d seconds.' % sleep_duration)
                self.read_only = True
                self.read_only_expiry_time = time.time() + sleep_duration
                self.queue_response(comment, response)
            except praw.errors.APIException as e:
                # The comment was deleted before we could reply so just move on
                logging.warning('\tTried to reply but encountered APIException.')
                logging.warning('\t%s' % e)
            except requests.exceptions.HTTPError as e:
                # We are banned from this subreddit
                logging.warning('\tTried to reply but encountered HTTPError.')
                logging.warning('\t%s' % e)
                logging.warning('\tAdding /r/%s to the list of banned subreddits' % sub)
                banned_subreddits.append(str(sub))
        else:
            logging.info('Ghost mode response:\n{}'.format(response))
