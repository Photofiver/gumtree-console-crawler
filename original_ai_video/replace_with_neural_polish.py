#!/usr/bin/env python3
"""Replace robotic eSpeak narration on previously original AI-generated film with
a more human-sounding offline neural Polish speech voice (Piper Gosia medium).

No external stock media. Preserves only previously AI-generated video track; creates
a fresh wholly synthetic neural audio track. Original LTX video from this repository.
Piper voice: rhasspy/piper-voices, pl_PL-gosia-medium, voice model card CC0 dataset.
"""
import json
import subprocess
from pathlib import Path
from urllib.request import Request, urlopen

OUT=Path("ai-robot-neural-human-voice-pl.mp4")
SRC=Path("ai-speaking-robot-source.mp4")
VOICE=Path("piper-polish-voice.wav")
TEXT="Cześć! Jestem małym robotem!"
SOURCE_URL="https://raw.githubusercontent.com/Photofiver/gumtree-console-crawler/main/social_videos/ai-speaking-robot-polish.mp4"
HEADERS={"User-Agent":"Photofiver-Original-AI-Video-GitHub-Action/1.0"}
report={"source_original_ai_video":SOURCE_URL,"voice_model":"pl_PL-gosia-medium",
        "voice_engine":"Piper local neural text-to-speech","text":TEXT,"success":False}
Path("neural-voice-report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2))
try:
    with urlopen(Request(SOURCE_URL,headers=HEADERS),timeout=30) as r:
        SRC.write_bytes(r.read(15000000))
    assert SRC.stat().st_size>100000
    print("PIPER NEURAL VOICE",flush=True)
    # Installed piper-tts will fetch the open model from rhasspy/piper-voices.
    # Ensure that the actual Polish neural model is loaded; no espeak replacement or fallback.
    result=subprocess.run(["python3","-m","piper","-m","pl_PL-gosia-medium","-f",str(VOICE),"--",TEXT],
       input="",text=True,capture_output=True,timeout=180)
    print("PIPER stdout",result.stdout[-800:],"stderr",result.stderr[-1400:],flush=True)
    if result.returncode:
        raise RuntimeError("Piper neural voice generation failed: "+result.stderr[-1500:])
    assert VOICE.is_file() and VOICE.stat().st_size>12000
    print("MIXING NEURAL VOICE INTO ORIGINAL AI VIDEO",flush=True)
    # Remove previous robot-like speech completely: map only video from source.
    # Pad with quiet final frame if speech extends beyond video by a few frames.
    subprocess.run(["ffmpeg","-nostdin","-y","-hide_banner","-loglevel","error",
        "-i",str(SRC),"-i",str(VOICE),
        "-filter_complex",
        "[1:a]adelay=250:all=1,volume=1.25,loudnorm=I=-16:TP=-1.5:LRA=10[a]",
        "-map","0:v:0","-map","[a]","-c:v","copy","-c:a","aac","-b:a","160k",
        "-movflags","+faststart","-shortest",str(OUT)],check=True,timeout=90)
    probe=subprocess.run(["ffprobe","-v","error","-show_entries","stream=codec_type,codec_name,duration",
        "-of","json",str(OUT)],capture_output=True,text=True,check=True)
    streams=json.loads(probe.stdout)["streams"]
    assert {s["codec_type"] for s in streams}>={"audio","video"}
    assert OUT.stat().st_size>100000
    report.update(success=True,video_bytes=OUT.stat().st_size,synthesized_wav_bytes=VOICE.stat().st_size,
                  streams=streams)
    print("VERIFIED NEURAL HUMAN-LIKE POLISH VOICE MP4",OUT.stat().st_size,flush=True)
except Exception as exc:
    report["error"]=str(exc)
    print("ERROR",str(exc),flush=True)
finally:
    Path("neural-voice-report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2))
if not report["success"]:raise SystemExit(2)
