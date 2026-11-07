#!/usr/bin/env python3
"""Generate a 9:16 technology comparison Short with local graphics, TTS and original music.
Needs: Pillow, numpy, kokoro-onnx, ffmpeg, ffprobe, espeak-ng. No external image/text API.
"""
import argparse
import json
import math
import os
import random
import shutil
import subprocess
import tempfile
import urllib.request
import urllib.error
import time
import wave

from kokoro_onnx import Kokoro
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H = 720, 1280
SR = 24000
FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
BOLD = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
BACKGROUND = (12, 20, 35)
OLD = (255, 170, 91)
NEW = (105, 235, 210)



KOKORO_RELEASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1"
KOKORO_FILES = {"kokoro-v1.0.int8.onnx": 50_000_000, "voices-v1.0.bin": 5_000_000}


def ensure_kokoro_models(directory):
    """Download the public Kokoro model files to one stable, cached directory.

    Download into temporary files so interrupted downloads aren't cached as valid
    models. File-size checks catch HTTP error pages or partial downloads.
    """
    directory = Path(directory).expanduser().resolve()
    directory.mkdir(parents=True, exist_ok=True)
    for name, min_bytes in KOKORO_FILES.items():
        target = directory / name
        if target.is_file() and target.stat().st_size >= min_bytes:
            print(f"Kokoro cache OK: {target} ({target.stat().st_size:,} bytes)", flush=True)
            continue
        if target.exists():
            print(f"Invalid/incomplete cached file: {target}; replacing", flush=True)
            target.unlink()
        source_url = f"{KOKORO_RELEASE}/{name}"
        last_error = None
        for attempt in range(1, 4):
            temporary = directory / f".{name}.download"
            try:
                print(f"Downloading Kokoro {name} (attempt {attempt}/3)", flush=True)
                req = urllib.request.Request(source_url, headers={"User-Agent": "Kokoro-Shorts/1.0"})
                with urllib.request.urlopen(req, timeout=120) as response, temporary.open("wb") as output:
                    shutil.copyfileobj(response, output, length=1024 * 1024)
                actual = temporary.stat().st_size
                if actual < min_bytes:
                    raise RuntimeError(f"Model download too small: {actual:,} bytes")
                temporary.replace(target)
                print(f"Saved {target} ({actual:,} bytes)", flush=True)
                break
            except (OSError, urllib.error.URLError, TimeoutError, RuntimeError) as exc:
                last_error = exc
                temporary.unlink(missing_ok=True)
                if attempt < 3:
                    time.sleep(2 * attempt)
        else:
            raise RuntimeError(
                f"Could not download {name} from {source_url}: {last_error}. "
                f"Check network access or download it manually into {directory}"
            )
    return directory / "kokoro-v1.0.int8.onnx", directory / "voices-v1.0.bin"


def run(*argv):
    subprocess.run(list(map(str, argv)), check=True, stdout=subprocess.DEVNULL)


def font(size, bold=False):
    return ImageFont.truetype(BOLD if bold else FONT, size)


def lines(draw, text, f, max_width):
    words = text.split()
    output, current = [], ''
    for word in words:
        trial = (current + ' ' + word).strip()
        if current and draw.textbbox((0, 0), trial, font=f)[2] > max_width:
            output.append(current)
            current = word
        else:
            current = trial
    if current:
        output.append(current)
    return output


def centered(draw, text, y, size, color, width=630, gap=8):
    f = font(size, True)
    for row in lines(draw, text, f, width):
        bbox = draw.textbbox((0, 0), row, font=f)
        draw.text(((W - (bbox[2] - bbox[0])) / 2, y), row, font=f, fill=color)
        y += size + gap
    return y


