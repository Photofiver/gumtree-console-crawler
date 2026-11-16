#!/usr/bin/env python3
"""Generate a NEW original, silent, caption-free moving AI cat per 96-minute TikTok slot.

The AI must create video from a prompt; no stock footage, slideshow, subtitles,
music, speech, on-screen text, branding, or externally supplied images.
User-facing ENGLISH descriptions are separate Buffer/TikTok post captions.
No output is published unless it passes objective video/audio checks.
"""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT / "social_videos"
SLOT_MINUTES = 96

# All actions are lighthearted, safe and friendly; none involve a person,
# impersonation, frightening animals, dangerous stunts or politics.
# Slugs, shot directions and captions stay matched in the video metadata.
SCENES = [
    ("baking-pancakes", "carefully flips one small pancake in a frying pan with a tiny spatula, then looks pleased with itself", "The chef has four paws and very high breakfast standards. Who wants pancakes?", "#AICat #CatChef #FunnyCats"),
    ("folding-laundry", "very carefully folds a tiny clean towel on a table, then admires the neat stack", "Laundry day has a new supervisor. Would you hire this little helper?", "#AICat #LaundryDay #FunnyCats"),
    ("watering-plants", "waters a houseplant with a small watering can, then checks a leaf with great seriousness", "The garden department's newest employee takes this job VERY seriously. ", "#AICat #PlantLover #CuteCats"),
    ("knitting-scarf", "knits a bright blue scarf with chunky knitting needles, pauses to inspect the stitches", "Grandma's knitting club just got an unexpected new member. ", "#AICat #CozyVibes #CatTok"),
    ("brushing-teeth", "holds a little toothbrush and gently brushes its own tiny teeth in front of a bathroom mirror", "When the dentist says brush twice a day and you take it personally. ", "#AICat #MorningRoutine #FunnyCats"),
    ("doing-yoga", "does a gentle yoga stretch on a miniature yoga mat, then settles into a proud pose", "The yoga instructor accepts payment in treats. ", "#AICat #CatYoga #Wellness"),
    ("painting-sunset", "paints a colorful abstract sunset with a small paintbrush on a blank canvas, then admires its work", "The art critic is also the artist. Five stars from the paws committee. ", "#AICat #CatArtist #ArtTok"),
    ("vacuuming-rug", "carefully pushes a tiny lightweight vacuum cleaner across a clean living-room rug", "Someone finally volunteered to do the vacuuming. ", "#AICat #CleaningDay #FunnyCats"),
    ("making-tea", "gently pours from a tiny teapot into a cup at a quiet afternoon tea table", "Tea time is serious business for this little host. Milk or no milk?", "#AICat #TeaTime #BritishHumour"),
    ("gardening", "uses a miniature garden trowel to pat fresh soil around a little potted flower", "The new gardener has a very paws-on approach. ", "#AICat #Gardening #CuteCats"),
    ("typing-on-laptop", "pretends to type rapidly on a closed-screen laptop keyboard and then gives the camera a businesslike look", "Very busy. Absolutely no idea what the deadline is. ", "#AICat #OfficeCat #WorkHumor"),
    ("playing-piano", "plays a few piano keys with its two front paws, proudly pausing after its performance", "The tiniest piano recital in town. Standing ovation? ", "#AICat #PianoCat #FunnyCats"),
    ("making-sandwich", "carefully stacks slices of bread and lettuce into a tiny sandwich on a plate", "Lunch is officially in expert paws. Rate this sandwich from 1 to 10.", "#AICat #CatChef #LunchTime"),
    ("making-bed", "pulls a small blanket neatly across a tiny bed and carefully pats the pillow", "The bed-making champion has arrived. ", "#AICat #CozyCat #CuteCats"),
    ("doing-puzzles", "sorts colorful wooden jigsaw pieces on a table and gently fits two pieces together", "A true puzzle genius. We think. ", "#AICat #PuzzleTime #SmartCat"),
    ("making-coffee", "carefully lifts a tiny espresso cup, takes a pretend sip, then gives a sleepy blink", "First coffee, then world domination. Or a nap. ", "#AICat #CoffeeCat #MorningMood"),
    ("wrapping-gifts", "wraps a little present in plain colorful paper and ties an oversized ribbon with its paws", "This present was wrapped with love. And a few paw prints. ", "#AICat #GiftWrapping #CuteCats"),
    ("reading-book", "turns one page of a completely blank picture book with a paw while sitting in a comfy armchair", "Book club meets every day. Everyone falls asleep by chapter two. ", "#AICat #BookTok #CozyVibes"),
    ("rolling-dough", "rolls out cookie dough with a tiny rolling pin on a clean kitchen counter", "Today's baking assistant is kneading a promotion. ", "#AICat #BakingCat #FunnyCats"),
    ("washing-dishes", "gently scrubs a small clean plate using a sponge beside a kitchen sink, without splashing", "Can we all agree this cat deserves a raise? ", "#AICat #KitchenHelper #CatTok"),
    ("taking-selfie", "holds up a tiny camera to take a selfie, then poses with an adorably serious expression", "The influencer has arrived. Zero sponsored treats so far. ", "#AICat #CatInfluencer #FunnyCats"),
    ("building-pillow-fort", "stacks a few colorful couch cushions into a miniature pillow fort and crawls inside", "The architect has approved the new living room. ", "#AICat #PillowFort #CatTok"),
    ("making-flower-bouquet", "carefully arranges a little bunch of colorful artificial flowers inside a vase", "Your flowers have been arranged by a professional. Allegedly. ", "#AICat #FlowerArranging #CuteCats"),
    ("checking-mail", "opens an empty unmarked envelope and peers inside with exaggerated anticipation", "Checking the mail for a letter from the treat company. ", "#AICat #CatLife #FunnyCats"),
    ("organizing-bookshelf", "straightens several blank-spined colorful books on a low shelf, then steps back proudly", "The library is now under new management. ", "#AICat #BookLover #CuteCats"),
    ("making-smoothie", "places pieces of banana in an unplugged clear blender jug and admires the ingredients", "The smoothie bar's newest employee is learning fast. ", "#AICat #KitchenCat #FunnyCats"),
    ("polishing-shoes", "carefully buffs one little clean shoe with a soft cloth on a wooden table", "The attention to detail is impeccable. The shoe is still tiny. ", "#AICat #FunnyCats #CatTok"),
    ("setting-dinner-table", "neatly sets down a little plate and folded napkin on a table, ready for dinner", "Dinner is served. The chef demands treats as a tip. ", "#AICat #DinnerTime #CuteCats"),
    ("decorating-cupcake", "carefully decorates a tiny cupcake with a dab of pink icing, then admires it", "A cupcake designed by an artist with paws. ", "#AICat #CupcakeArt #BakingCat"),
    ("using-telescope", "looks through a tiny toy telescope from a balcony at the peaceful evening sky", "Searching for the planet made entirely of treats. ", "#AICat #Stargazing #FunnyCats"),
]

