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
    ("ironing-shirt", "carefully smooths a doll-size shirt with an unplugged toy iron and hangs it neatly", "The tiny laundry expert is ironing out life's problems.", "#AICat #LaundryDay #CuteCats"),
    ("pouring-cereal", "pours cereal from a small blank box into a bowl, then gently picks up a spoon", "Breakfast is officially a paw-fessional operation.", "#AICat #BreakfastTime #FunnyCats"),
    ("packing-lunch", "packs a tiny sandwich and apple into a small plain lunchbox", "Lunch packed. Productivity optional.", "#AICat #LunchPrep #CatTok"),
    ("stacking-cups", "carefully stacks colorful empty paper cups into a very tall tower", "Engineering degree: pending. Confidence: unlimited.", "#AICat #CatEngineering #FunnyCats"),
    ("organizing-socks", "sorts several tiny colorful clean socks into matching pairs", "The sock detective has finally cracked the case.", "#AICat #LaundryDay #FunnyCats"),
    ("making-paper-plane", "folds a clean unmarked sheet of paper into a little airplane", "First-class travel, economy-size aircraft.", "#AICat #PaperCrafts #CuteCats"),
    ("folding-paper-boat", "folds a little blue origami boat out of plain paper", "Captain Whiskers is preparing to sail.", "#AICat #Origami #CatTok"),
    ("potting-succulent", "gently places a small succulent into a plain ceramic plant pot", "This gardener has extremely good paws for plants.", "#AICat #PlantTok #CuteCats"),
    ("polishing-glasses", "carefully wipes a pair of small spectacles with a soft cloth", "The professor is ready for another important nap.", "#AICat #ProfessorCat #FunnyCats"),
    ("checking-watch", "peeks at a blank-faced toy wristwatch, then looks dramatically surprised", "Is it snack o'clock yet? Asking for a friend.", "#AICat #SnackTime #FunnyCats"),
    ("building-cardboard-house", "folds up a small plain cardboard box into a cozy miniature house", "Property developer. Budget: one cardboard box.", "#AICat #CardboardHouse #CatTok"),
    ("drawing-abstract-art", "makes joyful colorful abstract squiggles on plain art paper with a crayon, no letters or numbers", "A little modern art from a very serious artist.", "#AICat #ArtTok #CuteCats"),
    ("making-fruit-salad", "carefully arranges precut strawberry and banana pieces in a small bowl", "Today's five-star menu is extremely fruity.", "#AICat #FruitSalad #FunnyCats"),
    ("placing-bookmarks", "slides a colorful blank bookmark between the pages of an open picture book", "Bookmark placed. Time for an intellectual nap.", "#AICat #BookTok #CozyCats"),
    ("watering-window-flowers", "gently waters colorful flowers in a window box with a tiny watering can", "The neighborhood flower inspector is on duty.", "#AICat #FlowerTok #CatLife"),
    ("wiping-window", "cleans a little section of a window with a soft microfiber cloth", "Window cleaning: now available in paws-size.", "#AICat #CleaningDay #FunnyCats"),
    ("sorting-crayons", "arranges wax crayons by their colors into a tidy rainbow", "Color coordination is this cat's superpower.", "#AICat #RainbowArt #CuteCats"),
    ("arranging-cushions", "perfectly lines up three colorful cushions on a sofa and steps back to admire them", "Interior design by a surprisingly picky cat.", "#AICat #InteriorDesign #CatTok"),
    ("dusting-bookshelf", "carefully dusts a low bookshelf with a fluffy little duster", "Someone takes spring cleaning very seriously.", "#AICat #SpringCleaning #FunnyCats"),
    ("painting-wooden-fence", "uses a tiny soft paintbrush to paint a clean decorative wooden fence panel", "That fence has never looked so important.", "#AICat #DIYCat #FunnyCats"),
    ("practicing-tai-chi", "slowly performs a gentle tai chi pose on a small mat", "Inner peace, outer fluff.", "#AICat #MindfulCat #CuteCats"),
    ("photographing-flowers", "holds a small unbranded toy camera and takes pictures of a bunch of flowers", "The photographer requests payment in snacks.", "#AICat #CatPhotographer #FunnyCats"),
    ("packing-suitcase", "carefully packs a folded colorful scarf into a tiny rolling suitcase", "The travel plans are ambitious. The suitcase is not.", "#AICat #TravelCat #FunnyCats"),
    ("rolling-suitcase", "proudly pulls a miniature wheeled suitcase down a tidy hallway", "Going on vacation. Back before dinner.", "#AICat #VacationMode #CatTok"),
    ("reading-blank-newspaper", "carefully unfolds a blank newsprint-style sheet and peers over the top", "Breaking news: the treat supply is running low.", "#AICat #MorningNews #FunnyCats"),
    ("whisking-cake-batter", "gently stirs cake batter in a bowl with a small wooden whisk", "The pastry department has hired a new whisker.", "#AICat #BakingCat #CatTok"),
    ("spreading-jam", "carefully spreads strawberry jam onto a piece of toast using a rounded butter spreader", "Breakfast is toast-ally under control.", "#AICat #BreakfastCat #FunnyCats"),
    ("stirring-hot-chocolate", "gently stirs a cooled cup of pretend hot chocolate with a tiny spoon", "The hot chocolate committee has reached a decision.", "#AICat #CozyTime #CuteCats"),
    ("planting-seedlings", "carefully plants a little leafy seedling in a pot of soft soil", "Tiny plant. Big gardener energy.", "#AICat #Gardening #CatTok"),
    ("sweeping-patio", "sweeps a few dry leaves on a quiet patio with a miniature broom", "The patio maintenance team works for treats.", "#AICat #GardenLife #FunnyCats"),
    ("mopping-floor", "slowly pushes a miniature clean damp mop over a tiled floor", "A surprisingly dedicated member of the cleaning crew.", "#AICat #CleanWithMe #FunnyCats"),
    ("practicing-ballet", "does an elegant little ballet pose beside a wooden dance barre", "The tiniest ballerina has entered the stage.", "#AICat #BalletCat #CuteCats"),
    ("doing-gentle-exercise", "performs one slow easy stretch with paws on a soft exercise mat", "Personal trainer available. Payment by treats only.", "#AICat #FitCat #CatTok"),
    ("lifting-toy-weights", "lifts two extremely lightweight foam toy dumbbells in a playful workout", "Gym membership: one nap and two snacks.", "#AICat #GymCat #FunnyCats"),
    ("polishing-trophy", "gently buffs a small blank golden trophy with a soft cloth", "Award winner. Category: excellent napping.", "#AICat #AwardWinning #FunnyCats"),
    ("planting-tulip", "plants one colorful tulip into a little flower pot", "The tulip has a new very fluffy landlord.", "#AICat #FlowerGarden #CuteCats"),
    ("sorting-buttons", "sorts several oversized colorful craft buttons into neat color groups", "Spreadsheet skills, but make them adorable.", "#AICat #OrganizedCat #FunnyCats"),
    ("sewing-fabric-patch", "carefully arranges a soft fabric patch onto a little cloth using a safe plastic sewing tool", "Fashion designer with impeccable whiskers.", "#AICat #CraftTok #CatLife"),
    ("knitting-hat", "works on a tiny colorful knitted hat with extra chunky soft needles", "Winter fashion is looking pawsome.", "#AICat #KnittingCat #CozyCats"),
    ("painting-plant-pot", "paints cheerful abstract color stripes on a plain flower pot", "The pottery collection just got a makeover.", "#AICat #DIYDecor #ArtCat"),
    ("decorating-blank-card", "decorates a blank greeting card with colorful shapes and no written words", "Someone is sending handmade happiness today.", "#AICat #CraftTime #CuteCats"),
    ("stamping-shapes", "presses a round foam stamp into washable paint and makes colorful shapes on paper", "Print shop open. No receipts, only purrs.", "#AICat #CreativeCat #ArtTok"),
    ("setting-picnic-blanket", "carefully unfolds a small gingham picnic blanket on a grassy garden lawn", "The picnic organiser has arrived early.", "#AICat #PicnicTime #CuteCats"),
    ("serving-cupcakes", "carefully arranges a few miniature cupcakes on a plain serving tray", "The dessert waiter has excellent taste.", "#AICat #CupcakeTime #FunnyCats"),
    ("balancing-tray", "slowly walks with a small empty tray balanced between its front paws", "Service with a smile and four little paws.", "#AICat #WaiterCat #FunnyCats"),
    ("spinning-globe", "gently spins a colorful unlabeled toy globe and points one paw toward it", "World travel begins right after lunch.", "#AICat #TravelDreams #CatTok"),
    ("magic-flower-trick", "pulls a paper flower from a small empty top hat during a playful magic trick", "A round of applause for the great Meowdini.", "#AICat #MagicCat #FunnyCats"),
    ("playing-chess", "carefully moves one oversized chess piece across a blank-sided chessboard", "Grandmaster of the snack break.", "#AICat #ChessCat #CuteCats"),
    ("stacking-wooden-blocks", "carefully builds a wobbly tower of colorful wooden blocks", "The structural engineer approves this tower.", "#AICat #BuildingBlocks #FunnyCats"),
    ("trying-rain-boots", "tries on a pair of comically oversized colorful toy rain boots", "Ready for puddles. Not ready for the forecast.", "#AICat #RainyDay #CuteCats"),
    ("opening-tiny-umbrella", "opens a little decorative umbrella while standing on a cozy indoor rug", "Prepared for any weather. Even indoors.", "#AICat #UmbrellaCat #FunnyCats"),
    ("sculpting-clay-vase", "shapes a small soft lump of modeling clay into a tiny vase", "An artist at work. Please admire the vase.", "#AICat #ClayArt #CuteCats"),
    ("folding-origami-star", "carefully folds a colorful paper star from a plain square sheet", "This star is officially the cutest in the galaxy.", "#AICat #OrigamiArt #CatTok"),
    ("tying-ribbon", "gently ties a colorful ribbon around a plain flower pot", "A simple ribbon. A major decorating achievement.", "#AICat #CraftyCat #CuteCats"),
    ("sorting-recycling", "sorts clean paper and plastic containers into two plain colored bins", "The recycling manager works for extra treats.", "#AICat #EcoCat #FunnyCats"),
    ("pushing-shopping-trolley", "gently pushes a miniature empty toy shopping trolley past an indoor produce display", "Grocery list: snacks, snacks and more snacks.", "#AICat #ShoppingCat #CatTok"),
    ("arranging-fruit-stand", "places shiny toy fruit into neat rows on a tiny market stall", "Fresh produce and the friendliest shopkeeper.", "#AICat #MarketCat #CuteCats"),
    ("sorting-wooden-coins", "carefully arranges oversized plain wooden pretend coins into tiny stacks", "The accountant says the snack budget is approved.", "#AICat #MoneyCat #FunnyCats"),
    ("playing-xylophone", "gently taps oversized colorful keys of a toy xylophone with a soft foam mallet", "A silent concert for the world's fluffiest audience.", "#AICat #MusicCat #CuteCats"),
    ("washing-mirror", "gently wipes a small mirror with a soft cloth and admires its reflection", "Mirror, mirror, who's the fluffiest of all?", "#AICat #MirrorCat #FunnyCats"),
    ("hanging-laundry", "clips two tiny clean socks onto a low indoor miniature clothesline", "The laundry service is now open for business.", "#AICat #LaundryCat #CuteCats"),
    ("watering-herbs", "gently waters two pots of fresh kitchen herbs on a window ledge", "A budding chef and now a herb gardener.", "#AICat #HerbGarden #CatTok"),
    ("cleaning-toy-car", "carefully polishes a tiny parked toy car with a soft cloth", "Car wash open. Five-star paw service.", "#AICat #CarWash #FunnyCats"),
    ("teaching-teddy-bear", "sits beside a teddy bear and points a paw toward a completely blank open book", "Today's class has one student and zero homework.", "#AICat #TeacherCat #CuteCats"),
    ("packing-backpack", "neatly puts a soft scarf into a miniature backpack and closes it", "Packed and ready for a very short adventure.", "#AICat #AdventureCat #CatTok"),
    ("sorting-boardgames", "carefully arranges colorful blank board-game pieces inside a small box", "Game night organiser takes the rules very seriously.", "#AICat #GameNight #FunnyCats"),
    ("folding-shopping-bags", "neatly folds colorful reusable shopping bags on a kitchen table", "The bag folding championship has a new winner.", "#AICat #OrganizedCat #CuteCats"),
    ("checking-recipe-book", "turns a page of an entirely blank recipe book and points toward a bowl of flour", "Chef's secret ingredient? More treats.", "#AICat #CatChef #FunnyCats"),
    ("making-sushi-roll", "carefully rolls pretend felt sushi pieces together on a bamboo mat", "The tiny sushi chef has prepared today's special.", "#AICat #SushiCat #CuteCats"),
    ("fluffing-pillow", "pats a big soft pillow until it is perfectly fluffy and sits down proudly", "An elite-level expert in pillow comfort.", "#AICat #CozyCat #CatTok"),
]

