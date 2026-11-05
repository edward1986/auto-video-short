#!/usr/bin/env python3
"""Generate factual trivia specifications from a reviewed bank, optionally AI.
Usage: python auto_trivia_spec.py jobs/trivia/spec.json [topic]
For AI: TRIVIA_USE_AI=true, CF_ACCOUNT_ID and CF_API_TOKEN.
"""
import datetime as dt
import json
import os
from pathlib import Path
import re
import sys
import urllib.request
import urllib.error

BANK = [
    ('science', 'Which planet is known as the Red Planet?', ['Venus', 'Mars', 'Jupiter', 'Mercury'], 1, 'Mars looks red because of iron oxide dust.'),
    ('animals', 'What is the fastest land animal?', ['Lion', 'Cheetah', 'Horse', 'Ostrich'], 1, 'The cheetah is the fastest land animal.'),
    ('space', 'What is the largest planet in our Solar System?', ['Earth', 'Saturn', 'Jupiter', 'Neptune'], 2, 'Jupiter is the largest planet in our Solar System.'),
    ('science', 'What gas do plants take in during photosynthesis?', ['Oxygen', 'Helium', 'Carbon dioxide', 'Nitrogen'], 2, 'Plants absorb carbon dioxide during photosynthesis.'),
    ('geography', 'What is the capital of Japan?', ['Osaka', 'Tokyo', 'Kyoto', 'Nagoya'], 1, 'Tokyo is the capital of Japan.'),
    ('animals', 'Which mammal can truly fly?', ['Flying squirrel', 'Bat', 'Sugar glider', 'Lemur'], 1, 'Bats are the only mammals capable of sustained powered flight.'),
    ('science', 'How many bones does a typical adult human have?', ['186', '206', '226', '246'], 1, 'A typical adult human skeleton has 206 bones.'),
    ('geography', 'Which ocean is the largest?', ['Atlantic', 'Indian', 'Arctic', 'Pacific'], 3, 'The Pacific Ocean is the largest ocean on Earth.'),
    ('nature', 'What is the chemical formula of water?', ['CO2', 'H2O', 'O2', 'NaCl'], 1, 'Water is made of two hydrogen atoms and one oxygen atom.'),
    ('animals', 'How many legs does a spider have?', ['Six', 'Eight', 'Ten', 'Twelve'], 1, 'Spiders have eight legs.'),
    ('science', 'Which star is closest to Earth?', ['Sirius', 'Polaris', 'The Sun', 'Betelgeuse'], 2, 'The Sun is the closest star to Earth.'),
    ('history', 'Which civilization built Machu Picchu?', ['Romans', 'Inca', 'Ancient Greeks', 'Maya'], 1, 'The Inca built Machu Picchu in the Andes.'),
]


def ai_question(topic):
    account = os.getenv('CF_ACCOUNT_ID', '').strip()
    token = os.getenv('CF_API_TOKEN', '').strip()
    model = os.getenv('CF_TEXT_MODEL', '@cf/meta/llama-3.1-8b-instruct').strip()
    if not account or not token:
        raise RuntimeError('AI mode requires CF_ACCOUNT_ID and CF_API_TOKEN')
    url = f'https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/{model}'
    prompt = (f'Create ONE simple, accurate, family-friendly trivia question about {topic or "general knowledge"}. '
              'Respond ONLY with JSON object: '
              '{"question":"...","options":["...","...","...","..."],'
              '"correct_index":0,"explanation":"One short factual sentence."}. '
              'Four distinctly different answers. Zero-based correct_index. '
              'No disputed facts, trick questions, brand trivia, or copyrighted wording. '
              'Choose a well-established fact and double-check correctness.')
    data = json.dumps({'messages': [{'role': 'user', 'content': prompt}], 'max_tokens': 350, 'temperature': .3}).encode()
    req = urllib.request.Request(url, data=data, headers={'Authorization': f'Bearer {token}', 'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=90) as response:
            obj = json.load(response)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f'Workers AI HTTP {e.code}: {e.read(250).decode(errors="replace")}') from e
    if obj.get('success') is False:
        raise RuntimeError(f'AI error: {obj.get("errors")}')
    result = obj.get('result') or {}
    answer = result.get('response')
    if not answer and result.get('choices'):
        answer = result['choices'][0].get('message', {}).get('content')
    if isinstance(answer, dict):
        return answer
    m = re.search(r'\{.*\}', str(answer), flags=re.S)
    if not m:
        raise ValueError('AI did not return JSON')
    return json.loads(m.group())


def validate(entry):
    question = entry.get('question')
    options = entry.get('options')
    explanation = entry.get('explanation')
    index = entry.get('correct_index')
    if not isinstance(question, str) or not 12 <= len(question) <= 150:
        raise ValueError('Invalid question')
    if not isinstance(options, list) or len(options) != 4 or not all(isinstance(o,str) and 1 <= len(o) <= 60 for o in options):
        raise ValueError('Exactly four short options required')
    if len(set(x.casefold().strip() for x in options)) != 4:
        raise ValueError('Options must be distinct')
    if type(index) is not int or not 0 <= index <= 3:
        raise ValueError('correct_index must be integer from 0 to 3')
    if not isinstance(explanation, str) or not 10 <= len(explanation) <= 180:
        raise ValueError('Invalid explanation')
    return entry


def main():
    if len(sys.argv) not in (2,3):
        sys.exit('Usage: python auto_trivia_spec.py jobs/trivia/spec.json [optional topic]')
    topic = (sys.argv[2] if len(sys.argv) == 3 else os.getenv('TRIVIA_TOPIC', '')).strip()
    mode = os.getenv('TRIVIA_USE_AI', 'false').strip().lower() in ('true','1','yes')
    if mode:
        entry = validate(ai_question(topic))
        source = 'AI-generated; review factual correctness before public publishing'
    else:
        matches = [x for x in BANK if x[0] == topic.lower()] if topic else BANK
        if not matches:
            raise ValueError(f'No curated questions for {topic!r}. Use science, animals, space, geography, nature, history, or enable AI mode.')
        index = (dt.datetime.now(dt.timezone.utc).date().toordinal() + int(os.getenv('GITHUB_RUN_NUMBER', '0'))) % len(matches)
        _, q, choices, correct, exp = matches[index]
        entry = validate({'question': q, 'options': choices, 'correct_index': correct, 'explanation': exp})
        source = 'curated question bank'
    slug = 'trivia-' + re.sub(r'[^a-z0-9]+', '-', entry['question'].lower()).strip('-')[:38]
    suffix = os.getenv('GITHUB_RUN_ID') or dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d%H%M%S')
    spec = dict(entry, slug=f'{slug}-{suffix}', aspect='9:16', voice='am_puck', speed=1.0,
        source=source, topic=topic or 'general knowledge',
        segments=[{'type': 'still', 'path': 'scene-01.png',
                   'prompt': 'A cheerful cartoon stickman quiz show host, bright studio with colorful spotlight beams, abstract geometric decorations, playful neon green accents, full-body figure placed centrally, no words or logos.'}])
    dest = Path(sys.argv[1]); dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(spec, indent=2) + '\n', encoding='utf-8')
    print('Generated:', dest, 'source:', source, 'question:', spec['question'])

if __name__ == '__main__':
    main()