def utc_slot(now: Optional[dt.datetime] = None):
    now = now or dt.datetime.now(dt.timezone.utc)
    if now.tzinfo is None:
        raise ValueError("UTC-aware time required")
    now = now.astimezone(dt.timezone.utc)
    index = (now.hour * 60 + now.minute) // SLOT_MINUTES
    if not 0 <= index < 15:
        raise ValueError("Invalid slot index")
    return now.strftime("%Y%m%d"), index

def choose_scene(date_stamp: str, slot: int):
    daynum = dt.date.fromisoformat(f"{date_stamp[:4]}-{date_stamp[4:6]}-{date_stamp[6:]}").toordinal()
    return SCENES[(daynum * 15 + slot) % len(SCENES)]

def output_paths(date_stamp: str, slot: int, slug: str):
    stem = f"new-ai-cat-{date_stamp}-s{slot:02d}-{slug}"
    return DEST / (stem + ".mp4"), DEST / (stem + ".json")

def video_prompt(action: str):
    return (
        "Create an entirely original AI-generated moving video of ONE highly "
        "photorealistic living ginger British Shorthair CAT, with accurate real "
        "feline eyes, fur, whiskers and paws. The cat behaves like a cheerful little "
        "human in a delightfully absurd but safe way: it " + action + ". "
        "The cat's action and moving paws are clearly visible, with physical "
        "movement throughout the shot. ONE stable continuously moving cinematic "
        "shot, bright warm natural light, detailed realistic environment, "
        "centered subject and action so it can be cropped into a vertical 9:16 "
        "TikTok video. Wholesome, friendly, funny, charming, non-offensive, "
        "family-friendly, no human actors, no cruelty, no distress, no dangerous "
        "behavior, no politics, no brand names. COMPLETELY SILENT: absolutely "
        "no soundtrack, music, voice, speech or sound effects. "
        "Absolutely NO text, letters, numbers, subtitles, captions, speech bubbles, "
        "signs, logo, watermark, interface or written words anywhere in the frames. "
        "NO cartoon, NO anime, NO 3D stylization, NO slides, NO still images. "
        "Real lifelike physical cat motion only."
    )

def run(cmd, timeout=120):
    return subprocess.run(cmd, check=True, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True, timeout=timeout)

def take_video_from_result(result):
    thing = result[0] if isinstance(result, (tuple, list)) else result
    if isinstance(thing, dict):
        thing = thing.get("path") or thing.get("video") or thing.get("name")
    if not isinstance(thing, str) or not Path(thing).is_file():
        raise RuntimeError("AI generation produced no local playable video")
    return Path(thing)