# Appearance, backgrounds, and activity are three independent cycles.
# Their combined cycle is lcm(100, 16, 17) = 6800 posting slots,
# which exceeds 15 * 365 = 5475 possible videos in a year.
CAT_LOOKS = [
    "ginger tabby British Shorthair with copper eyes",
    "fluffy solid black domestic longhair with amber eyes",
    "black-and-white tuxedo domestic shorthair with green eyes",
    "silver tabby American Shorthair with dark stripes",
    "cream-colored British Shorthair with honey-colored eyes",
    "white Persian with soft long fur and blue eyes",
    "blue-gray Russian Blue with emerald eyes",
    "calico domestic shorthair with black, ginger and white patches",
    "tortoiseshell domestic shorthair with mottled black and orange fur",
    "chocolate-brown Burmese with golden eyes",
    "seal-point Siamese with deep blue eyes and dark ears",
    "fluffy seal-bicolor Ragdoll with bright blue eyes",
    "golden spotted Bengal with lively green eyes",
    "brown tabby Maine Coon with a fluffy ruff and tufted ears",
    "ginger-and-white domestic shorthair with white socks",
    "dilute calico domestic shorthair with gray, cream and white patches"
]
ENVIRONMENT_STYLES = [
    "soft sage-green and oak home decor",
    "warm honey-colored timber details",
    "clean Scandinavian whites and beige textiles",
    "pale blue and white coastal interior details",
    "sunny pale-yellow and cream decor",
    "soft lavender and natural linen details",
    "warm terracotta and earthy ceramics",
    "calm pastel mint-green surroundings",
    "subtle vintage cottage furnishing details",
    "minimalist pale birchwood and white palette",
    "natural rattan and soft cream textiles",
    "muted teal and brushed brass details",
    "welcoming peach and ivory color accents",
    "soft dusty-rose and warm walnut color palette",
    "fresh seafoam-green and stone-gray palette",
    "subtle navy-blue and white decorative details",
    "warm caramel and muted beige details"
]
CAPTION_ENDINGS = (
    "What should this little helper try next?",
    "Would you hire this tiny professional?",
    "How would your cat handle this job?",
    "Give this little worker a rating out of ten!",
    "What should we call this very serious expert?",
    "Tag someone who needs a laugh today!"
)

