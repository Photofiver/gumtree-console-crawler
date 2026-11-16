import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from buffer_tiktok import generate_silent_ai_cat as gen

class SilentCatScheduleAndMediaTests(unittest.TestCase):
    def test_15_uniform_slots(self):
        self.assertEqual(gen.SLOT_MINUTES, 96)
        vals=[i*96 for i in range(15)]
        self.assertEqual(vals[-1], 1344)
        self.assertEqual([b-a for a,b in zip(vals,vals[1:])],[96]*14)
        self.assertEqual(1440-vals[-1], 96)

    def test_slot_by_utc_time(self):
        day="20261116"
        for slot in range(15):
            minute=slot*96
            clock=dt.datetime(2026,11,16,minute//60,minute%60,tzinfo=dt.timezone.utc)
            self.assertEqual(gen.utc_slot(clock),(day,slot))

    def test_all_scenes_friendly_english(self):
        self.assertGreaterEqual(len(gen.SCENES),25)
        for slug,action,caption,tags in gen.SCENES:
            self.assertTrue(slug and action and caption)
            self.assertIn("#AICat",tags)
            self.assertEqual(len((slug,action,caption,tags)),4)
            self.assertTrue(all(ord(ch)<128 for ch in slug))

    def test_no_text_or_audio_in_prompt(self):
        p=gen.video_prompt("folds a towel")
        self.assertIn("NO text",p)
        self.assertIn("COMPLETELY SILENT",p)
        self.assertIn("NO cartoon",p)
        self.assertIn("photorealistic",p)

    def test_distinct_filename_per_daily_slot(self):
        filenames={str(gen.output_paths("20261116",s,"test")[0]) for s in range(15)}
        self.assertEqual(len(filenames),15)
        self.assertFalse(any(".." in n for n in filenames))

    def test_ffprobe_rejects_audio(self):
        sample={"streams":[
            {"codec_type":"video","width":720,"height":1280,
             "codec_name":"h264","avg_frame_rate":"25/1"},
            {"codec_type":"audio","codec_name":"aac"}],
            "format":{"duration":"3.2"}}
        with tempfile.TemporaryDirectory() as td:
            f=Path(td)/"video.mp4"
            f.write_bytes(b"0"*50000)
            class Response:
                stdout=json.dumps(sample)
            with patch.object(gen,"run",return_value=Response()):
                with self.assertRaisesRegex(ValueError,"NO AUDIO"):
                    gen.validate_video(f)

    def test_ffprobe_accepts_silent_h264(self):
        sample={"streams":[
            {"codec_type":"video","width":720,"height":1280,
             "codec_name":"h264","avg_frame_rate":"25/1"}],
            "format":{"duration":"3.2"}}
        with tempfile.TemporaryDirectory() as td:
            f=Path(td)/"video.mp4"
            f.write_bytes(b"0"*50000)
            class Response:
                stdout=json.dumps(sample)
            with patch.object(gen,"run",return_value=Response()):
                details=gen.validate_video(f)
                self.assertEqual(details["audio_streams"],0)
                self.assertEqual(details["fps"],25)

    def test_model_outputs_are_never_reused_on_provider_error(self):
        with patch("gradio_client.Client",side_effect=RuntimeError("quota exhausted")):
            with self.assertRaisesRegex(RuntimeError,"No free AI video provider"):
                gen.obtain_generated_video("cat story",123)

if __name__ == "__main__":
    unittest.main()
