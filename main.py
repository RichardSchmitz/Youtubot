# TODO:		-Better algorithm for determining whether or not to respond?
#		-Can potentially crash if there are non-unicode characters in the video title
#		 (looks like plugging this into re.search() causes re to raise an exception)
#		-Hover-to-show
#		-When someone PMs to delete comment, print a permalink to their comment and the reason
#		 for the request to a dedicated, time-stamped log file (so I can browse later)
#		-For some reason the bot seems to not be able to retreive comments from reddit recently.
#		 This may be a result of reddit's recent move to HTTPS or recent PRAW updates...

import re, time, urllib2, praw, requests, logging, math, sys
from BeautifulSoup import BeautifulSoup, BeautifulStoneSoup, Tag

# The current version of youtubot
version = '1.0.3(beta)'
published = '27/04/2014'

# Reddit info
ADMIN_USERNAME = 'your_username' # This is your Reddit username
USERNAME = 'bot_username' # Username that you created for the bot
PASSWORD = 'bot_password' # Password for the bot's account
SUBREDDIT = 'bot_subreddit' # Subreddit that you created for the bot
WIKI_INFO_PATH = 'wiki/index' # Path within the subreddit to link to for "Bot Info"
WIKI_MODS_PATH = 'wiki/index#wiki_mods' # Path within the subreddit to link to for "Mods"


# Set the logging level, file and format
# Write all INFO to the console (for testing purposes)
#logging.basicConfig(format='%(levelname)s:\t%(message)s', level=logging.INFO)
# Write only WARNING and ERROR messages into a date-stamped file (for general running purposes)
logging.basicConfig(format='%(levelname)s:\t%(message)s', filename = '%s-%s.log' % (version, time.strftime('%H:%M-%d/%m/%Y')), level=logging.WARNING)

# Regex for testing if a token is a YouTube video URL
YOUTUBE_RE = re.compile(r'youtu(?:be\.com|\.be)/(?!user|results|channel|#)[\w?=&-]+')
# Regex for getting the number of seconds/minutes before we can post again
RATELIM_RE = re.compile(r'(\d+) (minutes|seconds)')

# List of comment IDs we have already replied to (so we don't reply twice)
already_done = []

# Mode: read-only (adds comments to task_list for future processing)
#	write (processes comments as normal, switching to read-only mode if RateLimit exceeded)
read_only = False
read_only_expiry_time = time.time()

# Set the next time to check our comment history for downvoted comments
next_review_of_comments = read_only_expiry_time

# Keep a count of the number of comments successfully made
comments_made = 0

# A list of comments to add later when the RateLimit timer has expired and there aren't any
# other responses to post. Each item is of the form (comment, response)
task_list = []

# Takes a string containing escaped HTML characters (eg. &quot;, &amp;) and returns the
# unescaped string
def unescape_html(s):
	s = s.replace('&#39;', "'")
	s = s.replace('&#34;', '"')
	s = s.replace('&quot;', '"')
	# This must be last
	s = s.replace('&#38;', '&')
	s = s.replace('&amp;', '&')

	return s

# Takes the name of a file as a string and returns a dictionary where even lines (0-indexed)
# are the keys and odd lines, split into lists on ', ', are the values
def file_to_dict(fname):
	d = {}
	try:
		f = open(fname)
		key = f.readline()
		while key:
			key = line.rstrip()
			value = f.readline.split(', ')
			d[key] = value
	except IOError:
		logging.warning('File %s not found. Continuing...' % fname)
	return d

# Takes the name of a file as a string and returns a list of the lines in that file
# with newlines removed. Returns an empty list with a warning if the file is not found
def file_to_list(fname):
	l = []
	try:
		f = open(fname)
		for line in f:
			l.append(line.rstrip())
	except IOError:
		logging.warning('File %s not found. Continuing...' % fname)
	return l

# Takes a list and a string representing a file name. Writes each element of the list to
# the file, appending a new line after each item.
def list_to_file(l, fname):
	f = open(fname, 'w')
	for item in l:
		f.write('%s\n' % item)
	f.close()

# Takes an integer num and an optional argument for the number of significant figures to
# retain. Returns num floored (NOT rounded) to that number of significant figures.
def approx_count(num, sf = 2):
	if num == 0:
		order = 0
	else:
		order = int(math.log10(num))
	factor = 10**(order - sf + 1)
	return int(num / factor * factor)

