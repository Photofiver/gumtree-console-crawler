#!/usr/bin/env python3
"""Generate an original, photorealistic talking cat with native Polish voice.
This is a separate pipeline; it does not import or modify the BloFin bot
or the existing Google AI and film workflows.
"""
import difflib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCENES = [
    ("Jest poniedziałek. A ja już chcę obiad.", "at an office desk, paw on a keyboard; glances at lunchbox"),
    ("Pracuję zdalnie. Z własnej kanapy.", "on a leather couch beside an open laptop; yawns and stretches"),
    ("Szef pyta o wyniki. Ja o karmę.", "in a business meeting behind a conference desk; tilts head at food bowl"),
    ("Mam dziś spotkanie. Z moją miską.", "at a bright office desk beside a cat bowl; stares thoughtfully"),
    ("Mój budżet? Wszystko na tuńczyka.", "at a tidy home office desk with calculator and can of tuna"),
    ("Przyszedłem do pracy. Po przekąski.", "in a company kitchen with a snack bowl on the counter"),
    ("Najpierw kawa. Potem pięć drzemek.", "by a home-office coffee cup, blinking sleepily"),
    ("Deadline? Najpierw szybka drzemka.", "at an office desk full of papers; lowers head sleepily"),
    ("Plan na dziś? Zjeść i odpoczywać.", "sitting in the morning sunlight at a windowsill"),
    ("Mam ważną konferencję. Z lodówką.", "in the office kitchen peering toward the refrigerator"),
    ("Nie przeszkadzaj. Liczę moje chrupki.", "at the kitchen table beside tiny piles of dry cat food"),
    ("Mój talent? Wyglądać na zajętego.", "typing on a computer keyboard with a serious expression"),
]
now=datetime.now(timezone.utc)
slot=now.hour//4*4
stamp=f"{now:%Y%m%d}-{slot:02d}"
index=int(now.strftime("%Y%m%d"))*6+now.hour//4
line,scene=SCENES[index%len(SCENES)]
out=Path("social_videos")/f"ai-cat-{stamp}.mp4"
report=Path("autopost_tiktok")/"last-generation-report.json"

def run(args,**kw):
    return subprocess.run(args,check=True,timeout=kw.pop("timeout",150),**kw)

def save(data):
    report.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")

info={"slot":stamp,"caption_line":line,"file":str(out),"generated":False,"speech_verified":False,
      "video_model":"Lightricks/LTX-2.5","no_stock_footage":True}
save(info)
if out.exists():
    print("SKIP: generation file already exists for this four-hour slot")
    sys.exit(0)
try:
    from gradio_client import Client
    client=Client("Lightricks/LTX-2.5",httpx_kwargs={"timeout":40.0})
    prompt=(
      "Real 9:16 vertical cinematic video, ultra-photorealistic lifelike orange tabby "
      "house cat, realistic detailed individual fur, true feline anatomy, whiskers, "
      "natural amber eyes, wet pink nose, cute face. Wearing a loose charcoal business "
      "tie, "+scene+". Bright natural cinematic lighting with a subtle depth of field. "
      "ONE continuous moving camera shot. Cat looks directly into camera with lively "
      "expressive face, and speaks clearly in Polish with natural lightly tired human "
      "male voice, actual spoken sentence, EXACTLY: '"+line+"' "
      "AUDIO AND VIDEO ARE GENERATED TOGETHER: matching visible feline mouth and jaw "
      "articulation while each Polish word is spoken; no narrator overlay and no second "
      "speaker. After speaking it blinks and reacts. Clear voice with quiet natural "
      "environment audio; no songs, no subtitles, no signs, no watermarks. Not cartoon, "
      "not CGI stylization, not still photo, not a slideshow."
    )
    # Space provides up to five seconds per video; portrait dimensions 512 x 896.
    res=client.predict(prompt,None,512,896,5.0,now.hour*100+now.day*7,"conv",
        False,False,False,api_name="/run")
    raw=res[0] if isinstance(res,(list,tuple)) else res
    if isinstance(raw,dict):
        raw=raw.get("path") or raw.get("video") or raw.get("name")
    src=Path(raw)
    assert src.is_file() and src.stat().st_size>100000,"AI model did not return valid video"
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_bytes(src.read_bytes())
    p=run(["ffprobe","-v","error","-show_entries",
        "format=duration:stream=codec_type,codec_name,width,height,nb_frames",
        "-of","json",str(out)],capture_output=True,text=True,timeout=30)
    details=json.loads(p.stdout)
    streams=details.get("streams",[])
    assert {"audio","video"}.issubset({s.get("codec_type") for s in streams})
    video=next(s for s in streams if s["codec_type"]=="video")
    assert video["height"]>video["width"],"Video isn't vertical"
    duration=float(details["format"]["duration"])
    assert 4.0<=duration<=6.0, f"Unexpected duration {duration}"
    volume=subprocess.run(["ffmpeg","-nostdin","-hide_banner","-i",str(out),
       "-vn","-af","volumedetect","-f","null","-"],capture_output=True,text=True,timeout=30)
    m=re.search(r"mean_volume:\s*(-?[\d.]+)\s*dB",volume.stderr)
    assert m and float(m.group(1))>-55,"Speech track may be silent"
    # Do not upload if the synthetic dialogue is missing or materially wrong.
    from faster_whisper import WhisperModel
    transcriber=WhisperModel("base",device="cpu",compute_type="int8")
    segments,language=transcriber.transcribe(str(out),language="pl",
         beam_size=3,vad_filter=False,condition_on_previous_text=False)
    recognized=" ".join(x.text.strip() for x in segments).strip()
    norm=lambda s:re.sub(r"[^a-ząćęłńóśźż ]","",s.lower()).strip()
    match=difflib.SequenceMatcher(None,norm(line),norm(recognized)).ratio()
    info.update({"duration_s":duration,"width":video["width"],"height":video["height"],
         "audio_mean_db":float(m.group(1)),"transcribed":recognized,
         "speech_similarity":round(match,3),"video_bytes":out.stat().st_size,
         "generated":True,"speech_verified":match>=0.7})
    save(info)
    if not info["speech_verified"]:
        out.unlink(missing_ok=True)
        raise RuntimeError("Polish AI dialogue verification failed; video discarded")
    print("GENERATED, VERIFIED POLISH WORDS AND 9:16 ORIGINAL AI VIDEO",stamp,flush=True)
except Exception as e:
    info["error"]=str(e)
    save(info)
    print("GENERATION FAILED, WILL NOT PUBLISH",str(e),flush=True)
    raise