def icon(draw, symbol, rect, accent, old=False):
    x0, y0, x1, y1 = rect
    cx = (x0 + x1) // 2
    cy = (y0 + y1) // 2
    width = x1-x0
    if symbol in ('phone', 'message'):
        if old:
            draw.rounded_rectangle((cx-82, cy-100, cx+82,cy+120), 20, fill=(43,49,62),outline=accent,width=5)
            draw.rounded_rectangle((cx-58,cy-60,cx+58,cy-3),9,fill=(176,185,158))
            for r in range(3):
                for c in range(3):
                    draw.rounded_rectangle((cx-50+c*37,cy+15+r*31,cx-26+c*37,cy+35+r*31),5,fill=accent)
            draw.line((cx-60,cy-100,cx-60,cy-158),fill=accent,width=10)
        else:
            draw.rounded_rectangle((cx-75,cy-150,cx+75,cy+150),25,fill=(16,23,40),outline=accent,width=7)
            draw.rounded_rectangle((cx-59,cy-114,cx+59,cy+114),12,fill=(34,92,102))
            for xx,yy in ((-32,-70),(18,-70),(-32,-14),(18,-14),(-32,42),(18,42)):
                draw.rounded_rectangle((cx+xx,cy+yy,cx+xx+30,cy+yy+30),8,fill=accent)
    elif symbol in ('camera',):
        draw.rounded_rectangle((cx-125,cy-62,cx+125,cy+88),25,fill=(35,45,60),outline=accent,width=6)
        draw.ellipse((cx-78,cy-52,cx+78,cy+100),fill=(17,28,48),outline=accent,width=9)
        draw.ellipse((cx-42,cy-16,cx+42,cy+66),fill=(47,100,116),outline=(233,244,245),width=5)
        draw.rounded_rectangle((cx-80,cy-94,cx-15,cy-61),8,fill=accent)
    elif symbol in ('computer','typing','keyboard','gaming','game'):
        if old:
            draw.rounded_rectangle((cx-134,cy-102,cx+134,cy+73),13,fill=(40,47,58),outline=accent,width=7)
            draw.rectangle((cx-110,cy-78,cx+110,cy+45),fill=(56,92,95))
            draw.rectangle((cx-16,cy+74,cx+16,cy+113),fill=accent)
            draw.rounded_rectangle((cx-104,cy+106,cx+104,cy+131),8,fill=accent)
        else:
            draw.rounded_rectangle((cx-138,cy-105,cx+138,cy+73),12,fill=(27,38,58),outline=accent,width=6)
            draw.rectangle((cx-120,cy-87,cx+120,cy+53),fill=(43,100,111))
            draw.polygon([(cx-148,cy+75),(cx+148,cy+75),(cx+173,cy+110),(cx-173,cy+110)],fill=accent)
    elif symbol in ('music','storage'):
        if old:
            draw.rounded_rectangle((cx-110,cy-110,cx+110,cy+110),18,fill=(43,50,60),outline=accent,width=6)
            for xo in (-53,53):
                draw.ellipse((cx+xo-38,cy-52,cx+xo+38,cy+24),outline=accent,width=8)
                draw.ellipse((cx+xo-10,cy-24,cx+xo+10,cy-4),fill=accent)
            draw.rectangle((cx-66,cy+40,cx+66,cy+73),fill=(111,130,137))
        else:
            draw.ellipse((cx-109,cy-109,cx+109,cy+109),outline=accent,width=6)
            draw.line((cx+24,cy-75,cx+24,cy+51),fill=accent,width=13)
            draw.line((cx+24,cy-75,cx+95,cy-88),fill=accent,width=13)
            draw.ellipse((cx-19,cy+35,cx+35,cy+84),fill=accent)
    elif symbol in ('tv', 'television'):
        draw.rounded_rectangle((cx-150,cy-90,cx+150,cy+100),15 if old else 5,fill=(34,47,60),outline=accent,width=8)
        draw.rectangle((cx-126,cy-66,cx+126,cy+76),fill=(37,105,124))
        if old:
            draw.line((cx-60,cy-90,cx-118,cy-155),fill=accent,width=5)
            draw.line((cx+60,cy-90,cx+118,cy-155),fill=accent,width=5)
    elif symbol == 'map':
        draw.polygon([(cx-144,cy-86),(cx-52,cy-121),(cx+50,cy-80),(cx+140,cy-118),(cx+140,cy+86),(cx+50,cy+125),(cx-52,cy+82),(cx-144,cy+118)],fill=(37,66,77),outline=accent,width=6)
        draw.line((cx-52,cy-121,cx-52,cy+82),fill=accent,width=4)
        draw.line((cx+50,cy-80,cx+50,cy+125),fill=accent,width=4)
        if not old:
            draw.ellipse((cx-28,cy-80,cx+28,cy-24),fill=accent)
            draw.polygon([(cx-23,cy-38),(cx+23,cy-38),(cx,cy+28)],fill=accent)
    elif symbol == 'watch':
        draw.rounded_rectangle((cx-46,cy-160,cx+46,cy+160),20,fill=(53,61,74),outline=accent,width=5)
        draw.ellipse((cx-98,cy-95,cx+98,cy+95),fill=(27,43,56),outline=accent,width=9)
        draw.line((cx,cy,cx,cy-58),fill=accent,width=8)
        draw.line((cx,cy,cx+47,cy+16),fill=accent,width=8)
    else:
        draw.ellipse((cx-100,cy-100,cx+100,cy+100),outline=accent,width=10)
        draw.ellipse((cx-22,cy-22,cx+22,cy+22),fill=accent)