# Takes a string representing a YouTube video URL and returns a dictionary of relevant
# meta data from the video (views, likes/dislikes, title, etc)
def getDataFromYouTube(url):
	data = {}
	try:
		html_page = urllib2.urlopen(url)
	except urllib2.HTTPError:
		logging.error('HTTPError for url %s' % url)
		logging.error('\tFound at: %s' % comment.permalink)
		return None
	soup = BeautifulSoup(html_page.read())
	# Get likes and dislikes and convert them to a percent
	try:
		likes = soup.find('span', {'class': 'likes-count'}).string
	except AttributeError, e:
		# Video might not be available in your region
		logging.error('Couldn\'t get like count from link %s' % url)
		logging.error('\t%s' % e)
		logging.error('\tFound at: %s' % comment.permalink)
		try:
			unavailable_message = soup.find('h1', {'id': 'unavailable-message'}).string
		except AttributeError:
			# Not a video and no unavailable message.
			# Link may be a short link to a channel.
			# Quit.
			return None
		if unavailable_message:
			# Print to the console the reason for the video being unavailable
			logging.error('\tVideo Unavailable Message: %s' % unavailable_message)
		return None
	likes = int(''.join(likes.split(',')))
	dislikes = soup.find('span', {'class': 'dislikes-count'}).string
	dislikes = int(''.join(dislikes.split(',')))
	try:
		likes_percent = int(100*float(likes)/float(likes+dislikes))
	except ZeroDivisionError:
		likes_percent = 0
	data['likes_percent'] = '{:,}'.format(likes_percent)
	likes = approx_count(likes)
	data['likes'] = '{:,}'.format(likes)
	# Get the video summary and convert it to plain text
	s_elems = soup.find('p', {'id': 'eow-description'}).contents
	summary = ''
	# String together a brief summary based on s_elems
	for elem in s_elems:
		tmp = str(elem)
		if isinstance(elem, Tag):
			if elem.name == 'br':
				# If the element is a newline, this is the end of the summary
				break
			if elem.name == 'a':
				# If the element is a link, format it to markup's link format
				tmp = '[%s](%s)' % (elem.text, elem['href'])
			if elem.name == 'em':
				# If the element is emphasis, format it to markup's italic format
				tmp = '*%s*' % elem.text
		try:
			# Concatenate the current element onto the end of the summary
			summary = '%s%s' % (summary, tmp)
		except UnicodeDecodeError, e:
			# Non-unicode characters cause this to crash
			logging.warning('\tUnicode Decode Error when making summary: %s' % e)
			logging.warning('\tContinuing...')
	summary = unescape_html(summary)
	# Add some processing for anchor tags... get teh href...
	data['summary'] = summary
	# Get the publishing date
	try:
		published = soup.find('span', {'id': 'eow-date'}).string
	except AttributeError, e:
		logging.warning('\t%s' % e)
		published = 'Unavailable'
	data['published'] = published
	# Get the xml page
	try:
		video_id = soup.find('meta', {'itemprop': 'videoId'})['content']
		url2 = 'http://gdata.youtube.com/feeds/api/videos/%s' % video_id
	except TypeError, e:
		logging.error('Could not extract video ID for link %s' % url)
		logging.error('\t%s' % e)
		logging.error('\tFound at: %s' % comment.permalink)
		return None
	try:
		xml_page = urllib2.urlopen(url2)
	except urllib2.HTTPError:
		logging.error('HTTPError for url2 %s' % url2)
		logging.error('\tFound at: %s' % comment.permalink)
		return None
	stonesoup = BeautifulStoneSoup(xml_page.read())
	# Get the YouTube video title
	title = stonesoup.find('title', {'type': 'text'}).string.strip()
	title = unescape_html(title)
	data['title'] = title
	# Get the view count
	try:
		views = int(stonesoup.find('yt:statistics')['viewcount'])
	except TypeError, e:
		logging.error('Could not extract viewcount for link %s' % url)
		logging.error('\t%s' % e)
		logging.error('\tFound at: %s' % comment.permalink)
		return None
	views = approx_count(views)
	data['views'] = '{:,}'.format(views)
	# Get the author's name
	author = stonesoup.find('name').string
	data['author'] = author
	# Get the video duration
	full_seconds = int(stonesoup.find('yt:duration')['seconds'])
	seconds = full_seconds % 60
	full_minutes = (full_seconds - seconds) / 60
	minutes = full_minutes % 60
	hours = (full_minutes - minutes) / 60
	duration = '%dm%ds' % (minutes, seconds)
	if hours:
		duration = '%dh%s' % (hours, duration)
	data['duration'] = duration
	# Get video category
	category = stonesoup.find('media:category').string
	data['category'] = category
	
	return data

