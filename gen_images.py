"""Generate FLUX.1 Schnell illustrations, then make correctly proportioned 9:16 or 16:9 PNGs.
Usage: python3 gen_images_fixed.py job_dir
Requires CF_ACCOUNT_ID and CF_API_TOKEN. Existing images are left untouched.
"""
import os
import sys
import json
import glob
import time
import base64
import io
import urllib.request
import urllib.error
from pathlib import Path
from PIL import Image, ImageFilter, ImageDraw, ImageFont
def create_fallback_image(path, aspect="9:16"):
    """Create a neutral trivia illustration when generation is blocked."""
    width, height = (1920, 1080) if aspect == "16:9" else (1080, 1920)

    im = Image.new("RGB", (width, height), (15, 23, 42))
    draw = ImageDraw.Draw(im)

    cx, cy = width // 2, height // 2

    # Decorative trivia symbol
    radius = min(width, height) // 6

    draw.ellipse(
        (cx-radius, cy-radius, cx+radius, cy+radius),
        fill=(30, 45, 70),
        outline=(34, 197, 94),
        width=12
    )

    try:
        font = ImageFont.truetype(
            "DejaVuSans-Bold.ttf", radius
        )
    except OSError:
        font = ImageFont.load_default()

    draw.text(
        (cx, cy),
        "?",
        font=font,
        fill=(255, 255, 255),
        anchor="mm"
    )

    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    im.save(path, "PNG")

    print(f"Fallback image created: {path}")
    return True
STYLE = (
    "Polished 2D cartoon illustration from a viral stickman comedy animation: "
    "clean bold black outlines, flat cel shading, rich painted full-color background, "
    "warm cinematic light, {FRAME}. Stickman characters with large solid white round heads "
    "with a thin black outline, big expressive eyes with small black pupils, "
    "black eyebrow strokes, small expressive mouth, thin black stick arms and legs, "
    "small black rounded hands and feet. No text, letters, numbers, captions, watermark. SCENE: "
)
FRAME = {
    '9:16': 'portrait composition, all people fully visible and centered, ample room around heads and feet',
    '16:9': 'wide cinematic composition, all people fully visible with generous edges',
}
SIZE = {'9:16': (1080, 1920), '16:9': (1920, 1080)}
ACC = os.getenv('CF_ACCOUNT_ID', '').strip()
TOK = os.getenv('CF_API_TOKEN', '').strip()
MODEL = os.getenv('CF_IMAGE_MODEL', '@cf/black-forest-labs/flux-1-schnell').strip()
if len(sys.argv) != 2:
    sys.exit('Usage: python3 gen_images_fixed.py job_dir')
if not ACC or not TOK:
    sys.exit('MISSING_SECRETS: CF_ACCOUNT_ID and CF_API_TOKEN')
ROOT = Path(sys.argv[1]).resolve()
URL = f'https://api.cloudflare.com/client/v4/accounts/{ACC}/ai/run/{MODEL}'


def fit_image(im, size):
    """Create an exact-aspect canvas without altering source-image proportions."""
    im = im.convert('RGB')
    w, h = size
    scale_fill = max(w / im.width, h / im.height)
    bg = im.resize((round(im.width * scale_fill), round(im.height * scale_fill)), Image.Resampling.LANCZOS)
    left = (bg.width - w) // 2
    top = (bg.height - h) // 2
    bg = bg.crop((left, top, left + w, top + h)).filter(ImageFilter.GaussianBlur(45))
    bg = Image.blend(bg, Image.new('RGB', (w, h), (20, 20, 26)), .30)
    scale_contain = min(w / im.width, h / im.height)
    fore = im.resize((round(im.width * scale_contain), round(im.height * scale_contain)), Image.Resampling.LANCZOS)
    bg.paste(fore, ((w - fore.width) // 2, (h - fore.height) // 2))
    return bg


def fetch(prompt, seed, path, aspect):
    prompt = (STYLE.replace('{FRAME}', FRAME.get(aspect, FRAME['9:16'])) + prompt)[:2048]
    # FLUX.1 Schnell's official Workers AI input schema does not offer width/height.
    body = json.dumps({'prompt': prompt, 'steps': 4}).encode('utf-8')
    for attempt in range(5):
        try:
            req = urllib.request.Request(URL, data=body, headers={
                'Authorization': f'Bearer {TOK}',
                'Content-Type': 'application/json',
            })
            with urllib.request.urlopen(req, timeout=120) as resp:
                response = json.load(resp)
            if response.get('success') is False:
                raise ValueError(str(response.get('errors', []))[:200])
            encoded = (response.get('result') or {}).get('image')
            if not encoded:
                raise ValueError('Image missing from Cloudflare response')
            with Image.open(io.BytesIO(base64.b64decode(encoded))) as im:
                adjusted = fit_image(im, SIZE.get(aspect, SIZE['9:16']))
                path.parent.mkdir(parents=True, exist_ok=True)
                adjusted.save(path, format='PNG', optimize=True)
            print('ok', path.name, adjusted.size, flush=True)
            return True
        except urllib.error.HTTPError as e:
            msg = e.read().decode("utf-8", "replace")
        
            print(
                f"Cloudflare HTTP {e.code}: "
                f"{os.path.basename(path)} - {msg[:300]}",
                flush=True
            )
        
            # NSFW moderation rejection
            if e.code == 400 and (
                '"code":8007' in msg.replace(" ", "")
                or "Input prompt contains NSFW content" in msg
            ):
                print(
                    "Prompt rejected by moderation. "
                    "Using neutral fallback illustration."
                )
                return create_fallback_image(path, aspect)
        
            # Other invalid requests
            if e.code == 400:
                print("Invalid image-generation request.")
                return False
        
            # Authentication errors
            if e.code in (401, 403):
                print("Cloudflare authentication failed.")
                sys.exit(3)
        
            # Daily limit
            if e.code == 429 and "neuron" in msg.lower():
                print("DAILY_FREE_LIMIT_REACHED")
                sys.exit(4)
        
            if e.code == 429 or e.code >= 500:
                time.sleep(10 + attempt * 10)
                continue
        
            return False
        except Exception as e:
            print('retry', path.name, attempt, str(e)[:200], flush=True)
        if attempt < 4:
            time.sleep(10 + attempt * 10)
    return False


failed = []
for spec_path in sorted(glob.glob(str(ROOT / '*.json'))):
    with open(spec_path, encoding='utf-8') as handle:
        spec = json.load(handle)
    aspect = spec.get('aspect', '9:16')
    for idx, seg in enumerate(spec.get('segments', [])):
        if seg.get('type') != 'still' or not seg.get('prompt'):
            continue
        dest = (ROOT / seg['path']).resolve()
        if not dest.is_relative_to(ROOT):
            raise ValueError('Unsafe output path in job JSON')
        if dest.is_file():
            print('skip', dest.name, flush=True)
            continue
        if not fetch(seg['prompt'], seg.get('seed', idx + 1000), dest, aspect):
            failed.append(str(dest))
if failed:
    print('FAILED', failed)
    sys.exit(1)
