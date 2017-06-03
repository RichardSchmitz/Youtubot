from banned_subreddits import BannedSubreddits
from response import get_comment_response
from comment import get_age, get_score
from inbox import get_new_pms
from config import DEFAULT_CONFIG
import logging
import time
import requests


class YoutuBot(object):
    def __init__(self, reddit, **config_overrides):
        self.bot_config = DEFAULT_CONFIG
        self.bot_config.update(config_overrides)
        self.r = reddit
        self.banned_subreddits = BannedSubreddits(filename=self.bot_config['banned_subreddits_filename'])

    def run(self):
        # todo: maybe handle this with signal instead of try/except. See:
        # https://stackoverflow.com/questions/18499497/how-to-process-sigterm-signal-gracefully
        try:
            while True:
                self._main_loop()
        except KeyboardInterrupt:
            self.banned_subreddits.save()
            logging.info('Received KeyboardInterrupt. Exiting.')

    def _main_loop(self):
        read_only = True
        read_only_expiry_time = time.time()
        next_review_of_comments = read_only_expiry_time
        task_list = []

        # List of comment IDs we have already replied to (so we don't reply twice)
        already_done = []
        youtubot = self.r.user.me()

        # First, check for new comments to reply to
        logging.info('STEP 1 - Retrieving Comments and Submitting/Storing Responses')
        try:
            comment_iter = self.r.subreddit('all').stream.comments()
            for i in range(10):
                comment = next(comment_iter)
                try:
                    # If we haven't done the comment, we're not the author and the comment isn't in a subreddit we're banned from
                    if comment.id not in already_done and not comment.author == youtubot and not self.banned_subreddits.contains(str(comment.subreddit)):
                        # Start a timer
                        timer_start = time.time()
                        response = get_comment_response(comment)
                        if response:
                            logging.info(response)
                            if read_only:
                                # Add the comment and response to a list to process later
                                task_list.append((comment, response))
                                logging.info('\tAppending comment to task list (length %d)' % len(task_list))
                            else:
                                # Submit the response as a comment to Reddit
                                # submit_response(comment, response)
                                timer_total = time.time() - timer_start
                except requests.exceptions.HTTPError as e:
                    logging.warning('\tHTTP Error')
                    logging.warning('\t%s' % e)
        except requests.exceptions.HTTPError as e:
            logging.warning('\tHTTP Error when getting all comments')
            logging.warning('\t%s' % e)
        # Second, check if there are any tasks in the task_list
        # Caution: this hasn't been tested as youtubot now has enough karma to comment constantly
        logging.info('STEP 2 - Checking on Task List (if in Write Mode. Read-only: %s, Task List Len: %d)' % (read_only, len(task_list)))
        if not read_only and len(task_list):
            # Pop one out, make sure it's less than 1.5 hours old, and submit the response
            task = task_list.pop(0)
            comment = task[0]
            response = task[1]
            logging.info('\tPopping comment out of task list (length %d)' % len(task_list))
            if get_age(comment) < 5400.0:
                submit_response(comment, response)
        # Third, check for any of our comments that are more than 1 hour old and have a score < 1
        # Delete them.
        logging.info('STEP 3 - Deleting Downvoted Comments')
        # Only do this every 10 minutes
        if time.time() > next_review_of_comments:
            for comment in youtubot.comments.new():
                if get_age(comment) > 3600.0 and get_score(comment) < 1:
                    logging.info('\tDeleting comment %s in /r/%s' % (comment.id, comment.subreddit))
                    comment.delete()
            next_review_of_comments = time.time() + 600
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
            if read_only and time.time() > read_only_expiry_time:
                logging.info('\tSwitching to write mode...')
                read_only = False

    # Takes a praw Comment object and returns a string representing an appropriate
    # youtubot response which may then be stored or submitted.
    def _get_comment_response(comment):
        response = ''
        is_first_match = True
        num_videos = 0
