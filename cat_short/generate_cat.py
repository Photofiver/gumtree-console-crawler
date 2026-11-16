#!/usr/bin/env python3
"""Original 5s AI-generated humorous cat TikTok, narrated in Polish by local
neural voice. No external footage or paid services. Save and verify final MP4.
"""
import json, re, subprocess, traceback
from pathlib import Path
from gradio_client import Client

TEXT="Jest poniedziałek. Udaję, że pracuję... ale myślę o jedzeniu."
OUTPUT=Path("cat-boss-ai-polish.mp4")
REPORT=Path("cat-boss-report.json")
report={
  "concept":"Funny office cat pretending to work, thinking about food",
  "spoken_text":TEXT,"language":"pl",
  "video_model":"Lightricks/LTX-2.5",
  "voice_model":"pl_PL-gosia-medium (Piper local neural TTS)",
  "footage_source":"AI text-to-video generation, no stock footage",
  "success":False
}
def save():
    REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2))
save()

def cmd(args,**kw):
    return subprocess.run(args,check=True,timeout=kw.pop("timeout",150),**kw)

try:
    print("CAT SHORT: generating a truly original moving AI cat video",flush=True)
    client=Client("Lightricks/LTX-2.5",httpx_kwargs={"timeout":40})
    prompt=(
      "Vertical 9:16 3D animated comedy film, ONE continuous camera shot, adorable expressive "
      "chubby orange tabby cat with a white chin, wearing a charcoal business suit and loose yellow tie, "
      "sitting at a modern office desk, paws tapping nervously on a computer keyboard. "
      "Cat is pretending to be a very serious employee. Cat looks straight into the camera with "
      "a funny deadpan face, mouth subtly moving as if speaking, then glances hungrily at a big "
      "delicious sandwich hidden under the desk, suddenly pulls the sandwich up and takes a joyful bite. "
      "Warm film lighting, rich cinematic 3D quality, shallow depth of field, lively continuous "
      "physical action, tiny facial movements, blink and tail swish. Close-up framing, clear view "
      "of whole head and paws, no captions, no signs, no text, no watermarks. "
      "Audio: gentle keyboard clicks and tiny cute office ambience under spoken Polish narration, "
      "not a slideshow and no still frames."
    )
    result=client.predict(prompt,None,896,512,5.0,736,"conv",False,False,False,api_name="/run")
    raw=result[0] if isinstance(result,(tuple,list)) else result
    if isinstance(raw,dict):raw=raw.get("path") or raw.get("video")
    original=Path(raw)
    assert original.is_file() and original.stat().st_size>=100_000,"No moving video returned"
    report["raw_video_bytes"]=original.stat().st_size
    report["model_frames"]=result[-1] if isinstance(result,(tuple,list)) else ""
    print("CAT SHORT: neural Polish narrator",flush=True)
    tts=cmd(["python3","-m","piper","-m","pl_PL-gosia-medium","-f","cat-voice.wav","--",TEXT],
      input="",capture_output=True,text=True,timeout=120)
    if not Path("cat-voice.wav").is_file():
        raise RuntimeError("Polish voice synthesis produced no file; log: "+tts.stderr[-1000:])
    # Check length to avoid silently clipping words.
    def probe(path):
        p=cmd(["ffprobe","-v","error","-show_entries",
            "format=duration:stream=codec_type,codec_name",
            "-of","json",str(path)],capture_output=True,text=True,timeout=30)
        return json.loads(p.stdout)
    vmeta=probe(original);ameta=probe("cat-voice.wav")
    v_duration=float(vmeta["format"]["duration"])
    a_duration=float(ameta["format"]["duration"])
    report["video_duration_s"]=round(v_duration,3)
    report["voice_duration_s"]=round(a_duration,3)
    print("CAT SHORT: video duration",v_duration,"voice duration",a_duration,flush=True)
    if a_duration+0.25>v_duration:
        raise RuntimeError(f"Voice ({a_duration:.2f}s) would be cut short by {v_duration:.2f}s clip")
    vstreams=vmeta.get("streams",[])
    has_native_audio=any(s.get("codec_type")=="audio" for s in vstreams)
    if has_native_audio:
        mix=("[0:a:0]volume=0.12[amb];"
            "[1:a:0]adelay=250:all=1,volume=1.3[voice];"
            "[amb][voice]amix=inputs=2:duration=first:dropout_transition=0,"
            "loudnorm=I=-16:TP=-1.5:LRA=10[a]")
    else:
        mix="[1:a:0]adelay=250:all=1,loudnorm=I=-16:TP=-1.5:LRA=10[a]"
    print("CAT SHORT: mixing the real synthesized voice",flush=True)
    cmd(["ffmpeg","-nostdin","-y","-hide_banner","-loglevel","error",
        "-i",str(original),"-i","cat-voice.wav",
        "-filter_complex",mix,
        "-map","0:v:0","-map","[a]",
        "-c:v","copy","-c:a","aac","-b:a","160k",
        "-movflags","+faststart",str(OUTPUT)],timeout=180)
    result=probe(OUTPUT)
    types={s.get("codec_type") for s in result.get("streams",[])}
    assert {"video","audio"}<=types,"Audio/video streams missing"
    assert OUTPUT.stat().st_size>100_000
    stats=subprocess.run(["ffmpeg","-nostdin","-hide_banner","-i",str(OUTPUT),
        "-vn","-af","volumedetect","-f","null","-"],
        capture_output=True,text=True,timeout=30)
    m=re.search(r"mean_volume:\s*(-?[\d.]+)\s*dB",stats.stderr)
    report["average_audio_db"]=float(m.group(1)) if m else None
    assert m and float(m.group(1))>-60,"Output audio might be silent"
    report.update({"success":True,"final_bytes":OUTPUT.stat().st_size,
       "final_duration_s":round(float(result["format"]["duration"]),3),
       "audio_and_video_verified":True,"voice_has_room_to_finish":True})
    print("CAT_SHORT_SUCCESS",json.dumps(report,ensure_ascii=False),flush=True)
except Exception as e:
    report["error"]=str(e)
    report["traceback"]=traceback.format_exc()[-2600:]
    print("CAT_SHORT_FAILURE",str(e),flush=True)
finally:
    save()
if not report["success"]:raise SystemExit(2)
