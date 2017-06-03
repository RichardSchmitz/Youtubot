import time


def get_age(thing):
	return time.time() - thing.created_utc


def get_score(thing):
	return thing.ups - thing.downs
