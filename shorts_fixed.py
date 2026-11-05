# usage: python3 shorts.py spec.json outdir
# Assembles a 9:16 Short from Flow clips + Flow stills: camera moves on stills, punch/whip/flash transitions,
# free Kokoro narration, word-by-word captions, a light comedy music bed, whooshes/pops, loop-friendly ending.
import sys, os, json, subprocess, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

if len(sys.argv) != 3:
    raise SystemExit('Usage: python3 shorts.py spec.json outdir')
with open(sys.argv[1], encoding='utf-8') as stream:
    spec = json.load(stream)
OUT = sys.argv[2]
os.makedirs(OUT, exist_ok=True)
BASE = os.path.dirname(os.path.abspath(sys.argv[1]))
W, H = (1920, 1080) if spec.get('aspect') == '16:9' else (1080, 1920)
FPS, SR = 30, 24000
LAND = W > H
def P(p): return p if os.path.isabs(p) else os.path.join(BASE, p)

# ---------------------------------------------------------------- narration (free, offline)
from kokoro_onnx import Kokoro
TTSDIR = os.environ.get('KOKORO_DIR', os.path.expanduser('~/factory/tts'))
K = Kokoro(os.path.join(TTSDIR, 'kokoro-v1.0.int8.onnx'), os.path.join(TTSDIR, 'voices-v1.0.bin'))
VOICE, SPEED = spec.get('voice', 'am_puck'), float(spec.get('speed', 1.05))
def tts(text):
    a, sr = K.create(text, voice=VOICE, speed=SPEED, lang='en-us')
    a = np.asarray(a, np.float32)
    if sr != SR:
        from scipy.signal import resample_poly; a = resample_poly(a, SR, sr).astype(np.float32)
    nz = np.where(np.abs(a) > 0.01)[0]
    if len(nz): a = a[max(0, nz[0] - 200): nz[-1] + 1200]
    return a

def probe_dur(p):
    return float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', p]).decode().strip())

# ---------------------------------------------------------------- timeline
segs = []; t = 0.0; voice_events = []  # (start, audio, text)
for sg in spec['segments']:
    lines = sg.get('narration') or []
    if isinstance(lines, str): lines = [lines]
    clips = [(tts(x), x) for x in lines]
    if sg['type'] == 'clip':
        a, b = sg.get('trim', [0, None]); full = probe_dur(P(sg['path'])); b = b if b is not None else full
        dur = b - a; vt = t + sg.get('narration_start', 0.15)
        for au, tx in clips:
            voice_events.append((vt, au, tx)); vt += len(au) / SR + sg.get('gap', 0.25)
    else:
        need = sum(len(au) / SR for au, _ in clips) + 0.25 * max(0, len(clips) - 1) + sg.get('pad', 0.45)
        dur = max(sg.get('min', 2.4), need); vt = t + 0.12
        for au, tx in clips:
            voice_events.append((vt, au, tx)); vt += len(au) / SR + 0.25
        a, b = 0, dur
    segs.append(dict(sg, start=t, dur=dur, a=a))
    t += dur
TOTAL = t
print('total', round(TOTAL, 2), 's', [round(s['dur'], 2) for s in segs])

# ---------------------------------------------------------------- frames per segment
def cover(img, w, h):
    """Fill a canvas while preserving aspect ratio (used only for soft background)."""
    scale = max(w / img.width, h / img.height)
    resized = img.resize((math.ceil(img.width * scale), math.ceil(img.height * scale)), Image.Resampling.LANCZOS)
    left = (resized.width - w) // 2
    top = (resized.height - h) // 2
    return resized.crop((left, top, left + w, top + h))


