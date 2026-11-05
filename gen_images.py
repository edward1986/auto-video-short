"""Generate FLUX.1 Schnell illustrations, then make correctly proportioned 9:16 or 16:9 PNGs.
Usage: python3 gen_images_fixed.py job_dir
Requires CF_ACCOUNT_ID and CF_API_TOKEN; optional CF_BACKUP_ACCOUNT_ID and CF_BACKUP_API_TOKEN.
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
from PIL import Image, ImageFilter

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
BACKUP_ACC = os.getenv('CF_BACKUP_ACCOUNT_ID', '').strip()
BACKUP_TOK = os.getenv('CF_BACKUP_API_TOKEN', '').strip()
MODEL = os.getenv('CF_IMAGE_MODEL', '@cf/black-forest-labs/flux-1-schnell').strip()
if len(sys.argv) != 2:
    sys.exit('Usage: python3 gen_images_fixed.py job_dir')
if not ACC or not TOK:
    sys.exit('MISSING_SECRETS: CF_ACCOUNT_ID and CF_API_TOKEN')
ROOT = Path(sys.argv[1]).resolve()
ACCOUNTS = [('primary', ACC, TOK)]
if BACKUP_ACC and BACKUP_TOK and BACKUP_ACC != ACC:
    ACCOUNTS.append(('backup', BACKUP_ACC, BACKUP_TOK))
elif BACKUP_ACC or BACKUP_TOK:
    print('WARNING: backup requires both secrets and a different account ID.', flush=True)
EXHAUSTED = set()


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
    # FLUX.1 Schnell does not accept `seed` in the Workers AI REST API schema.
    prompt = (STYLE.replace('{FRAME}', FRAME.get(aspect, FRAME['9:16'])) + prompt)[:2048]
    body = json.dumps({'prompt': prompt, 'steps': 4}).encode('utf-8')

    for label, account_id, token in ACCOUNTS:
        if label in EXHAUSTED:
            continue
        url = f'https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{MODEL}'
        for attempt in range(3):
            try:
                req = urllib.request.Request(url, data=body, headers={
                    'Authorization': f'Bearer {token}',
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                })
                with urllib.request.urlopen(req, timeout=120) as resp:
                    response = json.load(resp)
                if response.get('success') is False:
                    errors = response.get('errors') or []
                    raise ValueError(f'Cloudflare reported errors: {errors}')
                encoded = (response.get('result') or {}).get('image')
                if not encoded:
                    raise ValueError('Image missing from Cloudflare response')
                with Image.open(io.BytesIO(base64.b64decode(encoded))) as im:
                    adjusted = fit_image(im, SIZE.get(aspect, SIZE['9:16']))
                    path.parent.mkdir(parents=True, exist_ok=True)
                    adjusted.save(path, format='PNG', optimize=True)
                print('ok', path.name, adjusted.size, 'account:', label, flush=True)
                return True
            except urllib.error.HTTPError as e:
                raw = e.read(4096).decode('utf-8', 'replace')
                try:
                    errs = json.loads(raw).get('errors') or []
                except ValueError:
                    errs = []
                codes = {item.get('code') for item in errs if isinstance(item, dict)}
                depleted = (e.code == 429 and (4006 in codes or 'daily free allocation' in raw.lower() or 'neuron' in raw.lower()))
                print(f'{label}: {path.name} HTTP {e.code}, attempt {attempt+1}: {raw[:250]}', flush=True)
                if depleted:
                    EXHAUSTED.add(label)
                    print(f'DAILY_FREE_LIMIT_REACHED: {label}; attempting next configured account', flush=True)
                    break
                if e.code in (400, 401, 403):
                    # Invalid inputs or credentials cannot be repaired by retrying.
                    print(f'{label}: non-retryable error', flush=True)
                    return False
                if e.code not in (429, 500, 502, 503, 504):
                    return False
            except Exception as e:
                print(f'{label}: {path.name} attempt {attempt+1}: {type(e).__name__}: {str(e)[:180]}', flush=True)
            if attempt < 2:
                time.sleep(5 * (attempt + 1))

    print(f'NO_AVAILABLE_IMAGE_ACCOUNT: {path.name}', flush=True)
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
