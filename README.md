Youtubot
========

A bot that transcribes YouTube links on Reddit

##Setup##
###General###
Under the heading *Reddit info*, update the configuration variables to suit your needs. You should have a reddit account so that people can message you about the bot if they have any questions/issues, and your bot should have an accout so that it can post. Or you could just let the bot post on your account. Note that if you give the bot a brand new account, it will be unable to post in quick succession until it gains enough karma. It will automatically switch to read-only mode so that it keeps track of what to comment on at the next time it is allowed. You may also choose to create a subreddit for the bot such as */r/my_youtubot*.In this case, change the variable SUBREDDIT to *my_youtubot*.

There are two options as far as logging is concerned. You can have youtubot spit everything out onto the console (great if you're debugging), or you can have it log only the important messages to a time-stamped file. Just comment/uncomment the appropriate lines.

###Dependencies###
Youtubot uses PRAW (https://praw.readthedocs.org/en/v2.1.16/) and BeautifulSoup 3.2.1 (http://www.crummy.com/software/BeautifulSoup/), two excellent python libraries. These will need to be installed before running.

##Issues##
As of June, Youtubot was working pretty fantabulously. However, in the time since I've last used it, either PRAW updates have messed it up or else Reddit's switch to HTTPS did it in. I haven't had time to debug it yet. It seems to time out when attempting to load comments from /r/all.

There is a lot of error handling as a result of scraping from YouTube. It would probably be worthwhile to sign youtubot up with YouTube so it can use the API, I just haven't bothered yet as it's not that critical of a project.

There is a list of TODOs at the top of main.py.
