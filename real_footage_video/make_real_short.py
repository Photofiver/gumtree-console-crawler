#!/usr/bin/env python3
"""Produce a real moving-footage 9:16 social clip. Source: Wikimedia Commons, CC BY 3.0.
No synthetic/slideshow footage. Wikimedia source and author remain credited in video and file.
"""
import json
import subprocess
import urllib.request
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg

SRC = "https://upload.wikimedia.org/wikipedia/commons/e/ed/Gigaset_Smartphone_Production_V_Attaching_the_Label.webm"
PAGE = "https://commons.wikimedia.org/wiki/File:Gigaset_Smartphone_Production_V_Attaching_the_Label.webm"
LIC = "https://creativecommons.org/licenses/by/3.0/"
OUT = Path("social-real-footage-short.mp4")
head = {"User-Agent": "Photofiver-SocialVideo-Prototype/0.1 (https://github.com/Photofiver/gumtree-console-crawler; non-commercial test)"}
req=urllib.request.Request(SRC,headers=head)
with urllib.request.urlopen(req,timeout=90) as response:
    length=response.headers.get("Content-Length")
    if length and int(length)>25_000_000:
        raise RuntimeError("Source video too large")
    data=response.read(25_000_001)
    if len(data)>25_000_000 or len(data)<500_000:
        raise RuntimeError("Unexpected video size: "+str(len(data)))
Path("footage.webm").write_bytes(data)
fontb="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
font="/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
im=Image.new("RGBA",(720,1280),(0,0,0,0));d=ImageDraw.Draw(im)
d.rounded_rectangle((28,45,692,250),radius=20,fill=(8,16,30,195))
d.text((48,85),"ZOBACZ JAK PRACUJE",font=ImageFont.truetype(fontb,43),fill="white")
d.text((48,148),"ROBOT W FABRYCE",font=ImageFont.truetype(fontb,42),fill=(255,221,100))
d.rounded_rectangle((27,1017,692,1225),radius=24,fill=(9,16,30,220))
d.text((50,1049),"Prawdziwe nagranie",font=ImageFont.truetype(fontb,37),fill="white")
d.text((50,1110),"Gigaset / Sounds of Changes",font=ImageFont.truetype(font,27),fill=(221,226,232))
d.text((50,1165),"CC BY 3.0 · kadr przycięty",font=ImageFont.truetype(font,25),fill=(221,226,232))
im.save("overlay.png")

exe=imageio_ffmpeg.get_ffmpeg_exe()
cmd=[exe,"-nostdin","-hide_banner","-loglevel","error","-y",
 "-i","footage.webm","-loop","1","-i","overlay.png",
 "-filter_complex",
 "[0:v]scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,setsar=1,fps=25,format=yuv420p[bg];[bg][1:v]overlay=0:0:shortest=1[out]",
 "-map","[out]","-map","0:a?","-t","12.5","-r","25",
 "-c:v","libx264","-preset","veryfast","-crf","25","-pix_fmt","yuv420p",
 "-c:a","aac","-b:a","96k","-movflags","+faststart",str(OUT)]
print("RUNNING ffmpeg", flush=True)
subprocess.run(cmd,check=True,timeout=180)
assert OUT.exists() and OUT.stat().st_size>100_000
credit={
  "video_title":"Gigaset Smartphone Production V: Attaching the Label",
  "creator":"Sounds of Changes; video recordist Inke Pickhardt; sound recordist Kathinka Engels",
  "source":PAGE,"license":"CC BY 3.0","license_url":LIC,
  "changes":"Cropped to 9:16, overlaid Polish text and attribution, encoded to MP4",
  "output":str(OUT),"size_bytes":OUT.stat().st_size,
  "video_content":"Real moving camera footage, not AI generated video or still slides"
}
Path("social-real-footage-credits.json").write_text(json.dumps(credit,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(credit,ensure_ascii=False), flush=True)
