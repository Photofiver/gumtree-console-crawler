#!/usr/bin/env python3
"""Create a new original text-to-video clip with AUDIO by public LTX 2.5.
The model must output actual sound; it is normalized for phone playback.
No stock footage, no slides, and no externally sourced audio.
"""
import json, re, shutil, subprocess, traceback
from pathlib import Path
from gradio_client import Client

model="Lightricks/LTX-2.5"
target=Path("generated-ai-film-with-sound.mp4")
report={"source":model,"generated_from_text":True,"original_motion":True,
        "original_ai_audio":False,"success":False}
def update():
    Path("sound_video_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2))
update()
try:
    c=Client(model,httpx_kwargs={"timeout":40})
    api=c.view_api(return_format="dict")
    run=api["named_endpoints"]["/run"]
    report["endpoint"]="/run"
    report["num_parameters"]=len(run["parameters"])
    assert len(run["parameters"]) == 10, "The public generator API changed"
    prompt=(
      "One continuous original cinematic vertical video shot: a tiny cute turquoise clockwork robot "
      "with glowing amber eyes walks across a magical glass forest floor at sunrise, "
      "then hops over a shallow stream with a funny little metallic splash and continues walking. "
      "CAMERA slowly dollies forward while the robot physically moves and leafy branches sway. "
      "AUDIO: clearly audible ASMR-style tiny clinking metallic robot footsteps, "
      "gentle soft whirring of gears, flowing stream water, joyful sparkly bell chimes "
      "when the robot leaps, a distinct splash, soft birds in the background. "
      "Record these synchronous sounds prominently and cleanly, no speech, no soundtrack, "
      "no silence. High quality 3D animated short film, lively natural motion, rich depth of field, "
      "no signs, no logos, no text.")
    report["prompt"]=prompt
    print("GENERATING ORIGINAL VIDEO AND SOUND",flush=True)
    output=c.predict(prompt,None,896,512,4.0,154,"conv",False,False,False,api_name="/run")
    print("AI OUTPUT",str(output)[:1000],flush=True)
    v=output[0] if isinstance(output,(list,tuple)) else output
    if isinstance(v,dict):v=v.get("path") or v.get("video") or v.get("name")
    raw=Path(v)
    if not raw.is_file() or raw.stat().st_size<100000:raise RuntimeError("No real generated video")
    probe=subprocess.run(["ffprobe","-v","error","-show_entries","stream=index,codec_type,codec_name","-of","json",str(raw)],capture_output=True,text=True,check=True)
    streams=json.loads(probe.stdout)["streams"]
    report["streams_before"]=streams
    if not any(s.get("codec_type")=="audio" for s in streams):
        raise RuntimeError("The generative model did not produce an audio track")
    print("NORMALIZING GENERATED AUDIO FOR PHONE PLAYBACK",flush=True)
    subprocess.run(["ffmpeg","-nostdin","-y","-loglevel","error","-i",str(raw),
       "-map","0:v:0","-map","0:a:0","-c:v","copy","-c:a","aac","-b:a","192k",
       "-af","loudnorm=I=-16:TP=-1.5:LRA=11",
       "-movflags","+faststart",str(target)],check=True,timeout=180)
    stat=subprocess.run(["ffmpeg","-nostdin","-hide_banner","-i",str(target),
       "-vn","-af","volumedetect","-f","null","-"],capture_output=True,text=True,timeout=70)
    m=re.search(r"mean_volume:\s*(-?[\d.]+)\s*dB",stat.stderr)
    report["mean_audio_db"]=float(m.group(1)) if m else None
    report["audio_stats"]=stat.stderr[-1800:]
    if not m or float(m.group(1))<-60:
        raise RuntimeError("Generated audio is silent or too quiet even after normalization")
    report["original_ai_audio"]=True
    report["bytes"]=target.stat().st_size
    report["success"]=True
    print("VERIFIED ORIGINAL AI VIDEO AND AUDIBLE SOUND",report["mean_audio_db"],"dB",flush=True)
except Exception as e:
    report["error"]=str(e)
    report["traceback"]=traceback.format_exc()[-2000:]
    print("FAILED:",e,flush=True)
finally:
    update()
if not report["success"]:raise SystemExit(2)
