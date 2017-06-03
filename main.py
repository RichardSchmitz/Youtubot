import praw
import logging
import time
import configparser
import youtubot
import response

VERSION = '1.1.0(beta)'
ADMIN_USERNAME = 'theruchet'

logging.basicConfig(format='%(levelname)s:\t%(message)s', filename = 'youtubot_%s.log' % (time.strftime('%Y-%m-%d')), level=logging.DEBUG)
# logging.basicConfig(format='%(levelname)s:\t%(message)s', level=logging.DEBUG)

config = configparser.ConfigParser()
config.read('config.ini')

reddit_vars = config['reddit.com']
r = praw.Reddit(client_id=reddit_vars['client_id'],
                client_secret=reddit_vars['client_secret'],
                user_agent='YouTube link bot (youtubot v {}) by /u/{}'.format(VERSION, ADMIN_USERNAME),
                username=reddit_vars['username'],
                password=reddit_vars['password'])

y = response.YoutubeCommentResponder(config['youtube.com'])

bot = youtubot.YoutuBot(reddit=r,
                        responder=y,
                        ghost_mode=True)
bot.run()
