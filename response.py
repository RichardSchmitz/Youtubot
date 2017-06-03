import re


YOUTUBE_RE = re.compile(r'youtu(?:be\.com|\.be)/(?!user|results|channel|#)[\w?=&-]+')
USERNAME = '_youtubot_'
SUBREDDIT = 'bot_subreddit' # Subreddit that you created for the bot
WIKI_INFO_PATH = 'wiki/index' # Path within the subreddit to link to for "Bot Info"
WIKI_MODS_PATH = 'wiki/index#wiki_mods' # Path within the subreddit to link to for "Mods"
version = '1.1.0(beta)'
published = '2017-06-03'


def unescape_html(s):
    s = s.replace('&#39;', "'")
    s = s.replace('&#34;', '"')
    s = s.replace('&quot;', '"')
    # This must be last
    s = s.replace('&#38;', '&')
    s = s.replace('&amp;', '&')

    return s


def get_comment_response(comment):
    response = ''
    is_first_match = True
    num_videos = 0
    matches = YOUTUBE_RE.finditer(unescape_html(comment.body))
    # For each youtube video in the comment text
    for match in matches:
        link = match.group()
        # Formulate and post a response
        link = 'https://%s' % link
        response += 'Found link: {}\n'.format(link)
        # data = getDataFromYouTube(link)
        # if data:
        #     try:
        #         title_in_comment = re.search(data['title'].lower(), comment.body.lower())
        #     except:
        #         e = sys.exc_info()[0]
        #         logging.error('RE error: %s' % e)
        #         title_in_comment = False
        # if data and not title_in_comment:
        #     num_videos += 1
        #     # Respond in markup table format
        #     response = '%s[%s](%s) (%s) by %s\n\nPublished|Duration|Likes|Total Views\n:----------:|:----------:|:----------:|:----------:\n%s|%s|%s+ (%s%%)|%s+\n\n' % (response, data['title'], link, data['category'], data['author'], data['published'],  data['duration'], data['likes'], data['likes_percent'], data['views'])
        #     if is_first_match:
        #         # To save space, only include a summary for the first video
        #         is_first_match = False
        #         #temp
        #         try:
        #             response = '%s$quote %s\n\n' % (response, data['summary'])
        #         except UnicodeDecodeError:
        #             # This error shouldnt be happening. Is something wrong with data['summary']?
        #             # Non-unicode characters are causing this to fail (eg. some chinese characters, etc)
        #             # Also found for http://youtube.com/watch?v=-_8K7bOiBAA ????
        #             logging.warning('\t%s' % data)
        #             logging.warning('\tFound at %s' % link)
        # elif data and title_in_comment:
        #     # Don't respond if the video's title is already in the comment
        #     # temp
        #     logging.info('\tTitle found in comment %s' % comment.permalink)
    if len(response) > 0:
        # Append the starting and ending blurbs
        delete_url = 'http://www.reddit.com/message/compose/?to={}&subject=delete\%20comment&message=$comment_id\%0A\%0AReason\%3A\%20\%2A\%2Aplease+help+us+improve\%2A\%2A'.format(USERNAME)
        video_s = 'video'
        if num_videos > 1:
            video_s = '%ss' % video_s
        start_blurb = 'Here is some information on the %s linked by /u/%s:\n\n---\n\n' % (video_s, comment.author)
        end_blurb = '---\n\n[^Bot ^Info](http://www.reddit.com/r/%s/%s) ^| [^Mods](http://www.reddit.com/r/%s/%s) ^| [^Parent ^Commenter ^Delete](%s) ^| ^version ^%s ^published ^%s \n\n^youtubot ^is ^in ^beta ^phase. ^Please [^help ^us ^improve](http://www.reddit.com/r/%s/) ^and ^better ^serve ^the ^Reddit ^community.' % (SUBREDDIT, WIKI_INFO_PATH, SUBREDDIT, WIKI_MODS_PATH, delete_url, version, published, SUBREDDIT)
        response = '%s%s%s' % (start_blurb, response, end_blurb)
    return response
