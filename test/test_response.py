import unittest
from response import get_video_id_from_url


class TestResponse(unittest.TestCase):
    def test_get_video_id_from_url(self):
        assert get_video_id_from_url('https://youtu.be/x9xOJkhEfmQ') == 'x9xOJkhEfmQ'

        assert get_video_id_from_url('https://youtube.com/watch?v=6zuGk80VS6k') == '6zuGk80VS6k'

        assert get_video_id_from_url('https://youtube.com/higatv') == None