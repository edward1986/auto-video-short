"""Generate FLUX.1 Schnell illustrations, then make correctly proportioned 9:16 or 16:9 PNGs.
Usage: python3 gen_images.py job_dir
Supports primary and two separately authorized backup Cloudflare accounts.
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
    "Polished 2D illustrated storybook art, accurate to the characters and animals "
    "in the scene description, consistent character designs across scenes, "
    "clean outlines, rich painted background, cinematic lighting, {FRAME}. "
    "No text, letters, captions, numbers, logos or watermarks. SCENE: "
)
FRAME = {
    '9:16': 'portrait composition, all people fully visible and centered, ample room around heads and feet',
    '16:9': 'wide cinematic composition, all people fully visible with generous edges',
}
SIZE = {'9:16': (1080, 1920), '16:9': (1920, 1080)}
MODEL = os.getenv('CF_IMAGE_MODEL', '@cf/black-forest-labs/flux-1-schnell').strip()
if len(sys.argv) != 2:
    sys.exit('Usage: python3 gen_images.py job_dir')
ROOT = Path(sys.argv[1]).resolve()

ACCOUNT_FIELDS = [
    ('primary', 'CF_ACCOUNT_ID', 'CF_API_TOKEN'),
    ('backup', 'CF_BACKUP_ACCOUNT_ID', 'CF_BACKUP_API_TOKEN'),
    ('backup_2', 'CF_BACKUP_ACCOUNT_ID_2', 'CF_BACKUP_API_TOKEN_2'),
    ('backup_3', 'CF_BACKUP_ACCOUNT_ID_3', 'CF_BACKUP_API_TOKEN_3'),
]
ACCOUNTS = []
seen_ids = set()
for label, id_key, token_key in ACCOUNT_FIELDS:
    account_id = os.getenv(id_key, '').strip()
    token = os.getenv(token_key, '').strip()
    if not account_id and not token:
        continue
    if not account_id or not token:
        print(f'WARNING: {label} requires both {id_key} and {token_key}; skipping.', flush=True)
        continue
    if account_id in seen_ids:
        print(f'WARNING: duplicate Cloudflare account ID for {label}; skipping.', flush=True)
        continue
    ACCOUNTS.append((label, account_id, token))
    seen_ids.add(account_id)
if not ACCOUNTS:
    sys.exit('MISSING_SECRETS: Configure at least one complete Cloudflare account pair')
print('Configured image accounts:', ', '.join(label for label, _, _ in ACCOUNTS), flush=True)
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


def fetch(prompt, path, aspect):
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
                depleted = (4006 in codes or 'daily free allocation' in raw.lower() or 'daily neuron' in raw.lower())
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

    print(f'NO_AVAILABLE_IMAGE_ACCOUNT: {path.name}; configured={len(ACCOUNTS)}, exhausted={len(EXHAUSTED)}', flush=True)
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
        if not fetch(seg['prompt'], dest, aspect):
            failed.append(str(dest))
if failed:
    print('FAILED', failed)
    sys.exit(1)
