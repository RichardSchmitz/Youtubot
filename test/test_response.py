import unittest
from response import get_video_id_from_url, get_like_stats, format_cols_for_video, get_urls_from_text


class TestResponse(unittest.TestCase):
    def test_get_video_id_from_url(self):
        assert get_video_id_from_url('https://youtu.be/x9xOJkhEfmQ') == 'x9xOJkhEfmQ'

        assert get_video_id_from_url('https://youtube.com/watch?v=6zuGk80VS6k') == '6zuGk80VS6k'

        assert get_video_id_from_url('https://youtube.com/higatv') == None

    def test_get_likes_stats(self):
        assert get_like_stats({'likeCount': 1345, 'dislikeCount': 34}) == {'likes_count': 1345, 'likes_percent': 97}

    def test_format_cols_for_video_simple(self):
        assert format_cols_for_video({
            'title': 'On Mid-Set Coaching',
            'url': 'https://www.youtube.com/watch?v=yNakW3yhA18',
            'channel': 'Armada',
            'published': '2017-06-10',
            'duration': '0:08:01',
            'likes': 282,
            'likes_percent': 98,
            'views': 4317
        }) == '[On Mid-Set Coaching](https://www.youtube.com/watch?v=yNakW3yhA18)|Armada|2017-06-10|0:08:01|282+ (98%)|4,317'

    def test_format_cols_for_video_pipes(self):
        assert format_cols_for_video({
            'title': 'Inside Stuff: Live From London With Kristen Ledlow | January 7, 2017 | 2016-17 NBA Season',
            'url': 'https://www.youtube.com/watch?v=wlQ1lTRwz5A',
            'channel': 'Vancho',
            'published': '2017-01-25',
            'duration': '0:02:23',
            'likes': 1,
            'likes_percent': 100,
            'views': 623
        }) == '[Inside Stuff: Live From London With Kristen Ledlow &#124; January 7, 2017 &#124; 2016-17 NBA Season](https://www.youtube.com/watch?v=wlQ1lTRwz5A)|Vancho|2017-01-25|0:02:23|1+ (100%)|623'

    def test_format_cols_for_video_pipes_and_complex(self):
        assert format_cols_for_video({
            'title': 'My Angel Serena | Primary - Inai Sekai [Regret] +HD FC 99.23% 571pp #2',
            'url': 'https://youtu.be/Ewc8tPrgzk8',
            'channel': 'osu! Content',
            'published': '2017-06-05',
            'duration': '0:03:26',
            'likes': 41,
            'likes_percent': 95,
            'views': 1470
        }) == '[My Angel Serena &#124; Primary - Inai Sekai [Regret] +HD FC 99.23% 571pp #2](https://youtu.be/Ewc8tPrgzk8)|osu! Content|2017-06-05|0:03:26|41+ (95%)|1,470'

    def test_get_urls_from_text(self):
        text = """
               Junior Dad, but I always skip the instrumental part.
               Also, this guy has some pretty good covers:
               https://www.youtube.com/watch?v=uJcL8adoBwk
               """
        assert get_urls_from_text(text) == ['https://youtube.com/watch?v=uJcL8adoBwk']

        text = """
               > Scientific Method is great, but "irrationally angry Janeway" may not be a great intro, even if it does culminate in a badass crazy move.
               https://www.youtube.com/watch?v=bZls8aoA4CQ
               https://www.youtube.com/watch?v=sSp9geqULuY
               Mentally I compare these two scenes. The bottom one is from Scientific Method, and the top one is from Lethal Weapon 2. I tend to view Janeway and Martin Riggs as having rather a lot in common, to be honest.
               """
        assert get_urls_from_text(text) == ['https://youtube.com/watch?v=bZls8aoA4CQ', 'https://youtube.com/watch?v=sSp9geqULuY']

        text = """
                    128988612 ^United States Anonymous (ID: x7wpN7EC)
                Jeremy Corbyn: "Immigration is NOT too high." https://youtu.be/yYCutSGtXOg [Embed]
               """
        assert get_urls_from_text(text) == ['https://youtu.be/yYCutSGtXOg']

        text = """
               Thats a pretty good comparison. He's also a pretty good rapper https://youtu.be/JBpL341V02U.
               """
        assert get_urls_from_text(text) == ['https://youtu.be/JBpL341V02U']

        text = """
               I just listened [here](https://www.youtube.com/watch?v=QtREMnVrDS4&t=15s) that ETNZ will take light option for the foils. But I see gusts about 25 knots!!! Ouch!
               """
        assert get_urls_from_text(text) == ['https://youtube.com/watch?v=QtREMnVrDS4&t=15s']

        text = """
               So during my break I was on Youtube when suddenly [HOLY SHIT NEW KHIII TRAILER](https://www.youtube.com/watch?v=p51wHlWY1uM).
               Needless to say, I had a productive Naruto break.
               """
        assert get_urls_from_text(text) == ['https://youtube.com/watch?v=p51wHlWY1uM']

        text = """
               It's pretty difficult to find bona-fide metal in Vocaloid, as a lot of the artists that get grouped as metal are more like emo, hardcore, or hard rock. \n\n[SHEBA](http://vocadb.net/Ar/6042) does good [thrash](https://www.youtube.com/watch?v=74otMglSkwE) and has some of the best screams/growls I've heard from Vocaloids/Utau. \n\n[Annyahoo](http://vocadb.net/Ar/4691) also does a lot of [thrash](https://www.youtube.com/watch?v=FEVSKSmE5e0) but messes with other genres a lot. His production quality varies.\n\n[Senjougahara Yousei](http://vocadb.net/Ar/13350) has done some [djent](https://www.youtube.com/watch?v=ztqLjIaU0B4)/prog in the past that's worth checking out, but he's not very active as of late.\n\nThere's also a lot of small artists with just a few songs like [kotoriP](https://www.youtube.com/watch?v=A5pvjDKmbRA), [Punie Koubou](https://www.youtube.com/watch?v=zYR3kKuKWRc), and [lustybaby](https://www.youtube.com/watch?v=ovRLL_ED2xo).
               """
        assert get_urls_from_text(text) == ['https://youtube.com/watch?v=74otMglSkwE', 'https://youtube.com/watch?v=FEVSKSmE5e0', 'https://youtube.com/watch?v=ztqLjIaU0B4', 'https://youtube.com/watch?v=A5pvjDKmbRA', 'https://youtube.com/watch?v=zYR3kKuKWRc', 'https://youtube.com/watch?v=ovRLL_ED2xo']
