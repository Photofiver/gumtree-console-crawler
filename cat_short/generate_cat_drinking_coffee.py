#!/usr/bin/env python3
"""Create an original 5-second 9:16 AI-motion video: a silent cat drinks coffee.

Isolated from Stock-finder, existing Google AI scripts, and TikTok credentials.
A validated real MP4 is required: no still image or slideshow fallback.
The final MP4 intentionally has NO AUDIO STREAM.
"""
import json
import shutil
import subprocess
import traceback
from pathlib import Path

from gradio_client import Client

OUT = Path("social_videos/ai-cat-sipping-coffee-silent.mp4")
REPORT = Path("cat_short/coffee-cat-report.json")
PROMPT = (
    "One continuous five-second vertical 9:16 live-action movie with natural realistic movement, "
    "photorealistic cute orange domestic ginger tabby CAT in a cozy small cafe, "
    "large expressive amber eyes, wet pink nose, individual realistic fur strands, "
    "fluffy tail gently moving, natural cat proportions with slightly anthropomorphic front paws. "
    "The cat is seated at a tiny wooden table with a small white ceramic espresso cup "
    "containing coffee, warm morning sun through a window, cinematic shallow depth of field. "
    "The cat carefully picks up the handle of the little coffee cup with its furry front paw, "
    "raises the cup to its mouth, clearly takes a sip of the coffee, "
    "lowers the cup back onto its saucer, licks its lips once and blinks at the camera. "
    "Clearly show the drinking action in one unbroken moving shot with camera tracking, "
    "natural fluid real motion and absolutely clear cause-and-effect movement of paws, cup and head. "
    "A REAL moving video, not a still picture, not a slideshow, not cartoons, not animation-style CGI. "
    "No person, no talking, no speech, no narration, no captions, no subtitles, no text, "
    "no voice-over, no music, no visible watermark. Silent coffee moment."
)
def save(d):
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(d, ensure_ascii=False, indent=2)+"\n", encoding="utf8")

def check(args):
    return subprocess.run(args, check=True, timeout=120, capture_output=True, text=True)

result={"source":"Lightricks/LTX-2.5 HF public Gradio Space","success":False,
    "original_ai_motion":False,"silent_no_audio":False,
    "output":str(OUT),"prompt":PROMPT}
save(result)
try:
    client=Client("Lightricks/LTX-2.5",httpx_kwargs={"timeout":40.0})
    print("Requesting truly original 5-second AI moving video: a cat sipping coffee; no speech",flush=True)
    res=client.predict(PROMPT,None,512,896,5.0,914257,"conv",
        False,False,False,api_name="/run")
    video=res[0] if isinstance(res,(list,tuple)) else res
    if isinstance(video,dict):
        video=video.get("path") or video.get("video") or video.get("name")
    src=Path(video)
    if not src.is_file() or src.stat().st_size<100_000:
        raise RuntimeError("Gradio returned no generated moving MP4")
    OUT.parent.mkdir(parents=True,exist_ok=True)
    # Explicitly strip *all* audio regardless of whether the model adds any.
    check(["ffmpeg","-hide_banner","-y","-i",str(src),"-map","0:v:0",
        "-an","-c:v","libx264","-preset","fast","-crf","22","-pix_fmt","yuv420p",
        "-movflags","+faststart",str(OUT)])
    probe=json.loads(check(["ffprobe","-v","error","-show_entries",
        "stream=codec_type,width,height,r_frame_rate,nb_frames:format=duration,size",
        "-of","json",str(OUT)]).stdout)
    streams=probe.get("streams",[])
    if len(streams)!=1 or streams[0].get("codec_type")!="video":
        raise RuntimeError("Final clip contains an unexpected stream; expected silent video only")
    stream=streams[0]
    duration=float(probe.get("format",{}).get("duration",0))
    width=int(stream.get("width",0))
    height=int(stream.get("height",0))
    if width>=height or duration<3 or duration>7 or OUT.stat().st_size<100_000:
        raise RuntimeError("Invalid MP4: not short portrait moving-video output")
    # Detect a common false result: unchanged frame repeated throughout.
    changes=check(["ffmpeg","-v","info","-i",str(OUT),"-vf",
        "select='gt(scene,0.001)',showinfo","-an","-f","null","-"])
    changed_frames=changes.stderr.count("showinfo")-1
    result.update({"success":True,"original_ai_motion":True,"silent_no_audio":True,
       "duration_s":duration,"width":width,"height":height,
       "bytes":OUT.stat().st_size,"changed_frames_approx":max(0,changed_frames)})
    if changed_frames<=0:
        raise RuntimeError("Movement test inconclusive: no detectable frame changes")
    save(result)
    print("SUCCESS: original 9:16 moving cat coffee MP4, with no speech and no audio stream",flush=True)
except Exception as error:
    result.update({"success":False,"error":str(error),"traceback":traceback.format_exc()[-2000:]})
    save(result)
    OUT.unlink(missing_ok=True)
    print("FAILED: no video should be represented as created",str(error),flush=True)
    raise