def fit_image(img, w, h):
    """Show the ENTIRE source image without stretching or cutting subjects off."""
    img = img.convert('RGB')
    # A softly blurred full-canvas background eliminates black bars.
    canvas = cover(img, w, h).filter(ImageFilter.GaussianBlur(45))
    canvas = Image.blend(canvas, Image.new('RGB', (w, h), (18, 18, 24)), .32)
    scale = min(w / img.width, h / img.height)
    fw, fh = max(1, round(img.width * scale)), max(1, round(img.height * scale))
    foreground = img.resize((fw, fh), Image.Resampling.LANCZOS)
    canvas.paste(foreground, ((w - fw) // 2, (h - fh) // 2))
    return canvas


def ease(x):
    x = min(1, max(0, x))
    return x * x * (3 - 2 * x)

_still = {}

def still_frame(sg, lt):
    """Gentle zoom/pan on a correctly proportioned canvas."""
    key = sg['path']
    if key not in _still:
        with Image.open(P(key)) as src:
            _still[key] = fit_image(src, W, H)
    image = _still[key]
    progress = ease(lt / max(float(sg['dur']), .001))
    movement = sg.get('move', 'zoom_in')

    # Limit zoom to 4%; the full composition stays visible.
    factor = 1.0 + 0.04 * progress if movement == 'zoom_in' else (1.04 - 0.04 * progress if movement == 'zoom_out' else 1.015)
    crop_w, crop_h = W / factor, H / factor
    room_x, room_y = (W - crop_w) / 2, (H - crop_h) / 2
    cx, cy = W / 2, H / 2
    if movement == 'pan_left': cx += room_x * (1 - 2 * progress)
    elif movement == 'pan_right': cx += room_x * (2 * progress - 1)
    elif movement == 'pan_up': cy += room_y * (1 - 2 * progress)
    elif movement == 'pan_down': cy += room_y * (2 * progress - 1)
    focus_x, focus_y = sg.get('focus', [0.5, 0.5])
    cx += (float(focus_x) - .5) * 2 * room_x
    cy += (float(focus_y) - .5) * 2 * room_y
    cx = max(crop_w / 2, min(W - crop_w / 2, cx))
    cy = max(crop_h / 2, min(H - crop_h / 2, cy))
    box = (cx - crop_w / 2, cy - crop_h / 2, cx + crop_w / 2, cy + crop_h / 2)
    return np.asarray(image.resize((W, H), Image.Resampling.BICUBIC, box=box))

class ClipReader:
    def __init__(self, sg):
        self.p = subprocess.Popen(['ffmpeg', '-loglevel', 'error', '-ss', str(sg['a']), '-t', str(sg['dur']), '-i', P(sg['path']),
            '-vf', f'scale={W}:{H}:flags=lanczos:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},unsharp=5:5:0.6', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], stdout=subprocess.PIPE)
        self.last = None
    def get(self):
        b = self.p.stdout.read(W * H * 3)
        if len(b) == W * H * 3: self.last = np.frombuffer(b, np.uint8).reshape(H, W, 3)
        return self.last if self.last is not None else np.zeros((H, W, 3), dtype=np.uint8)

def zoom(a, z):
    cw, ch = int(W / z), int(H / z); x0, y0 = (W - cw) // 2, (H - ch) // 2
    return np.asarray(Image.fromarray(a[y0:y0 + ch, x0:x0 + cw]).resize((W, H), Image.BICUBIC))
def hblur(a, amount, shift):
    f = a.astype(np.float32); acc = np.zeros_like(f); k = 9
    for j in range(k): acc += np.roll(f, int(shift + (j - k // 2) * amount / k), axis=1)
    return (acc / k).astype(np.uint8)
def mix(a, b, t): return (a.astype(np.float32) * (1 - t) + b.astype(np.float32) * t).astype(np.uint8)

# ---------------------------------------------------------------- captions (word by word)
FONT = next((f for f in [os.environ.get('CAPTION_FONT', ''), '/usr/share/fonts/truetype/google-fonts/Poppins-Black.ttf', '/usr/share/fonts/truetype/google-fonts/Poppins-ExtraBold.ttf', '/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'] if f and os.path.exists(f)))
_f = {}
def font(px):
    px = int(px); _f.setdefault(px, ImageFont.truetype(FONT, px)); return _f[px]
cues = []
for st, au, tx in voice_events:
    ws = tx.split(); d = len(au) / SR
    for i in range(0, len(ws), 3):  # chunks of up to 3 words
        ch = ws[i:i + 3]; tot = sum(len(w) + 1 for w in ws); pre = sum(len(w) + 1 for w in ws[:i]); n = sum(len(w) + 1 for w in ch)
        t0 = st + d * pre / tot; t1 = st + d * (pre + n) / tot
        wt = []; tt = t0
        for w in ch: dd = (t1 - t0) * (len(w) + 1) / n; wt.append((tt, tt + dd, w)); tt += dd
        cues.append((t0, t1 + 0.05, wt))
def draw_caps(a, t):
    """Measured, bounded, centered captions; highlighted words never overlap."""
    cue = next((c for c in cues if c[0] <= t < c[1]), None)
    if cue is None:
        return a
    t0, t1, items = cue
    active = next((i for i, (start, end, _) in enumerate(items) if start <= t < end), len(items) - 1)
    words = [w.upper() for _, _, w in items]
    img = Image.fromarray(a)
    dr = ImageDraw.Draw(img)
    max_width = int(W * (.76 if LAND else .79))
    max_height = int(H * (.20 if LAND else .17))
    font_px = 65 if LAND else 86
    spacing = 16 if LAND else 19
    stroke = 5 if LAND else 6

    def layout(fs):
        nonlocal spacing
        f = font(fs)
        gap = max(8, int(fs * .24))
        lines, line = [], []
        for idx, word in enumerate(words):
            width = dr.textbbox((0, 0), word, font=f, stroke_width=stroke)[2]
            candidate = line + [(idx, word, width)]
            total = sum(x[2] for x in candidate) + gap * (len(candidate) - 1)
            if line and total > max_width:
                lines.append(line)
                line = [(idx, word, width)]
            else:
                line = candidate
        if line:
            lines.append(line)
        line_height = int(fs * 1.48)
        overall_w = max(sum(x[2] for x in line) + gap * (len(line) - 1) for line in lines)
        overall_h = line_height * len(lines)
        return f, gap, lines, overall_w, overall_h, line_height

    while True:
        f, gap, lines, text_w, text_h, line_height = layout(font_px)
        if (text_w <= max_width and text_h <= max_height and len(lines) <= 3) or font_px <= 30:
            break
        font_px -= 3
    # Place captions below the action, away from social-app buttons.
    center_y = int(H * (.81 if LAND else .72))
    y = max(50, min(H - text_h - 230, center_y - text_h // 2))
    for line in lines:
        line_w = sum(x[2] for x in line) + gap * (len(line) - 1)
        x = (W - line_w) / 2
        for idx, word, width in line:
            # The same font size is used for all words, preventing baseline jumps.
            dr.text((round(x), round(y)), word, font=f,
                    fill=(255, 219, 75) if idx == active else (255, 255, 255),
                    stroke_width=stroke, stroke_fill=(10, 10, 12))
            x += width + gap
        y += line_height
    return np.asarray(img)

# ---------------------------------------------------------------- audio
N = int(TOTAL * SR) + SR; rng = np.random.default_rng(5)
voice = np.zeros(N, np.float32); fx = np.zeros(N, np.float32); clipa = np.zeros(N, np.float32); musicmask = np.zeros(N, np.float32)
for st, au, _ in voice_events: i = int(st * SR); voice[i:i + len(au)] += au[:N - i]
def whoosh(n):
    tt = np.arange(n) / SR; nz = rng.normal(0, 1, n).astype(np.float32)
    from scipy.signal import lfilter
    out = np.zeros(n, np.float32)
    for k, a in enumerate(np.linspace(0.6, 0.97, 6)):
        seg = slice(k * n // 6, (k + 1) * n // 6); out[seg] = lfilter([1 - a], [1, -a], nz[seg])
    return out * np.sin(np.pi * tt / tt[-1]) ** 2 * 2.2
def pop():
    n = int(0.12 * SR); tt = np.arange(n) / SR; return (np.sin(2 * np.pi * (900 - 2500 * tt) * tt) * np.exp(-tt * 40) * 0.35).astype(np.float32)
for sg in segs:
    i = int(sg['start'] * SR); n = int(sg['dur'] * SR)
    if sg['type'] == 'clip':
        try:
            raw = subprocess.check_output(['ffmpeg', '-loglevel', 'error', '-ss', str(sg['a']), '-t', str(sg['dur']), '-i', P(sg['path']), '-vn', '-ac', '1', '-ar', str(SR), '-f', 'f32le', '-'], stderr=subprocess.DEVNULL)
            ca = np.frombuffer(raw, np.float32) * float(sg.get('clip_audio', 1.0))
            valid = max(0, min(len(ca), N-i))
            clipa[i:i + valid] += ca[:valid]
        except subprocess.CalledProcessError:
            print('WARNING: no usable audio for clip', sg['path'])
        if sg.get('music_under'): musicmask[i:i + n] = 0.5
    else:
        musicmask[i:i + n] = 1.0
        if sg.get('sfx', 'pop') == 'pop': p = pop(); fx[i + 1200:i + 1200 + len(p)] += p
    tr = sg.get('transition', 'cut')
    if sg['start'] > 0 and tr in ('punch', 'whip'): w = whoosh(int(0.4 * SR)); j = max(0, i - int(0.28 * SR)); fx[j:j + len(w)] += w * 0.5
    if tr == 'flash': p = pop() * 1.5; fx[i:i + len(p)] += p
def comedy_bed(n):
    # bouncy pizzicato loop (original, synthesized): bass on beats, plucked melody on off-beats
    bpm = 118; beat = 60 / bpm; out = np.zeros(n, np.float32)
    notes = [261.6, 329.6, 392.0, 440.0, 392.0, 329.6, 293.7, 349.2]; bass = [130.8, 130.8, 174.6, 196.0]
    def pluck(f, d, amp):
        m = int(d * SR); tt = np.arange(m) / SR
        return amp * (np.sin(2 * np.pi * f * tt) + 0.35 * np.sin(4 * np.pi * f * tt)) * np.exp(-tt * 9)
    k = 0; tt = 0.0
    while tt < n / SR:
        i = int(tt * SR); b = pluck(bass[(k // 4) % 4], beat, 0.22); out[i:i + len(b)] += b[:n - i]
        j = int((tt + beat / 2) * SR); m2 = pluck(notes[(k * 3) % 8] * (2 if k % 8 == 7 else 1), beat * 0.5, 0.12)
        if j < n: out[j:j + len(m2)] += m2[:n - j]
        tt += beat; k += 1
    return out
mus = comedy_bed(N) * float(spec.get('music_gain', 0.55))
env = np.convolve(np.abs(voice), np.ones(4800) / 4800, mode='same'); duck = 1 - 0.6 * np.clip(env * 12, 0, 1)
cenv = np.convolve(musicmask, np.ones(4800) / 4800, mode='same')  # smooth music in/out
mixd = voice * 1.0 + fx * 0.8 + clipa * np.where(env > 0.01, 0.55, 1.0) + mus * cenv * duck
mixd = mixd[:int(TOTAL * SR)]; mixd = mixd / max(1e-6, np.abs(mixd).max()) * 0.95
import wave
wav = os.path.join(OUT, spec['slug'] + '_mix.wav')
with wave.open(wav, 'wb') as wf: wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(SR); wf.writeframes((mixd * 32767).astype(np.int16).tobytes())

# ---------------------------------------------------------------- video
mp4 = os.path.join(OUT, spec['slug'] + '.mp4')
ff = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-', '-i', wav,
                       '-af', 'loudnorm=I=-14:TP=-1.5:LRA=11', '-c:v', 'libx264', '-preset', 'medium', '-crf', '17', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-ar', '48000',
                       '-shortest', '-movflags', '+faststart', mp4], stdin=subprocess.PIPE)
nfr = int(round(TOTAL * FPS))
for si, sg in enumerate(segs):
    f0, f1 = int(round(sg['start'] * FPS)), int(round((sg['start'] + sg['dur']) * FPS)); rd = ClipReader(sg) if sg['type'] == 'clip' else None
    nxt = segs[si + 1] if si + 1 < len(segs) else None
    for fi in range(f0, min(f1, nfr)):
        lt = (fi - f0) / FPS; li = fi - f0; left = f1 - fi
        a = rd.get() if rd else still_frame(sg, lt)
        mb = sg.get('beat_at')  # optional punch-in at a moment inside a still (e.g. on the joke word)
        if mb is not None and 0 <= lt - mb < 0.25: a = zoom(a, 1 + 0.07 * (1 - (lt - mb) / 0.25))
        tr = sg.get('transition', 'cut')
        if fi > 0:
            if tr == 'punch' and li < 7: a = zoom(a, 1 + 0.12 * (1 - li / 7) ** 2)
            if tr == 'whip' and li < 5: q = 1 - li / 5; a = hblur(a, W * 0.12 * q, W * 0.18 * q * q)
            if tr == 'flash' and li < 6: a = mix(a, np.full_like(a, 255), 0.8 * (1 - li / 6) ** 1.5)
        if nxt and nxt.get('transition') == 'whip' and left <= 5: q = (6 - left) / 5; a = hblur(a, W * 0.12 * q, -W * 0.18 * q * q)
        a = draw_caps(np.ascontiguousarray(a), fi / FPS)
        ff.stdin.write(np.ascontiguousarray(a).tobytes())
    if rd: rd.p.kill()
ff.stdin.close(); ff.wait(); print(mp4, round(TOTAL, 2))
