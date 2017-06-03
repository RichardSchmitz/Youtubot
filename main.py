import praw
import logging
import time
import configparser
import youtubot

VERSION = '1.1.0(beta)'
ADMIN_USERNAME = 'theruchet'

logging.basicConfig(format='%(levelname)s:\t%(message)s', filename = '%s-%s.log' % (VERSION, time.strftime('%Y-%m-%dT%H:%M')), level=logging.WARNING)

config = configparser.ConfigParser()
config.read('config.ini')

conf_vars = config['reddit.com']
r = praw.Reddit(client_id=conf_vars['client_id'],
                client_secret=conf_vars['client_secret'],
                user_agent='YouTube link bot (youtubot v {}) by /u/{}'.format(VERSION, ADMIN_USERNAME),
                username=conf_vars['username'],
                password=conf_vars['password'])

# stream = r.subreddit('all').stream.comments()
# print(next(stream).body)

#bot = youtubot.YoutuBot(r)
#bot.run()