def background(draw):
    for y in range(H):
        k = y/H
        draw.line((0,y,W,y),fill=(int(11+k*8),int(19+k*12),int(36+k*13)))
    for i in range(0,11):
        draw.line((i*85-140,0,i*85+240,H),fill=(21,36,57),width=1)


def card(draw, rect, heading, sub, accent, symbol, old):
    x0,y0,x1,y1=rect
    draw.rounded_rectangle(rect,36,fill=(24,37,55),outline=(54,68,88),width=3)
    draw.rounded_rectangle((x0+22,y0+19,x0+170,y0+65),22,fill=(60,47,41) if old else (25,72,69))
    draw.text((x0+42,y0+27),heading,font=font(24,True),fill=accent)
    centered(draw,sub,y0+80,27,(235,242,248),width=x1-x0-65)
    # Draw the technology icon separately, then scale to fit below the label.
    # This keeps tall device antennas/phones clear of the text.
    icon_layer = Image.new('RGBA',(400,400),(0,0,0,0))
    icon_draw = ImageDraw.Draw(icon_layer)
    icon(icon_draw,symbol,(0,0,400,400),accent,old)
    icon_layer = icon_layer.resize((246,246),Image.Resampling.LANCZOS)
    draw._image.paste(icon_layer,(int((W-246)/2),int(y0+126)),icon_layer)