# Takes a praw Comment object and returns a string representing an appropriate
# youtubot response which may then be stored or submitted.
def get_comment_response(comment):
	response = ''
	is_first_match = True
	num_videos = 0
	matches = YOUTUBE_RE.finditer(unescape_html(comment.body))
	# For each youtube video in the comment text
	for match in matches:
		link = match.group()
		# Formulate and post a response
		link = 'http://%s' % link
		data = getDataFromYouTube(link)
		if data:
			try:
				title_in_comment = re.search(data['title'].lower(), comment.body.lower())
			except:
				e = sys.exc_info()[0]
				logging.error('RE error: %s' % e)
				title_in_comment = False
		if data and not title_in_comment:
			num_videos += 1
			# Respond in markup table format
			response = '%s[%s](%s) (%s) by %s\n\nPublished|Duration|Likes|Total Views\n:----------:|:----------:|:----------:|:----------:\n%s|%s|%s+ (%s%%)|%s+\n\n' % (response, data['title'], link, data['category'], data['author'], data['published'],  data['duration'], data['likes'], data['likes_percent'], data['views'])
			if is_first_match:
				# To save space, only include a summary for the first video
				is_first_match = False
				#temp
				try:
					response = '%s$quote %s\n\n' % (response, data['summary'])
				except UnicodeDecodeError:
					# This error shouldnt be happening. Is something wrong with data['summary']?
					# Non-unicode characters are causing this to fail (eg. some chinese characters, etc)
					# Also found for http://youtube.com/watch?v=-_8K7bOiBAA ????
					logging.warning('\t%s' % data)
					logging.warning('\tFound at %s' % link)
		elif data and title_in_comment:
			# Don't respond if the video's title is already in the comment
			# temp
			logging.info('\tTitle found in comment %s' % comment.permalink)
	if len(response) > 0:
		# Append the starting and ending blurbs
		delete_url = 'http://www.reddit.com/message/compose/?to=%s&subject=delete\%20comment&message=$comment_id\%0A\%0AReason\%3A\%20\%2A\%2Aplease+help+us+improve\%2A\%2A' % USERNAME
		video_s = 'video'
		if num_videos > 1:
			video_s = '%ss' % video_s
		start_blurb = 'Here is some information on the %s linked by /u/%s:\n\n---\n\n' % (video_s, comment.author)
		end_blurb = '---\n\n[^Bot ^Info](http://www.reddit.com/r/%s/%s) ^| [^Mods](http://www.reddit.com/r/%s/%s) ^| [^Parent ^Commenter ^Delete](%s) ^| ^version ^%s ^published ^%s \n\n^youtubot ^is ^in ^beta ^phase. ^Please [^help ^us ^improve](http://www.reddit.com/r/%s/) ^and ^better ^serve ^the ^Reddit ^community.' % (SUBREDDIT, WIKI_INFO_PATH, SUBREDDIT, WIKI_MODS_PATH, delete_url, version, published, SUBREDDIT)
		response = '%s%s%s' % (start_blurb, response, end_blurb)
	return response

# Takes a praw comment object and a response string and attempts to reply to the comment.
# If the reply fails, responds accordingly by either switching to read_only mode or adding
# the comment's subreddit to the list of banned subreddits
def submit_response(comment, response):
	global comments_made
	global read_only
	global banned_subreddits
	global task_list
	global read_only_expiry_time
	sub = comment.submission.subreddit
	try:
		reply = comment.reply(response)
		logging.info('\tCommenting on %s in /r/%s' % (comment.permalink, sub))
		# Edit the reply to replace the comment_id placeholder
		new_response = reply.body.replace('$comment_id', reply.name)
		# Also replace the format quote placeholder
		new_response = new_response.replace('$quote', '>')
		reply.edit(new_response)
		# Don't reply to this comment again
		already_done.append(comment.id)
		comments_made += 1
	except praw.errors.RateLimitExceeded, e:
		# We are commenting too much. Switch to read_only mode
		m = RATELIM_RE.search(str(e))
		try:
			sleep_duration = int(m.group(1))
			sleep_unit = m.group(2)
		except (AttributeError, TypeError), e:
			logging.warning('\tRatelimit exceeded but time until next allowed post could not be retrieved')
			logging.warning('\t%s' % e)
			sleep_duration = 1
			sleep_unit = 'minutes'
		if sleep_unit == "minutes":
			sleep_duration = sleep_duration * 60
		# Go to read-only mode for an extra 30 seconds, just to be safe
		sleep_duration += 30
		logging.info('\tComment rate limit exceeded. Switching to read-only mode for %d seconds.' % sleep_duration)
		read_only = True
		read_only_expiry_time = time.time() + sleep_duration
		task_list.append((comment, response))
	except praw.errors.APIException, e:
		# The comment was deleted before we could reply so just move on
		logging.warning('\tTried to reply but encountered APIException.')
		logging.warning('\t%s' % e)
	except requests.exceptions.HTTPError, e:
		# We are banned from this subreddit
		logging.warning('\tTried to reply but encountered HTTPError.')
		logging.warning('\t%s' % e)
		logging.warning('\tAdding /r/%s to the list of banned subreddits' % sub)
		banned_subreddits.append(str(sub))

