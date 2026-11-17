import unittest
from unittest.mock import patch, call
from buffer_tiktok import post_new_video as pub

class BufferTiktokSafetyTests(unittest.TestCase):

    def test_recovery_cannot_flood_15_short_posts(self):
        self.assertEqual(pub.MAX_PER_24H, 3)
        self.assertGreaterEqual(pub.MIN_PUBLISH_SECONDS, 8)

    def test_recovery_rejects_3_second_video_even_if_buffer_accepts_it(self):
        from pathlib import Path
        fake = {"streams": [{"codec_type": "video", "codec_name": "h264",
                 "avg_frame_rate": "25/1"}],
                "format": {"duration": "3.08"}}
        with patch.object(pub, "ffprobe", return_value=fake):
            with self.assertRaisesRegex(RuntimeError, "short clips"):
                pub.ready_video(Path("social_videos/old-3-second.mp4"))

    def test_connects_only_requested_handle(self):
        def response(key, query, variables=None):
            if "organizations" in query:
                return {"account": {"organizations": [{"id":"org-1","name":"Test"}]}}
            return {"channels": [
                {"id":"wrong","name":"another_creator","service":"tiktok","externalLink":"https://www.tiktok.com/@another_creator","isDisconnected":False,"isLocked":False},
                {"id":"ours","name":"photofiver.photof","service":"tiktok","externalLink":"https://www.tiktok.com/@photofiver.photof","isDisconnected":False,"isLocked":False}
            ]}
        with patch.object(pub,"gql",side_effect=response):
            self.assertEqual(pub.verify_tiktok_channel("fake"),"ours")
            with self.assertRaisesRegex(RuntimeError,"Cannot uniquely verify"):
                pub.verify_tiktok_channel("fake","wrong")

    def test_refuses_other_channel(self):
        with patch.object(pub,"gql",side_effect=[
             {"account":{"organizations":[{"id":"org-1"}]}},
             {"channels":[{"id":"bad","name":"other","service":"tiktok","isDisconnected":False,"isLocked":False}]}]):
            with self.assertRaisesRegex(RuntimeError,"Cannot uniquely verify"):
                pub.verify_tiktok_channel("fake")

    def test_locked_target_rejected(self):
        with patch.object(pub,"gql",side_effect=[
             {"account":{"organizations":[{"id":"org-1"}]}},
             {"channels":[{"id":"ours","name":"photofiver.photof","service":"tiktok","isDisconnected":False,"isLocked":True}]}]):
            with self.assertRaisesRegex(RuntimeError,"disconnected or locked"):
                pub.verify_tiktok_channel("fake")

    def test_commit_when_changes_exist(self):
        with patch.object(pub,"git") as git, patch.object(pub.subprocess,"call",return_value=1):
            pub.commit_changes("buffer_tiktok/attempts.json")
            self.assertTrue(any(x.args[0] == "commit" for x in git.call_args_list))
            self.assertTrue(any(x.args[0] == "push" for x in git.call_args_list))

    def test_no_commit_when_clean(self):
        with patch.object(pub,"git") as git, patch.object(pub.subprocess,"call",return_value=0):
            pub.commit_changes("buffer_tiktok/attempts.json")
            self.assertFalse(any(x.args[0] == "commit" for x in git.call_args_list))

    def test_no_credentials_means_no_post(self):
        with patch.dict(pub.os.environ,{"BUFFER_API_KEY":"","BUFFER_TIKTOK_CHANNEL_ID":""}):
            with patch.object(pub,"gql") as gql:
                self.assertIsNone(pub.main())
                gql.assert_not_called()

    def test_coffee_caption_mentions_topic_and_discloses_ai(self):
        from pathlib import Path
        from buffer_tiktok.captions import make_caption
        text = make_caption(Path("social_videos/new-coffee-cat.mp4"))
        self.assertIn("coffee", text.lower())
        self.assertIn("#AIGenerated", text)
        self.assertIn("?", text)
        self.assertLess(len(text), 2200)

    def test_custom_caption_adds_disclosure(self):
        import tempfile, json
        from pathlib import Path
        from buffer_tiktok.captions import make_caption
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "new-special-cat.mp4"
            source.with_suffix(".json").write_text(
                json.dumps({"caption": "The secret life of cats! #Cats"}), encoding="utf-8")
            text = make_caption(source)
            self.assertIn("#AIGenerated", text)
            self.assertIn("The secret life", text)

    def test_neutral_fallback_does_not_invent_scene(self):
        from pathlib import Path
        from buffer_tiktok.captions import make_caption
        text = make_caption(Path("social_videos/new-special-2026.mp4"))
        self.assertTrue("AI cat" in text or "imaginary cat" in text)
        self.assertIn("#AIGenerated", text)

if __name__ == "__main__":
    unittest.main()
