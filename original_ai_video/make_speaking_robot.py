#!/usr/bin/env python3
"""Generate original moving video and add a 100% synthetic Polish robot voice.
No stock videos, no user account, no paid API. Offline espeak-ng guarantees
an actual intelligible spoken sentence even if native LTX dialogue is unclear.
"""
from gradio_client import Client
from pathlib import Path
import json,subprocess,traceback
report={"model":"Lightricks/LTX-2.5","sound":"espeak-ng Polish robotic synthesized voice mixed with model native sound",
        "speech_text":"Cześć! Jestem małym robotem!","generated_from_text":True,
        "verified_speech_track":False,"success":False}
out=Path("ai-speaking-robot-polish.mp4")
try:
    print("GENERATING ORIGINAL MOVING VIDEO",flush=True)
    prompt=(
      "One smooth vertical cinematic shot, 3D animation of a cute little imaginary turquoise "
      "robot with a friendly expressive metal mouth and large glowing amber eyes, standing "
      "in a fantasy magical glowing glass forest. The robot turns toward camera, waves its "
      "tiny mechanical hand, and moves its mouth as it delivers a cheerful short greeting "
      "in Polish, then blinks and smiles. The robot articulates its mouth clearly during "
      "the greeting and maintains eye contact, bright cute animation, coherent physical "
      "movement, single character, close-up medium shot, no subtitles, no text, no logos. "
      "Audio: subtle gentle birds singing and magical chimes; calm ambient atmosphere.")
    client=Client("Lightricks/LTX-2.5",httpx_kwargs={"timeout":40})
    result=client.predict(prompt,None,896,512,5.0,882,"conv",False,False,False,api_name="/run")
    raw=result[0] if isinstance(result,(tuple,list)) else result
    if isinstance(raw,dict):raw=raw.get("path") or raw.get("video")
    src=Path(raw)
    assert src.is_file() and src.stat().st_size>100000,"LTX did not generate a video"
    report["model_output_bytes"]=src.stat().st_size
    report["frames"]=result[-1] if isinstance(result,(tuple,list)) else ""
    print("GENERATING ORIGINAL POLISH VOICE",flush=True)
    subprocess.run(["espeak-ng","-v","pl","-s","145","-p","58","-a","165",
        "-w","robot-speech.wav",report["speech_text"]],check=True,timeout=30)
    voice=Path("robot-speech.wav")
    assert voice.is_file() and voice.stat().st_size>10000
    # Native model audio underneath, voice starts 0.45s into video, mixed and normalized
    filt=("[0:a:0]volume=0.2[a];"
          "[1:a:0]adelay=450:all=1,volume=1.6[b];"
          "[a][b]amix=inputs=2:duration=first:dropout_transition=0,"
          "loudnorm=I=-16:TP=-1.5:LRA=11[out]")
    subprocess.run(["ffmpeg","-nostdin","-hide_banner","-y","-loglevel","error",
        "-i",str(src),"-i",str(voice),"-filter_complex",filt,
        "-map","0:v:0","-map","[out]","-c:v","copy","-c:a","aac",
        "-b:a","160k","-movflags","+faststart",str(out)],check=True,timeout=150)
    probe=subprocess.run(["ffprobe","-v","error","-show_entries",
        "stream=codec_type,codec_name,duration","-of","json",str(out)],
        capture_output=True,text=True,check=True)
    streams=json.loads(probe.stdout)["streams"]
    assert any(s["codec_type"]=="audio" for s in streams),"No audio track"
    assert any(s["codec_type"]=="video" for s in streams),"No video track"
    report.update({"success":True,"verified_speech_track":True,
        "bytes":out.stat().st_size,"stream_info":streams})
    print("SUCCESS POLISH SPEAKING ROBOT MOVING VIDEO",out.stat().st_size,flush=True)
except Exception as e:
    report["error"]=str(e)
    report["traceback"]=traceback.format_exc()[-2500:]
    print("FAILED",repr(e),flush=True)
finally:
    Path("ai-speaking-robot-report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2))
if not report["success"]:raise SystemExit(2)
