#!/usr/bin/env python3
"""CPU-only ORIGINAL animated motion short: cat lifts and drinks coffee, no audio.
Fallback when free AI-video generation GPU quota is unavailable.
No existing Google AI code or TikTok workflows are modified.
"""
import math
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw

W,H,FPS,SECONDS=480,854,24,7
OUT=Path("social_videos/cat-drinking-coffee-silent.mp4")
OUT.parent.mkdir(exist_ok=True, parents=True)

def easing(x):
    x=max(0,min(1,x))
    return x*x*(3-2*x)

def cup():
    im=Image.new("RGBA",(170,150))
    d=ImageDraw.Draw(im)
    d.ellipse((102,48,159,124),outline=(250,230,208,255),width=13)
    d.rounded_rectangle((24,46,128,126),radius=20,
        fill=(246,229,210),outline=(172,130,104),width=4)
    d.ellipse((24,31,129,69),fill=(254,244,230),outline=(174,129,96),width=4)
    d.ellipse((33,40,120,63),fill=(94,51,34))
    d.arc((47,43,108,60),0,160,fill=(184,120,70),width=3)
    d.ellipse((70,82,85,98),fill=(211,160,121))
    return im
CUP=cup()

def background():
    im=Image.new("RGBA",(W,H))
    d=ImageDraw.Draw(im)
    for y in range(H):
        d.line((0,y,W,y),fill=(24+int(y*75/H),43+int(y*48/H),59+int(y*24/H)))
    d.rounded_rectangle((287,65,467,484),radius=19,
        fill=(241,193,138),outline=(243,211,162),width=7)
    d.ellipse((323,106,419,212),fill=(255,239,181))
    for yy in (194,329,442):
        d.line((290,yy,465,yy),fill=(158,106,79),width=9)
    d.line((382,68,382,481),fill=(158,106,79),width=9)
    d.ellipse((-125,26,135,135),fill=(24,32,46))
    d.arc((-48,78,136,175),0,180,fill=(255,205,146),width=5)
    d.line((454,0,454,157),fill=(195,154,117),width=4)
    for j in range(6):
        x=453+17*math.cos(j*.9);y=158+16*math.sin(j*.9)
        d.ellipse((x-10,y-12,x+10,y+12),fill=(33,128,82))
    return im
BG=background()
process=subprocess.Popen(["ffmpeg","-y","-hide_banner","-loglevel","error",
  "-f","rawvideo","-vcodec","rawvideo","-pix_fmt","rgb24","-s",f"{W}x{H}",
  "-r",str(FPS),"-i","-","-an","-c:v","libx264","-preset","fast","-crf","21",
  "-pix_fmt","yuv420p","-movflags","+faststart",str(OUT)],stdin=subprocess.PIPE)
try:
  for frame in range(FPS*SECONDS):
    t=frame/FPS
    pos=easing((t-1.0)/1.5)*(1-easing((t-3.7)/1.5))
    sip=2.55<=t<=3.75
    cx=368-118*pos; cy=698-226*pos+2*math.sin(t*13)*float(sip)
    im=BG.copy()
    d=ImageDraw.Draw(im)
    d.rounded_rectangle((52,429,415,758),radius=80,fill=(38,70,85))
    d.line((169,667,88+7*math.sin(t),650),fill=(174,84,51),width=32)
    d.ellipse((133,485,383,750),fill=(209,113,65),outline=(159,78,48),width=6)
    d.ellipse((206,568,336,740),fill=(247,195,138))
    for j in range(3):
        d.arc((143+j*9,536+j*13,254+j*9,721+j*10),110,236,fill=(146,79,49),width=8)
        d.arc((285-j*5,536+j*13,395-j*5,719+j*11),280,422,fill=(151,76,48),width=8)
    d.polygon([(150,365),(160,264),(223,300)],fill=(205,112,65))
    d.polygon([(159,344),(173,285),(206,311)],fill=(223,137,125))
    d.polygon([(314,299),(375,266),(382,366)],fill=(204,104,60))
    d.polygon([(334,314),(363,290),(371,343)],fill=(221,138,122))
    dy=2*math.sin(t*1.4)-4*pos
    d.ellipse((125,296+dy,383,530+dy),fill=(226,136,70),outline=(167,82,49),width=6)
    d.polygon([(236,302),(250,342),(257,322)],fill=(164,79,45))
    d.polygon([(291,304),(268,339),(277,326)],fill=(164,79,45))
    blink=max(0,1-abs(t-5.65)/0.17)
    for ex in (196,310):
        ey=402+dy; yh=max(2,25*(1-blink))
        d.ellipse((ex-29,ey-yh,ex+29,ey+yh),fill=(255,244,215))
        if yh>8:
            d.ellipse((ex-15+4*pos,ey-19,ex+14+4*pos,ey+20),fill=(66,140,109))
            d.ellipse((ex-6+4*pos,ey-16,ex+7+4*pos,ey+16),fill=(30,63,55))
            d.ellipse((ex-8+4*pos,ey-16,ex-1+4*pos,ey-8),fill=(255,255,255))
        else:
            d.line((ex-24,ey,ex+24,ey),fill=(77,59,50),width=3)
    d.ellipse((190,445+dy,266,498+dy),fill=(246,208,158))
    d.ellipse((252,445+dy,326,498+dy),fill=(246,208,158))
    d.polygon([(248,457+dy),(268,457+dy),(258,469+dy)],fill=(205,116,111))
    if sip:
        d.ellipse((249,480+dy,267,494+dy),fill=(91,49,49))
    else:
        d.arc((238,475+dy,259,489+dy),0,130,fill=(115,72,65),width=3)
        d.arc((259,475+dy,279,489+dy),40,180,fill=(115,72,65),width=3)
    for sy in (-12,0,14):
        for left in (True,False):
            start=226 if left else 293; end=130 if left else 389
            d.line((start,480+dy+sy,end,480+dy+sy*2),fill=(248,230,206),width=2)
    d.rounded_rectangle((-5,707,W+5,875),radius=14,fill=(113,68,50))
    d.rectangle((0,710,W,719),fill=(188,124,76))
    for yy in (766,810):
        d.line((0,yy,W,yy),fill=(81,49,42),width=4)
    # The front paw visibly lifts the mug from the cafe table to the cat's mouth.
    d.line((330,615,cx+35,cy+59),fill=(177,88,47),width=34)
    d.line((328,613,cx+32,cy+56),fill=(230,139,70),width=24)
    d.ellipse((cx+15,cy+42,cx+52,cy+77),fill=(226,131,64),
      outline=(151,76,48),width=3)
    im.alpha_composite(CUP,(int(cx-85),int(cy-75)))
    d=ImageDraw.Draw(im)
    for j in (0,1):
        steamx=cx-22+j*33
        steam=[(steamx+6*math.sin((k+t*20+j*10)/17),
                 cy-79-k-(t*20)%18) for k in range(0,61,4)]
        d.line(steam,fill=(255,247,224,85 if pos<.6 else 30),width=3)
    process.stdin.write(im.convert("RGB").tobytes())
  process.stdin.close()
  if process.wait(timeout=90)!=0:
    raise RuntimeError("ffmpeg encoding failed")
finally:
  if process.poll() is None:
    process.kill()
assert OUT.is_file() and OUT.stat().st_size>50000
print("SILENT MOTION MP4 CREATED",OUT,OUT.stat().st_size,flush=True)
