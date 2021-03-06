import praw
import logging
import time
import configparser
import youtubot
import response
from greplin.scales import graphite

ADMIN_USERNAME = 'theruchet'

logging.basicConfig(format='%(asctime)s [%(name)s] %(levelname)s: %(message)s', filename = 'logs/youtubot_%s.log' % (time.strftime('%Y-%m-%d')), level=logging.INFO)
# logging.basicConfig(format='%(levelname)s:\t%(message)s', level=logging.DEBUG)

config = configparser.ConfigParser()
config.read('config.ini')

reddit_vars = config['reddit.com']
r = praw.Reddit(client_id=reddit_vars['client_id'],
                client_secret=reddit_vars['client_secret'],
                user_agent='YouTube link bot (youtubot v {}) by /u/{}'.format(youtubot.version, ADMIN_USERNAME),
                username=reddit_vars['username'],
                password=reddit_vars['password'])

y = response.YoutubeCommentResponder(config['youtube.com'])

bot = youtubot.YoutuBot(reddit=r,
                        responder=y,
                        ghost_mode=False,
                        subreddit='all')

graphite_vars = config['graphite']
graphitePeriodicPusher = graphite.GraphitePeriodicPusher(graphite_vars['host'], int(graphite_vars['port']), graphite_vars['prefix'])
graphitePeriodicPusher.allow("*") # Logs everything to graphite
graphitePeriodicPusher.start()

bot.run()
logging.shutdown()
