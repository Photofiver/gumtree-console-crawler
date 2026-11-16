import json, re, sys, os, textwrap
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

data=json.loads(Path("social-media-probe.json").read_text(encoding="utf-8"))
page=data["google_ai"]
body=page.get("text","")
# Extract only the returned answer, never the echoed question.
body=body.split("AI Mode reply for")[-1]
body=body.split("AI can make mistakes")[0]
parts={}
for key in ["HEADLINE","SCENE1","SCENE2","SCENE3","CAPTION"]:
    m=re.search(r"(?m)^\s*"+key+r":\s*(.+)$",body)
    if not m:
        print("NOT_CONFIRMED: no generated answer field",key)
        sys.exit(2)
    parts[key]=m.group(1).strip()
if not all(len(v)>3 and len(v)<250 for v in parts.values()):
    print("NOT_CONFIRMED: invalid generated response lengths")
    sys.exit(2)

Path("social-ai-script.json").write_text(json.dumps(parts,indent=2,ensure_ascii=False))
font="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
small="/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
slides=["HEADLINE","SCENE1","SCENE2","SCENE3"]
from PIL import ImageColor
for idx, key in enumerate(slides):
    im=Image.new("RGB",(720,1280),(20,26,38))
    d=ImageDraw.Draw(im)
    d.rounded_rectangle((55,130,665,1160),radius=48,fill=(33,49,74))
    d.text((85,215),f"{idx+1} / 4",font=ImageFont.truetype(small,43),fill=(175,190,210))
    f=ImageFont.truetype(font,58)
    words=parts[key].split()
    lines=[]; line=""
    for word in words:
        trial=(line+" "+word).strip()
        if d.textbbox((0,0),trial,font=f)[2]>520 and line:
            lines.append(line); line=word
        else: line=trial
    if line: lines.append(line)
    y=430-(len(lines)-2)*45
    for line in lines:
        d.text((100,y),line,font=f,fill=(250,250,255))
        y+=80
    d.text((86,1035),"AI script  |  GitHub video",font=ImageFont.truetype(small,27),fill=(162,183,211))
    im.save(f"social-slide-{idx}.png")
print("GENERATED_AI_SCRIPT",json.dumps(parts,ensure_ascii=False))