# Takes a praw thing object (comment, submission, message...)
# and returns its age in seconds
def get_age(thing):
	return time.time() - thing.created_utc

# Takes a praw thing object (comment, submission, message...)
# and returns the thing's score (upvotes - downvotes)
def get_score(thing):
	return thing.ups - thing.downs

# Gets unread praw Message objects from the inbox, returning them
# as a list
def get_new_pms():
	inbox = r.get_unread()
	pms = []
	for pm in inbox:
		if isinstance(pm, praw.objects.Message):
			pms.append(pm)
	return pms

# List of subreddits where we are not allowed to post
banned_subreddits_fname = 'banned_subreddits.txt'
banned_subreddits = file_to_list(banned_subreddits_fname)

# Dictionary of subreddits (keys) where we use spoiler tags (values as (start,end) )
# is this going to work...? currently unused...
spoiler_subreddits_fname = 'spoiler_subreddits.txt'
spoiler_subreddits = file_to_dict(spoiler_subreddits_fname)

# Connect to reddit
logging.info('Connecting to reddit...')
r = praw.Reddit('testing1234')#('YouTube link bot (youtubot v %s) by /u/%s' % (version, ADMIN_USERNAME))
r.login(USERNAME, PASSWORD)
youtubot = r.get_redditor(user_name = USERNAME)

try:
	# The main program loop
	while True:
		# First, check for new comments to reply to
		logging.info('STEP 1 - Retrieving Comments and Submitting/Storing Responses')
		# This seemed redundant. Is this error handling necessary? Could time out I guess...
		#try:
		#	all_comments = r.get_comments('all')
		#except requests.exceptions.HTTPError, e:
		#	logging.warning('\tError getting comment generator')
		#	logging.warning('\t%s' % e)
		try:
			comment_iter = r.get_comments('all')
			for comment in comment_iter: #r.get_comments('all'):
				try:
					# If we haven't done the comment, we're not the author and the comment isn't in a subreddit we're banned from
					if comment.id not in already_done and not comment.author == youtubot and not str(comment.subreddit) in banned_subreddits:
						# Start a timer
						timer_start = time.time()
						response = get_comment_response(comment)
						if response:
							if read_only:
								# Add the comment and response to a list to process later
								task_list.append((comment, response))
								logging.info('\tAppending comment to task list (length %d)' % len(task_list))
							else:
								# Submit the response as a comment to Reddit
								submit_response(comment, response)
								timer_total = time.time() - timer_start
								logging.info('\tResponse took %d s' % timer_total)
				except requests.exceptions.HTTPError, e:
					logging.warning('\tHTTP Error')
					logging.warning('\t%s' % e)
		except requests.exceptions.HTTPError, e:
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
			for comment in youtubot.get_comments():
				if get_age(comment) > 3600.0 and get_score(comment) < 1:
					logging.info('\tDeleting comment %s in /r/%s' % (comment.id, comment.subreddit))
					comment.delete()
			next_review_of_comments = time.time() + 600
		# Fourth, check the inbox for any unread PMs
		logging.info('STEP 4 - Check PMs and Respond Accordingly')
		messages = get_new_pms()
		for m in messages:
			if m.subject == 'delete comment':
				body = m.body.split('\n\n', 1)
				comment_id = body[0]
				# This will return None if no comment exists with comment_id
				comment = r.get_info(thing_id = comment_id)
				try:
					parent = r.get_info(thing_id = comment.parent_id)
					# If there is such a comment belonging to us, and the sender of the message is the parent commentor
					if comment and comment.author == youtubot and parent.author == m.author:
						logging.info('\tDeleting comment %s' % comment_id)
						if len(body) > 1:
							logging.info('\t%s' % body[1])
						comment.delete()
				except AttributeError, e:
					logging.warning('\tCould not delete requested comment %s' % comment_id)
					logging.warning('\t%s' % e)
				m.mark_as_read()
		# Fifth, check if the read_only time has expired
		logging.info('STEP 5 - Check if it\'s Time to Switch to Write Mode')
		if read_only and time.time() > read_only_expiry_time:
			logging.info('\tSwitching to write mode...')
			read_only = False
except KeyboardInterrupt:
	# Write the data to a file
	list_to_file(banned_subreddits, banned_subreddits_fname)
	# Print number of comments made this round
	logging.info('\nMade %d comments' % comments_made)
	# Exit gracefully
	logging.info('Exiting.')
