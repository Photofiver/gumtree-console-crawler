import os
import unittest
from unittest.mock import patch
import publish as p


class SafetyTests(unittest.TestCase):
    def creator(self):
        return dict(creator_username=p.ACCOUNT, privacy_level_options=['SELF_ONLY'],
            max_video_post_duration_sec=60, comment_disabled=False,
            duet_disabled=True, stitch_disabled=True)

    def test_missing_token_never_calls_api(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(p, 'api') as api:
            with self.assertRaisesRegex(p.Blocked, 'MISSING_TIKTOK_ACCESS_TOKEN'):
                p.run({})
            api.assert_not_called()

    def test_preflight_only_queries_creator(self):
        with patch.dict(os.environ, {'TIKTOK_ACCESS_TOKEN':'test'}, clear=True), \
             patch.object(p, 'api', return_value=self.creator()) as api, \
             patch.object(p, 'source', return_value={'sha256':'a'*64, 'duration':8}):
            report = {}
            p.run(report)
            self.assertIn('NO_UPLOAD', report['result'])
            self.assertEqual([c.args[0] for c in api.call_args_list], ['creator_info/query/'])

    def test_wrong_account_stops_before_media_or_publish(self):
        with patch.dict(os.environ, {'TIKTOK_ACCESS_TOKEN':'test'}, clear=True), \
             patch.object(p, 'api', return_value={'creator_username':'other'}) as api:
            with self.assertRaisesRegex(p.Blocked, 'WRONG_TIKTOK_ACCOUNT'):
                p.run({})
            self.assertEqual(api.call_count, 1)

    def test_publish_requires_setup_and_exact_consent(self):
        for extra, expected in [({}, 'APP_APPROVAL'), ({'APP_READY':'true'}, 'EXPLICIT_APPROVAL')]:
            with self.subTest(extra=extra), patch.dict(os.environ,
                    {'TIKTOK_ACCESS_TOKEN':'test', 'MODE':'publish', **extra}, clear=True), \
                 patch.object(p, 'api', return_value=self.creator()) as api, \
                 patch.object(p, 'source', return_value={'sha256':'a'*64, 'duration':8}):
                with self.assertRaisesRegex(p.Blocked, expected):
                    p.run({})
                self.assertEqual(api.call_count, 1)

    def test_disallowed_privacy_interactions_duration(self):
        for settings, duration in [({},8), ({'privacy_level':'PUBLIC_TO_EVERYONE'},8),
                ({'privacy_level':'SELF_ONLY', 'allow_duet':True},8),
                ({'privacy_level':'SELF_ONLY'},61)]:
            with self.subTest(settings=settings, duration=duration), self.assertRaises(p.Blocked):
                p.validate_post(self.creator(), {'duration':duration}, settings, '')

    def test_caption_unicode_limit_and_ai_label(self):
        settings = {'privacy_level':'SELF_ONLY'}
        with self.assertRaisesRegex(p.Blocked, 'CAPTION_TOO_LONG'):
            p.validate_post(self.creator(), {'duration':8}, settings, '\U0001f600'*1101)
        post = p.validate_post(self.creator(), {'duration':8}, settings, 'Cat #AI')
        self.assertTrue(post['is_aigc'])
        self.assertTrue(post['disable_comment'])

    def test_path_escape_rejected(self):
        for path in ['/etc/passwd', 'social_videos/../../secret.mp4', 'tiktok_publisher/a.mp4']:
            with self.subTest(path=path), self.assertRaises(p.Blocked):
                p.source(path, 'a'*40)

    def test_rerun_cannot_create_duplicate(self):
        with patch.dict(os.environ, {'TIKTOK_ACCESS_TOKEN':'test','MODE':'publish',
                'GITHUB_RUN_ATTEMPT':'2'}, clear=True), \
             patch.object(p, 'api', return_value=self.creator()) as api, \
             patch.object(p, 'source', return_value={'sha256':'a'*64,'duration':8}):
            with self.assertRaisesRegex(p.Blocked, 'DO_NOT_RERUN'):
                p.run({})
            self.assertEqual(api.call_count, 1)


if __name__ == '__main__':
    unittest.main()
