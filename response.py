import re
from apiclient.discovery import build
from urllib.parse import urlparse, parse_qs
import logging
import isodate
import youtubot


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


MAX_DESCRIPTION_LENGTH = 60

YOUTUBE_RE = re.compile(r'youtu(?:be\.com|\.be)/(?!user|results|channel|playlist|static|#)[a-zA-Z0-9_?=&.#-]+')
USERNAME = '_youtubot_'
SUBREDDIT = 'youtubot' # Subreddit that you created for the bot
WIKI_INFO_PATH = 'wiki/index' # Path within the subreddit to link to for "Bot Info"


# This may no longer be necessary since we're not scraping the youtube page directly anymore
def unescape_html(s):
    s = s.replace('&#39;', "'")
    s = s.replace('&#34;', '"')
    s = s.replace('&quot;', '"')
    # This must be last
    s = s.replace('&#38;', '&')
    s = s.replace('&amp;', '&')

    return s


def find_youtube_urls(text):
    return YOUTUBE_RE.findall(unescape_html(text))


def get_urls_from_text(text):
    matches = find_youtube_urls(text)
    # For each youtube video in the comment text
    # Need to strip out trailing period because period matches the regex for cases like
    # &feature=youtu.be, but a trailing period is most likely not part of the URL
    urls = ['https://{}'.format(match).rstrip('.') for match in matches]

    return urls


def get_like_stats(statistics):
        likes_percent = 0
        dislikes_count = 0
        likes_count = 0

        if 'likeCount' in statistics:
            likes_count = int(statistics['likeCount'])
        if 'dislikeCount' in statistics:
            dislikes_count = int(statistics['dislikeCount'])

        total_votes = likes_count + dislikes_count

        if total_votes > 0:
            likes_percent = int(100 * likes_count / total_votes)
        return dict(likes_count=likes_count, likes_percent=likes_percent)

def get_video_id_from_url(url):
    parsed_url = urlparse(url)
    video_id = None
    logger.debug('Attempting to parse id from url={}'.format(url))
    if 'youtube.com' in parsed_url.netloc:
        # Full form URL. Video id is in query param.
        query_params = parse_qs(parsed_url.query)
        if 'v' in query_params:
            video_id = query_params['v'][0]
    elif 'youtu.be' in parsed_url.netloc:
        # Shortened URL. Video id is in path.
        video_id = parsed_url.path.strip('/').split('/')[0]

    logger.debug('Parsed video_id={} from url={}'.format(video_id, url))

    return video_id


def get_concise_description(description):
    if len(description.strip()) == 0:
        return None

    description = description.replace('\n', ' ').replace('\r', ' ')

    if len(description) > MAX_DESCRIPTION_LENGTH:
        description = description[:MAX_DESCRIPTION_LENGTH].strip()
        last_space = description.rfind(' ')
        if last_space > MAX_DESCRIPTION_LENGTH / 2: # arbitrary minimum cutoff length
            description = description[:last_space] + '...'

    return description


def format_cols_for_video(video):
    format_str = '[{}]({})|{}|{}|{}|{:,}+ ({}%)|'
    # Views might be a number or it could be 'Unknown'
    views = video['views']
    try:
        views = int(views)
        format_str += '{:,}'
    except ValueError:
        # Not a number
        format_str += '{}'

    # Pipe (|) characters mess up table formatting, so we need to replace them with html escape sequences
    response = format_str.format(
        video['title'].replace('|', '&#124;'),
        video['url'],
        video['channel'].replace('|', '&#124;'),
        video['published'],
        video['duration'],
        video['likes'],
        video['likes_percent'],
        views
    )
    return response


def generate_comment_response(comment_text, comment_author, videos):
    responded_videos = []
    response_rows = [
        'Title' +   '|Channel' + '|Published'+'|Duration' +'|Likes' +   '|Total Views',
        ':----------:|:----------:|:----------:|:----------:|:----------:|:----------:'
    ]
    for video in videos:
        title_in_comment = video['title'].lower() in comment_text.lower()
        if title_in_comment:
            logger.info("Title found in comment. Won't include info for this video.")
        else:
            responded_videos.append(video)
            response_rows.append(format_cols_for_video(video))

    if len(responded_videos) == 1 and responded_videos[0]['description']:
        response_rows.append('')
        response_rows.append('$quote {}'.format(responded_videos[0]['description']))

    if len(responded_videos) == 0:
        return None
    else:
        delete_url = 'https://np.reddit.com/message/compose/?to={}&subject=delete\%20comment&message=$comment_id\%0A\%0AReason\%3A\%20\%2A\%2Aplease+help+us+improve\%2A\%2A'.format(USERNAME)
        video_s = 'Video'
        if len(responded_videos) > 1:
            video_s = '%ss' % video_s
        start_blurb = '{} linked by /u/{}:\n'.format(video_s, comment_author)
        end_blurb = '---\n\n[^Info](https://np.reddit.com/r/%s/%s) ^| [^/u/%s ^can ^delete](%s) ^| ^v%s' % (SUBREDDIT, WIKI_INFO_PATH, comment_author, delete_url, youtubot.version)

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
            vid = get_video_id_from_url(url)

            if vid:
                urls[vid] = url
                ids.append(vid)

        video_info = []

        if len(ids) > 0:
            # The YouTube API only allows us to request data for up to 50 videos
            # at a time (https://developers.google.com/youtube/v3/docs/videos/list)
            # so we need to break the id list up into chunks of 50 or less
            max_ids_per_call = 50
            id_chunks = [ids[i:i+max_ids_per_call] for i in range(0, len(ids), max_ids_per_call)]
            items = []
            for chunk in id_chunks:
                logger.debug('Sending YouTube API request for {} videos'.format(len(chunk)))
                api_response = self.youtube.videos().list(
                    id=','.join(chunk),
                    part='snippet,statistics,contentDetails'
                ).execute()
                items += api_response['items']

            for item in items:
                if item['id'] not in urls:
                    logger.warn("video_id={} not found in urls but was returned with API response! Skipping this video.".format(item['id']))
                    logger.warn("urls={}".format(urls))
                    logger.warn("ids={}".format(ids))
                    continue

                snippet = item['snippet']
                statistics = item['statistics']
                content_details = item['contentDetails']

                description = get_concise_description(snippet['description'])
                like_stats = get_like_stats(statistics)
                published = isodate.parse_date(snippet['publishedAt'])
                duration = isodate.parse_duration(content_details['duration'])

                video_info.append({
                    'id': item['id'],
                    'url': urls[item['id']],
                    'channel': snippet['channelTitle'],
                    # Currently not including category information as YouTube just responds with a category id.
                    # Category ids refer to different categories based on the region, so I somehow need to figure
                    # out what region the response is referring to. The response table was too wide anyway so for
                    # now category is simply excluded. See https://developers.google.com/youtube/v3/docs/videoCategories/list
                    #'category': 'Unknown',
                    'title': snippet['title'],
                    'description': description,
                    'published': str(published),
                    'duration': str(duration),
                    'likes': like_stats['likes_count'],
                    'likes_percent': like_stats['likes_percent'],
                    'views': statistics.get('viewCount', 'Unknown')
                })

        return video_info

    def get_comment_response(self, comment_text, comment_author):
        urls = get_urls_from_text(comment_text)
        if len(urls) > 0:
            videos = self.get_video_info(urls)
            if len(videos) > 0:
                return generate_comment_response(comment_text, comment_author, videos)
        return None