def draw_frame(topic, scene, index, total, path):
    image=Image.new('RGB',(W,H),BACKGROUND)
    d=ImageDraw.Draw(image)
    background(d)
    d.rounded_rectangle((43,37,333,92),22,fill=(31,61,79))
    d.text((64,48),'TECH EVOLUTION',font=font(25,True),fill=(205,247,243))
    centered(d, topic['topic'].upper(),138,49,(247,250,255),620)
    centered(d,'THEN  /  NOW',222,26,(158,183,206),620)
    card(d,(45,322,675,705),'THEN · '+topic['then_year'],topic['then'],OLD,topic['symbol'],True)
    card(d,(45,725,675,1108),'NOW · '+topic['now_year'],topic['now'],NEW,topic['symbol'],False)
    # Emphasize the current part of the explanation, without blocking artwork.
    if scene == 1:
        d.rounded_rectangle((48,322,672,704),36,outline=OLD,width=8)
    elif scene == 2:
        d.rounded_rectangle((48,725,672,1105),36,outline=NEW,width=8)
    elif scene == 3:
        d.text((W//2-29,696),'↓',font=font(55,True),fill=NEW)
    title = ['A BIG TRANSFORMATION', 'THE OLD WAY', 'THE MODERN WAY', 'WHAT CHANGED?', 'WHAT DO YOU THINK?'][scene]
    centered(d,title,1137,32,(240,245,250),630)
    d.rounded_rectangle((65,1226,655,1235),4,fill=(52,68,83))
    d.rounded_rectangle((65,1226,65+int(590*(index+1)/total),1235),4,fill=NEW)
    image.save(path)


def synthesized_music(length):
    n=round(length*SR)
    out=np.zeros(n,np.float32)
    # Original ambient plucks, no commercial music samples.
    notes=(164.81,196.00,246.94,293.66,220.00,196.00,164.81,146.83)
    for i,t in enumerate(np.arange(0,length,0.5)):
        start=int(t*SR)
        dur=min(int(0.39*SR),n-start)
        if dur<=0:break
        tt=np.arange(dur)/SR
        envelope=(1-np.exp(-tt*90))*np.exp(-tt*7)
        tone=(np.sin(2*np.pi*notes[i%len(notes)]*tt)+0.22*np.sin(4*np.pi*notes[i%len(notes)]*tt))
        out[start:start+dur]+=0.055*tone*envelope
    return out


def wav_write(path,values):
    values=np.clip(values,-.95,.95)
    with wave.open(str(path),'wb') as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(SR)
        f.writeframes((values*32767).astype(np.int16).tobytes())


def wav_read(path):
    with wave.open(str(path),'rb') as f:
        if f.getframerate()!=SR or f.getnchannels()!=1 or f.getsampwidth()!=2:
            raise ValueError('Narration WAV must be 24kHz mono s16')
        return np.frombuffer(f.readframes(f.getnframes()),dtype=np.int16).astype(np.float32)/32768


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--topics',default=str(Path(__file__).with_name('topics.json')))
    p.add_argument('--output',default='output.mp4')
    p.add_argument('--metadata',default='tech_metadata.json')
    p.add_argument('--seed',type=int,default=None)
    p.add_argument('--topic',default='auto',help='auto or topic ID from topics.json')
    p.add_argument('--voice',default=os.getenv('KOKORO_VOICE', 'am_puck'))
    p.add_argument('--voice-speed',type=float,default=float(os.getenv('KOKORO_SPEED', '1.08')))
    p.add_argument('--ensure-model',action='store_true',help='Download/verify Kokoro files then exit')
    args=p.parse_args()
    # The action and the renderer share the same stable cache location.
    model_dir = Path(os.getenv('KOKORO_DIR') or (Path.home() / '.cache' / 'kokoro'))
    model_file, voices_file = ensure_kokoro_models(model_dir)
    if args.ensure_model:
        print(f'Kokoro files ready in {model_file.parent}', flush=True)
        return
    for executable in ('ffmpeg','ffprobe'):
        if not shutil.which(executable):
            raise SystemExit(f'Missing required executable: {executable}')
    topics=json.loads(Path(args.topics).read_text())
    run_number=os.getenv('GITHUB_RUN_NUMBER','')
    if args.topic=='auto':
        if args.seed is not None:
            chosen=topics[random.Random(args.seed).randrange(len(topics))]
        elif run_number.isdigit():
            chosen=topics[(int(run_number)-1)%len(topics)]
        else:
            chosen=random.SystemRandom().choice(topics)
    else:
        chosen=next((x for x in topics if x['id']==args.topic),None)
        if chosen is None:raise SystemExit('Unknown topic: '+args.topic)
    # Offline Kokoro neural text-to-speech (voice is selectable in Actions).
    if not (0.65 <= args.voice_speed <= 1.6):
        raise SystemExit('Voice speed must be between 0.65 and 1.6')
    kokoro=Kokoro(str(model_file),str(voices_file))

    spoken=[
        f'{chosen["topic"]}, then versus now. How much has technology changed?',
        chosen['fact'],
        chosen['change'],
        chosen['takeaway'],
        'Which technology should we compare next? Tell us in the comments!',
    ]
    output=Path(args.output).resolve()
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='tech_short_') as td:
        temp=Path(td)
        images=[]
        timings=[]
        narrations=[]
        for index,text in enumerate(spoken):
            frame=temp/f'frame{index:02}.png'
            draw_frame(chosen,index,index,len(spoken),frame)
            images.append(frame)
            try:
                samples, sample_rate = kokoro.create(
                    text, voice=args.voice, speed=args.voice_speed, lang='en-us'
                )
            except Exception as exc:
                raise RuntimeError(f'Kokoro failed for narration {index+1}: {exc}') from exc
            audio=np.asarray(samples,dtype=np.float32).reshape(-1)
            if sample_rate != SR:
                # Resample through FFmpeg to avoid another Python dependency.
                raw=temp/f'kokoro{index:02}.f32'
                speech=temp/f'speech{index:02}.wav'
                audio.tofile(raw)
                run('ffmpeg','-y','-loglevel','error','-f','f32le','-ar',str(sample_rate),
                    '-ac','1','-i',raw,'-ar',str(SR),'-ac','1','-acodec','pcm_s16le',speech)
                audio=wav_read(speech)
            if len(audio)==0 or not np.isfinite(audio).all():
                raise RuntimeError(f'Kokoro produced invalid audio for narration {index+1}')
            narrations.append(audio)
            timings.append(max(4.3,len(audio)/SR+0.8))
        duration=sum(timings)
        audio=synthesized_music(duration)
        pos=0
        for i,(voice,seconds) in enumerate(zip(narrations,timings)):
            at=int((pos+.18)*SR)
            length=min(len(voice),len(audio)-at)
            audio[at:at+length]+=voice[:length]*.88
            # Brief transition click; no clips from copyrighted recordings.
            if i:
                t0=int(pos*SR)
                length=min(1800,len(audio)-t0)
                tt=np.arange(length)/SR
                audio[t0:t0+length]+=0.10*np.sin(2*np.pi*620*tt)*np.exp(-tt*48)
            pos+=seconds
        wav=temp/'mix.wav'
        wav_write(wav,audio)
        concat=temp/'frames.txt'
        with concat.open('w') as f:
            for file,seconds in zip(images,timings):
                f.write('file '+str(file)+'\n')
                f.write(f'duration {seconds:.6f}\n')
            f.write('file '+str(images[-1])+'\n')
        run('ffmpeg','-y','-loglevel','error','-f','concat','-safe','0','-i',concat,
            '-i',wav,'-vf','fps=24,format=yuv420p','-c:v','libx264','-preset','veryfast','-crf','21',
            '-c:a','aac','-b:a','160k','-shortest','-movflags','+faststart',output)
    if not output.is_file() or output.stat().st_size<10000:
        raise SystemExit('Video generation failed')
    data={'topic_id':chosen['id'],'topic':chosen['topic'],'then':chosen['then'],
          'now':chosen['now'],'title':f'{chosen["topic"]}: Then vs Now! #Shorts',
          'description':f'{chosen["topic"]}: {chosen["then"]} vs {chosen["now"]}.\n\n'
           f'{chosen["fact"]} {chosen["change"]}\n\n{chosen["takeaway"]}\n\n'
           '#Shorts #Technology #ThenVsNow #TechHistory',
          'duration_seconds':round(duration,2),'run_number':run_number,'video':str(output.name),
          'narration_engine':'Kokoro ONNX','voice':args.voice,'voice_speed':args.voice_speed}
    Path(args.metadata).write_text(json.dumps(data,indent=2)+'\n')
    print(json.dumps(data,indent=2))
    print('Video generated:',output,output.stat().st_size,'bytes')

if __name__=='__main__':
    main()
