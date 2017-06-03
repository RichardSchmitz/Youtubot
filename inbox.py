import praw


def get_new_pms(r):
    inbox = r.inbox.unread()
    pms = []
    for pm in inbox:
        if isinstance(pm, praw.models.Message):
            pms += pm

    r.inbox.mark_read(pms)

    return pms
