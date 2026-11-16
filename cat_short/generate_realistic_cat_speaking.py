#!/usr/bin/env python3
"""Realistic-cat lip-synced-dialogue feasibility test using one-pass LTX-2.5
native audio + video. No separate voiceover, no stock footage, no slideshow.
Validate audio presence, duration and transcribe Polish audio as a QA check.
"""
import json, re, traceback, subprocess, difflib, shutil
from pathlib import Path

from gradio_client import Client

OUT=Path("realistic-cat-speaking-native-ai.mp4")
REPORT=Path("realistic-cat-speaking-report.json")
DIALOGUE="Jest poniedziałek. A ja już chcę obiad."
report={
 "approach":"One-pass native text-to-audio-video to avoid adding an out-of-sync voice track",
 "requested_dialogue":DIALOGUE,
 "requested_language":"Polish",
 "visual_style":"photorealistic living domestic cat with real fur and natural feline anatomy, not 3D cartoon",
 "model":"Lightricks/LTX-2.5",
 "success":False,"speech_verified":False
}
def save():
 REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf8")
def run(args,**kwargs):
 return subprocess.run(args,check=True,timeout=kwargs.pop("timeout",90),**kwargs)
save()
try:
 print("GENERATING VIDEO + VOICE SIMULTANEOUSLY",flush=True)
 prompt=(
  "An ultra-photorealistic close-up film shot of a REAL-LIFE domestic ginger tabby cat "
  "with individual orange fur strands, detailed white whiskers, wet pink nose, "
  "true-to-life green feline eyes and anatomically authentic cat face and paws. "
  "The cat is naturally sitting behind an office desk with a dark charcoal necktie "
  "loosely hanging over its chest. A keyboard is in front of its furry paws, "
  "an unopened lunchbox rests on the desk. Documentary-grade 4K natural realistic "
  "photography, real fur texture, subtle breathing and natural ear twitch, "
  "not cartoon, not CGI, not illustration. Single locked medium close-up portrait "
  "shot, softly lit contemporary office with a shallow depth of field. "
  "At first the cat glances at the laptop and slowly blinks. Then it looks directly "
  "at the camera and clearly SPEAKS IN POLISH, with perfectly timed visible "
  "mouth and jaw articulation, in a natural dry and mildly tired human male voice: "
  '"Jest poniedziałek. A ja już chcę obiad." '
  "During the words, the cat's muzzle visibly moves in sync with every syllable. "
  "After speaking, it gives a dry stare and glances toward the lunchbox. "
  "The audio includes the cat's exact spoken Polish words, close-miked clear "
  "Polish speech front and center, with subtle distant office keyboard sounds "
  "underneath. No voiceover, no narrator, no music and no overlaid text. "
  "Only one cat and one speaker. The spoken line is short, unhurried and fully finished."
 )
 report["full_prompt"]=prompt
 client=Client("Lightricks/LTX-2.5",httpx_kwargs={"timeout":40.0})
 result=client.predict(prompt,None,896,512,6.0,2718,"conv",False,False,False,api_name="/run")
 raw=result[0] if isinstance(result,(tuple,list)) else result
 if isinstance(raw,dict): raw=raw.get("path") or raw.get("video") or raw.get("name")
 generated=Path(raw)
 if not generated.is_file() or generated.stat().st_size<100_000:raise RuntimeError("No original generated MP4")
 shutil.copyfile(generated,OUT)
 report["generated_bytes"]=OUT.stat().st_size
 report["reported_frames"]=result[-1] if isinstance(result,(tuple,list)) else ""
 p=run(["ffprobe","-v","error","-show_entries","stream=codec_type,codec_name,duration:format=duration",
    "-of","json",str(OUT)],capture_output=True,text=True)
 data=json.loads(p.stdout)
 streams={x.get("codec_type"):x for x in data.get("streams",[])}
 if not {"video","audio"} <= streams.keys(): raise RuntimeError("No native audio+video tracks")
 report["duration"]=data.get("format",{}).get("duration")
 vol=subprocess.run(["ffmpeg","-nostdin","-i",str(OUT),"-vn","-af","volumedetect",
    "-f","null","-"],capture_output=True,text=True,timeout=45)
 m=re.search(r"mean_volume:\s*(-?[\d.]+)\s*dB",vol.stderr)
 report["mean_audio_db"]=float(m.group(1)) if m else None
 if not m or float(m.group(1))<-60:raise RuntimeError("Audio contains no audible content")
 report["success"]=True
 save()
 print("Generated real cat MOVING VIDEO + NATIVE SOUND",json.dumps(report,ensure_ascii=False)[:600],flush=True)
 print("CHECKING IF MODEL ACTUALLY SPOKE POLISH (speech recognition)",flush=True)
 from faster_whisper import WhisperModel
 model=WhisperModel("base",device="cpu",compute_type="int8")
 segments, info=model.transcribe(str(OUT),language="pl",beam_size=3,vad_filter=False,
   condition_on_previous_text=False)
 transcript=" ".join(s.text.strip() for s in segments).strip()
 report["detected_transcript"]=transcript
 report["speech_language_probability"]=round(info.language_probability,3)
 norm=lambda s:re.sub(r"[^a-ząćęłńóśźż ]","",s.lower()).strip()
 ratio=difflib.SequenceMatcher(None,norm(DIALOGUE),norm(transcript)).ratio()
 report["dialogue_similarity"]=round(ratio,3)
 report["speech_verified"]= ratio >= .66
 if not report["speech_verified"]:
   report["warning"]="Audio exists but Polish exact dialogue not confirmed; do not claim accurate lip sync or dialogue"
 print("WHISPER TRANSCRIPT:",transcript,"MATCH",report["dialogue_similarity"],flush=True)
except Exception as exc:
 report["error"]=str(exc)
 report["traceback"]=traceback.format_exc()[-2400:]
 print("GENERATION/VALIDATION ERROR:",exc,flush=True)
finally:
 save()
if not report["success"]:raise SystemExit(2)
