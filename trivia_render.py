#!/usr/bin/env python3
"""Render a 9:16 trivia video with Kokoro audio and safe text layout.
Usage: python trivia_render.py jobs/trivia/spec.json render_output
"""
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from kokoro_onnx import Kokoro
from scipy.signal import resample_poly

W, H = 1080, 1920
SR = 24000
BG = '#101622'
GREEN = '#4BEA90'
FONT_PATH = next((p for p in [os.getenv('CAPTION_FONT',''), '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'] if p and Path(p).is_file()), None)
if not FONT_PATH:
    raise SystemExit('Missing font; install fonts-dejavu-core or set CAPTION_FONT')

def font(n):
    return ImageFont.truetype(FONT_PATH, n)

def layout(text, max_w, max_h, size=74, minimum=28):
    """Return (font, lines, line_height) sized to fit its own bounded region."""
    text = str(text)
    for px in range(size, minimum - 1, -2):
        ft = font(px)
        draw = ImageDraw.Draw(Image.new('RGB', (1,1)))
        lines = []
        for paragraph in text.split('\n'):
            curr = ''
            for word in paragraph.split():
                candidate = (curr + ' ' + word).strip()
                if curr and draw.textbbox((0,0), candidate, font=ft, stroke_width=2)[2] > max_w:
                    lines.append(curr)
                    curr = word
                else:
                    curr = candidate
            lines.append(curr)
        line_h = int(px * 1.23)
        widths = [draw.textbbox((0,0),ln,font=ft,stroke_width=2)[2] for ln in lines]
        if widths and max(widths) <= max_w and len(lines) * line_h <= max_h:
            return ft, lines, line_h
    raise ValueError('Text too long for safe zone: ' + text[:60])

