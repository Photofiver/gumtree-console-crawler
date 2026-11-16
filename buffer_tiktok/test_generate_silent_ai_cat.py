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

    def test_ltx_fallback_clamps_out_of_range_seed(self):
        with tempfile.TemporaryDirectory() as td:
            sample = Path(td) / "fresh-cat.mp4"
            sample.write_bytes(b"video-data" * 4000)
            test_case = self

            class FakeClient:
                def __init__(self, model):
                    self.model = model

                def predict(self, *args, **kwargs):
                    if self.model.startswith("mastaP/"):
                        raise RuntimeError("anonymous GPU quota exhausted")
                    test_case.assertGreaterEqual(args[5], 0)
                    test_case.assertLessEqual(args[5], 2147483647)
                    return str(sample)

            with patch("gradio_client.Client", side_effect=FakeClient):
                result, model = gen.obtain_generated_video(
                    "original AI cat clip", 4019789778)
                self.assertEqual(result, sample)
                self.assertEqual(model, "Lightricks/LTX-2.5")

    def test_exactly_100_distinct_friendly_human_activities(self):
        self.assertEqual(len(gen.SCENES), 100)
        self.assertEqual(len(set(x[0] for x in gen.SCENES)), 100)
        self.assertEqual(len(gen.CAT_LOOKS), 16)
        self.assertEqual(len(gen.ENVIRONMENT_STYLES), 17)

    def test_365_days_have_distinct_full_visual_concepts(self):
        # 15 slots/day x 365 days = 5,475 prompts.
        # A complete (action, cat appearance, environment) combination cannot repeat.
        first = dt.date(2026, 11, 17)
        seen = set()
        for days in range(365):
            stamp = (first + dt.timedelta(days=days)).strftime("%Y%m%d")
            scenes_per_day = set()
            looks_per_day = set()
            for slot in range(15):
                activity = gen.choose_scene(stamp, slot)[0]
                look = gen.choose_look(stamp, slot)
                room = gen.choose_environment(stamp, slot)
                concept = (activity, look, room)
                self.assertNotIn(concept, seen)
                seen.add(concept)
                scenes_per_day.add(activity)
                looks_per_day.add(look)
            self.assertEqual(len(scenes_per_day), 15)
            self.assertEqual(len(looks_per_day), 15)
        self.assertEqual(len(seen), 365 * 15)

    def test_prompt_uses_new_coat_color_and_background_without_sound_or_text(self):
        p = gen.video_prompt("carefully folds a towel",
                             "fluffy solid black domestic longhair with amber eyes",
                             "soft dusty-rose and warm walnut color palette")
        self.assertIn("solid black", p)
        self.assertIn("dusty-rose", p)
        self.assertNotIn("living ginger British Shorthair CAT", p)
        self.assertIn("COMPLETELY SILENT", p)
        self.assertIn("NO text", p)

    def test_no_second_generated_post_for_same_existing_daily_slot(self):
        with tempfile.TemporaryDirectory() as folder:
            previous = gen.DEST
            gen.DEST = Path(folder)
            try:
                existing = Path(folder) / "new-ai-cat-20261116-s05-original-scene.mp4"
                existing.write_bytes(b"previously published video")
                with patch.object(gen, "utc_slot", return_value=("20261116", 5)), \
                     patch.object(gen, "obtain_generated_video") as call:
                    gen.generate()
                    call.assert_not_called()
            finally:
                gen.DEST = previous

if __name__ == "__main__":
    unittest.main()