def obtain_generated_video(prompt: str, seed: int):
    from gradio_client import Client
    failures = []
    # Previously demonstrated working public Hugging Face Spaces. They may
    # refuse requests when anonymous GPU quotas or queue capacity are used up.
    for model in ("mastaP/wan22-remix-sfw-t2v", "Lightricks/LTX-2.5"):
        try:
            print("AI_VIDEO_ATTEMPT", model, flush=True)
            client = Client(model)
            if model == "mastaP/wan22-remix-sfw-t2v":
                result = client.predict(prompt, api_name="/generate_video")
            else:
                result = client.predict(
                    prompt, None, 512, 896, 5.0, seed,
                    "conv", False, False, False, api_name="/run")
            path = take_video_from_result(result)
            if path.stat().st_size < 25000:
                raise RuntimeError("Generated video file too small")
            return path, model
        except Exception as exc:
            # Public GPU providers sometimes fail; never substitute old media.
            failures.append(f"{model}: {type(exc).__name__} {str(exc)[:160]}")
            print("AI_VIDEO_PROVIDER_FAILED", failures[-1], flush=True)
    raise RuntimeError("No free AI video provider available for this slot: " +
                       " | ".join(failures))

def validate_video(path: Path):
    probe = json.loads(run(["ffprobe", "-v", "error", "-show_streams",
                            "-show_format", "-of", "json", str(path)], timeout=35).stdout)
    streams = probe.get("streams", [])
    videos = [v for v in streams if v.get("codec_type") == "video"]
    if len(videos) != 1 or any(v.get("codec_type") == "audio" for v in streams):
        raise ValueError("Only one VIDEO stream and NO AUDIO permitted")
    stream = videos[0]
    duration = float(probe["format"]["duration"])
    width, height = int(stream["width"]), int(stream["height"])
    fps_num, fps_den = [int(x) for x in stream.get("avg_frame_rate", "0/1").split("/")]
    fps = fps_num / max(1, fps_den)
    if width != 720 or height != 1280 or stream.get("codec_name") != "h264":
        raise ValueError("Expected 720x1280 H264")
    if not 2.8 <= duration <= 8 or not 24 <= fps <= 30:
        raise ValueError("Invalid duration or framerate")
    if path.stat().st_size < 40000:
        raise ValueError("Missing image detail")
    return {"seconds": round(duration, 2), "fps": round(fps, 2),
            "width": width, "height": height, "audio_streams": 0,
            "bytes": path.stat().st_size}

def generate():
    date_stamp, slot = utc_slot()
    slug, action, hook, tags = choose_scene(date_stamp, slot)
    output, sidecar = output_paths(date_stamp, slot, slug)
    if output.exists():
        print("EXISTING_AI_SLOT_VIDEO_NO_REGENERATION", output, flush=True)
        return
    prompt = video_prompt(action)
    seed = int.from_bytes(hashlib.sha256(
        (date_stamp + str(slot)).encode()).digest()[:4], "big")
    video, model = obtain_generated_video(prompt, seed)
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        # Strip ALL model audio. Never add text/subtitles/voiceovers to the frame.
        run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
             "-i", str(video), "-map", "0:v:0",
             "-vf", "crop='min(iw,ih*9/16)':ih:(iw-ow)/2:0,scale=720:1280:flags=lanczos,fps=25",
             "-t", "6", "-an", "-c:v", "libx264", "-preset", "veryfast",
             "-crf", "22", "-pix_fmt", "yuv420p",
             "-movflags", "+faststart", str(output)], timeout=130)
        report = validate_video(output)
        details = {
            "generated_with": model,
            "original_text_to_video": True,
            "no_stock_footage": True,
            "no_added_text_or_subtitles": True,
            "no_audio_verified": True,
            "concept": action,
            "caption": (hook.strip() + " " + tags + " #AIGenerated").strip(),
            "prompt": prompt,
            "utc_day": date_stamp,
            "scheduled_slot": slot,
            "validation": report
        }
        sidecar.write_text(json.dumps(details, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
        print("NEW_SILENT_AI_CAT_SUCCESS", json.dumps({
            "video": str(output.relative_to(ROOT)), "metadata": str(sidecar.relative_to(ROOT)),
            "model": model, **report
        }), flush=True)
    except Exception:
        output.unlink(missing_ok=True)
        sidecar.unlink(missing_ok=True)
        raise

if __name__ == "__main__":
    try:
        generate()
    except Exception as exc:
        print("NEW_SILENT_AI_CAT_FAILED:", str(exc)[:500], file=sys.stderr)
        # No fake output: next run may work when free GPU quota returns.
        sys.exit(1)