def centered(draw, text, box, px, color='white'):
    x0,y0,x1,y1=box
    ft, lines, line_h = layout(text, x1-x0-20,y1-y0-10,size=px)
    start_y = y0 + ((y1-y0)-len(lines)*line_h)//2
    for i,line in enumerate(lines):
        width = draw.textbbox((0,0),line,font=ft,stroke_width=2)[2]
        draw.text((x0+((x1-x0)-width)//2,start_y+i*line_h),line,font=ft,fill=color,stroke_width=2,stroke_fill='#0c0e12')

def generate_audio(spec, out_dir):
    root = Path(os.getenv('KOKORO_DIR', str(Path.home()/'factory/tts')))
    kokoro = Kokoro(str(root/'kokoro-v1.0.int8.onnx'), str(root/'voices-v1.0.bin'))
    choices = '. '.join(f'{chr(65+i)}. {v}' for i,v in enumerate(spec['options']))
    inputs = [f'Trivia time! {spec["question"]} {choices}. Make your choice!',
              f'The correct answer is {chr(65+spec["correct_index"])}. {spec["options"][spec["correct_index"]]}. {spec["explanation"]}']
    waveforms=[]
    for phrase in inputs:
        audio,sr = kokoro.create(phrase, voice=spec.get('voice','am_puck'),speed=float(spec.get('speed',1)),lang='en-us')
        audio=np.asarray(audio,dtype=np.float32).reshape(-1)
        if sr != SR:
            audio = resample_poly(audio,SR,sr).astype(np.float32)
        waveforms.append(audio)
    question_duration = max(12, math.ceil(len(waveforms[0])/SR + 1.5))
    answer_duration = max(4, math.ceil(len(waveforms[1])/SR + 0.8))
    total = question_duration + answer_duration + 1
    samples=np.zeros(total*SR,dtype=np.float32)
    for start, audio in [(0.5,waveforms[0]),(question_duration+0.3,waveforms[1])]:
        i=int(start*SR)
        samples[i:min(i+len(audio),len(samples))]+=audio[:max(0,len(samples)-i)]
    samples = np.clip(samples*0.9,-1.0,1.0)
    p=out_dir/'voice.wav'
    with wave.open(str(p),'wb') as f:
        f.setnchannels(1);f.setsampwidth(2);f.setframerate(SR)
        f.writeframes((samples*32767).astype('<i2').tobytes())
    return p,question_duration,answer_duration,total

def make_background(spec, base):
    p=base/spec['segments'][0]['path']
    if not p.is_file():
        raise FileNotFoundError(f'Missing image: {p}')
    src=Image.open(p).convert('RGB')
    scale=max(W/src.width,H/src.height)
    layer=src.resize((math.ceil(src.width*scale),math.ceil(src.height*scale)),Image.Resampling.LANCZOS)
    x=(layer.width-W)//2;y=(layer.height-H)//2
    bg=layer.crop((x,y,x+W,y+H)).filter(ImageFilter.GaussianBlur(30))
    bg=Image.blend(bg,Image.new('RGB',(W,H),(8,12,20)),0.66)
    # Keep an uncropped illustration visible behind semitransparent trivia cards.
    scale=min(800/src.width,530/src.height)
    fg=src.resize((max(1,int(src.width*scale)),max(1,int(src.height*scale))),Image.Resampling.LANCZOS)
    pos=((W-fg.width)//2,1120)
    bg.paste(Image.blend(fg,Image.new('RGB',fg.size,(18,22,29)),0.42),pos)
    return bg

def frame(spec,bg,t,question_duration,total):
    im=bg.copy()
    d=ImageDraw.Draw(im,'RGBA')
    d.rounded_rectangle((65,135,1015,300),radius=40,fill=(14,20,30,230),outline=(70,240,145,230),width=6)
    centered(d,'TRIVIA TIME!',(90,160,990,270),100,GREEN)
    if t < question_duration:
        d.rounded_rectangle((65,340,1015,635),radius=34,fill=(9,14,24,235))
        centered(d,spec['question'],(95,365,985,600),75,'white')
        for i, opt in enumerate(spec['options']):
            y=675+i*151
            d.rounded_rectangle((70,y,1010,y+127),radius=29,fill=(25,34,49,239),outline=(110,125,140,220),width=2)
            centered(d,f'{chr(65+i)}. {opt}',(105,y+8,975,y+119),64,'white')
        remaining=max(0,math.ceil(question_duration-t))
        d.rounded_rectangle((330,1433,750,1580),radius=42,fill=(10,14,20,235))
        centered(d,f'{remaining}',(350,1445,730,1565),100,GREEN)
    else:
        correct=spec['correct_index']
        d.rounded_rectangle((65,390,1015,595),radius=38,fill=(10,20,20,245),outline=(75,234,144,255),width=6)
        centered(d,'CORRECT ANSWER',(100,420,980,565),78,GREEN)
        d.rounded_rectangle((65,660,1015,945),radius=38,fill=(20,40,29,245),outline=(75,234,144,255),width=6)
        centered(d,f'{chr(65+correct)}. {spec["options"][correct]}',(100,705,980,900),90,'white')
        d.rounded_rectangle((65,990,1015,1160),radius=30,fill=(10,14,24,232))
        centered(d,spec['explanation'],(100,1010,980,1135),52,'white')
    d.rectangle((0,H-16,int(W*min(1,t/total)),H),fill=(77,235,146,255))
    return im

def main():
    if len(sys.argv)!=3:
        raise SystemExit('Usage: python trivia_render.py jobs/trivia/spec.json render_output')
    path=Path(sys.argv[1]).resolve(); spec=json.loads(path.read_text())
    out=Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True)
    audio,qd,ad,total=generate_audio(spec,out)
    bg=make_background(spec,path.parent)
    # One image per second gives the visible countdown, with no text stretching.
    frames=out/'frames';frames.mkdir(exist_ok=True)
    playlist=out/'slides.txt'
    with playlist.open('w') as f:
        for second in range(total):
            name=f'frame-{second:03}.png'
            frame(spec,bg,second+0.01,qd,total).save(frames/name)
            f.write(f"file 'frames/{name}'\n")
            f.write('duration 1\n')
        f.write(f"file 'frames/frame-{total-1:03}.png'\n")
    mp4=out/(spec['slug']+'.mp4')
    cmd=['ffmpeg','-y','-hide_banner','-loglevel','error','-f','concat','-safe','0','-i',str(playlist),'-i',str(audio),'-vf',f'fps=30,scale={W}:{H}:flags=lanczos,format=yuv420p','-c:v','libx264','-preset','medium','-crf','22','-c:a','aac','-b:a','160k','-movflags','+faststart','-t',str(total),str(mp4)]
    subprocess.run(cmd,check=True)
    print('Rendered:',mp4, 'duration:',total)

if __name__=='__main__':
    main()
