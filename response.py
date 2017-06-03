import re
from apiclient.discovery import build
from urllib.parse import urlparse, parse_qs
import logging

MAX_DESCRIPTION_LENGTH = 240

YOUTUBE_RE = re.compile(r'youtu(?:be\.com|\.be)/(?!user|results|channel|playlist|#)[\w?=&-.]+')
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

def get_video_id_from_url(url):
    parsed_url = urlparse(url)
    video_id = None
    logging.debug('Attempting to parse id from url={}'.format(url))
    if 'youtube.com' in parsed_url.netloc:
        # Full form URL. Video id is in query param.
        video_id = parse_qs(parsed_url.query)['v'][0]
    elif 'youtu.be' in parsed_url.netloc:
        # Shortened URL. Video id is in path.
        video_id = parsed_url.path.strip('/').split('/')[0]

    logging.debug('Parsed video_id={} from url={}'.format(video_id, url))

    return video_id

def get_concise_description(description):
    description = description.replace('\n', ' ')

    if len(description) > MAX_DESCRIPTION_LENGTH:
        description = description[:MAX_DESCRIPTION_LENGTH].strip()
        last_space = description.rfind(' ')
        if last_space > 100: # arbitrary minimum cutoff length
            description = description[:last_space] + '...'

    return description

def format_cols_for_video(video):
    response = '[{}]({})|{}|{}|{}|{}|{}+ ({}%)|{}'.format(
        video['title'],
        video['url'],
        video['category'],
        video['channel'],
        video['published'],
        video['duration'],
        video['likes'],
        video['likes_percent'],
        video['views']
    )
    return response

def generate_comment_response(comment_text, comment_author, videos):
    responded_videos = []
    response_rows = [
        'Title' +   '|Category' +'|Channel' + '|Published'+'|Duration' +'|Likes' +   '|Total Views',
        ':----------:|:----------:|:----------:|:----------:|:----------:|:----------:|:----------:'
    ]
    for video in videos:
        try:
            title_in_comment = re.search(data['title'].lower(), comment_text.lower())
        except Exception as e:
            logging.error('RE error: %s' % e)
            title_in_comment = False
        if title_in_comment:
            logging.info("Title found in comment. Won't include info for this video.")
        else:
            responded_videos.append(video)
            response_rows.append(format_cols_for_video(video))

    if len(responded_videos) == 1:
        response_rows.append('')
        response_rows.append('$quote {}'.format(responded_videos[0]['description']))

    if len(responded_videos) == 0:
        return None
    else:
        delete_url = 'http://www.reddit.com/message/compose/?to={}&subject=delete\%20comment&message=$comment_id\%0A\%0AReason\%3A\%20\%2A\%2Aplease+help+us+improve\%2A\%2A'.format(USERNAME)
        video_s = 'Video'
        if len(responded_videos) > 1:
            video_s = '%ss' % video_s
        start_blurb = '{} linked by /u/{}:\n\n---\n\n'.format(video_s, comment_author)
        end_blurb = '---\n\n[^Bot ^Info](http://www.reddit.com/r/%s/%s) ^| [^Mods](http://www.reddit.com/r/%s/%s) ^| [^Parent ^Commenter ^Delete](%s) ^| ^version ^%s ^published ^%s \n\n^youtubot ^is ^in ^beta ^phase. ^Please [^help ^us ^improve](http://www.reddit.com/r/%s/) ^and ^better ^serve ^the ^Reddit ^community.' % (SUBREDDIT, WIKI_INFO_PATH, SUBREDDIT, WIKI_MODS_PATH, delete_url, version, published, SUBREDDIT)

        response_rows.insert(0, start_blurb)
        response_rows.append('')
        response_rows.append(end_blurb)

        return '\n'.join(response_rows)

class YoutubeCommentResponder(object):
    def __init__(self, config):
        self.youtube = build(config['api_name'], config['api_version'], developerKey=config['api_key'])

    def get_video_info(self, video_urls):
        urls = {}
        ids = []
        for url in video_urls:
            # temporary hack because some of the URLs are ending up with a ) or * at the end.. dont know why
            url.strip(')')
            url.strip('*')

            vid = get_video_id_from_url(url)
            urls[vid] = url
            ids.append(vid)
        api_response = self.youtube.videos().list(
            id=','.join(ids),
            part='snippet'
        ).execute()

        video_info = []
        for item in api_response['items']:
            snippet = item['snippet']
            description = get_concise_description(snippet['description'])

            video_info.append({
                'id': item['id'],
                'url': urls[item['id']],
                'channel': snippet['channelTitle'],
                'category': 'Unknown',
                'title': snippet['title'],
                'description': description,
                'published': snippet['publishedAt'],
                'duration': 'Unknown',
                'likes': 'Unknown',
                'likes_percent': 'Unknown',
                'views': 'Unknown'
            })

        return video_info

    def get_comment_response(self, comment_text, comment_author):
        matches = YOUTUBE_RE.finditer(unescape_html(comment_text))
        # For each youtube video in the comment text
        urls = []
        for match in matches:
            url = match.group()
            # Formulate and post a response
            url = 'https://%s' % url
            urls.append(url)
        if len(urls) > 0:
            videos = self.get_video_info(urls)
            return generate_comment_response(comment_text, comment_author, videos)
        else:
            return None
