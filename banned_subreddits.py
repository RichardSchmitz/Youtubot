import logging


def write_list_to_file(l, filename):
    with open(filename, 'w') as f:
        for item in l:
            f.write('%s\n' % item)

def get_list_from_file(filename):
    l = []
    try:
        with open(filename) as f:
            for line in f:
                l.append(line.rstrip())
    except FileNotFoundError:
        logging.warning('File %s not found. Continuing...' % filename)
    return l

class BannedSubreddits(object):
    def __init__(self, filename=None):
        self.filename = filename
        self.banned_subreddits = get_list_from_file(filename)

    def add(self, subreddit):
        if subreddit not in self.banned_subreddits:
            self.banned_subreddits.append(subreddit)

    def contains(self, subreddit):
        return subreddit in self.banned_subreddits

    def save(self):
        write_list_to_file(self.banned_subreddits, self.filename)