def slot_number(date_stamp: str, slot: int) -> int:
    daynum = dt.date.fromisoformat(
        f"{date_stamp[:4]}-{date_stamp[4:6]}-{date_stamp[6:]}"
    ).toordinal()
    if not 0 <= slot < 15:
        raise ValueError("Invalid daily slot")
    return daynum * 15 + slot

def choose_look(date_stamp: str, slot: int):
    serial = slot_number(date_stamp, slot)
    return CAT_LOOKS[serial % len(CAT_LOOKS)]

def choose_environment(date_stamp: str, slot: int):
    serial = slot_number(date_stamp, slot)
    return ENVIRONMENT_STYLES[serial % len(ENVIRONMENT_STYLES)]


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
    return SCENES[slot_number(date_stamp, slot) % len(SCENES)]

def output_paths(date_stamp: str, slot: int, slug: str):
    stem = f"new-ai-cat-{date_stamp}-s{slot:02d}-{slug}"
    return DEST / (stem + ".mp4"), DEST / (stem + ".json")

def video_prompt(action: str, look: str = CAT_LOOKS[0],
                 environment: str = ENVIRONMENT_STYLES[0]):
    return (
        "Create an entirely original AI-generated moving video of ONE highly "
        "photorealistic living " + look + " CAT, with accurate real "
        "feline eyes, fur, whiskers and paws. The cat behaves like a cheerful little "
        "human in a delightfully absurd but safe way: it " + action + ". "
        "The cat's action and moving paws are clearly visible, with physical "
        "movement throughout the shot. ONE stable continuously moving cinematic "
        "shot, detailed realistic environment naturally suited to the action, "
        "styled with " + environment + ", natural-looking lighting, "
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
    # LTX API accepts a signed 31-bit seed, while our deterministic hash may be 32-bit.
    for model in ("mastaP/wan22-remix-sfw-t2v", "Lightricks/LTX-2.5"):
        try:
            print("AI_VIDEO_ATTEMPT", model, flush=True)
            client = Client(model)
            if model == "mastaP/wan22-remix-sfw-t2v":
                result = client.predict(prompt, api_name="/generate_video")
            else:
                result = client.predict(
                    prompt, None, 512, 896, 5.0, seed & 0x7fffffff,
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
    # Never post a second film for a slot after a code or appearance update.
    if list(DEST.glob(f"new-ai-cat-{date_stamp}-s{slot:02d}-*.mp4")):
        print("EXISTING_AI_SLOT_VIDEO_NO_REGENERATION", date_stamp, slot, flush=True)
        return
    slug, action, hook, tags = choose_scene(date_stamp, slot)
    look = choose_look(date_stamp, slot)
    environment = choose_environment(date_stamp, slot)
    output, sidecar = output_paths(date_stamp, slot, slug)
    if output.exists():
        print("EXISTING_AI_SLOT_VIDEO_NO_REGENERATION", output, flush=True)
        return
    prompt = video_prompt(action, look, environment)
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
            "cat_appearance": look,
            "environment_style": environment,
            "content_variety_cycle_slots": 6800,
            "caption": (hook.strip() + " " +
                        CAPTION_ENDINGS[slot_number(date_stamp, slot) % len(CAPTION_ENDINGS)] +
                        " " + tags + " #AIGenerated").strip(),
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
