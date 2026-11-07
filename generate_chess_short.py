#!/usr/bin/env python3
"""Create a vertical chess game Short with Stockfish + python-chess + Pillow.

Stockfish is installed using apt-get install stockfish on GitHub's Ubuntu runner.
The output MP4 uses FFmpeg and has a synthesized (royalty-free) quiet music bed.
"""
import argparse
import datetime
import io
import math
import os
from pathlib import Path
import random
import shutil
import subprocess
import tempfile
import json
import secrets
import wave

import chess
import chess.engine
import chess.pgn
import chess.svg
import cairosvg
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter


def font(size, bold=True):
    choices = (["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"]
               if bold else ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"])
    for name in choices:
        if Path(name).exists():
            return ImageFont.truetype(name, size)
    return ImageFont.load_default()


def find_stockfish(explicit):
    candidates = [explicit, os.environ.get('STOCKFISH_PATH'), shutil.which('stockfish'), '/usr/games/stockfish']
    for p in candidates:
        if p and Path(p).is_file() and os.access(p, os.X_OK):
            return p
    raise SystemExit('Stockfish missing: install with sudo apt-get install -y stockfish')


# Named, legal opening lines in UCI notation. They are validated before use.
# The run number cycles through openings to avoid identical *consecutive*
# openings on scheduled/manual GitHub runs; independent runs still use entropy.
OPENINGS = [
    ("Italian Game", ["e2e4", "e7e5", "g1f3", "b8c6", "f1c4"]),
    ("Ruy Lopez", ["e2e4", "e7e5", "g1f3", "b8c6", "f1b5"]),
    ("Sicilian Defense", ["e2e4", "c7c5", "g1f3", "d7d6"]),
    ("French Defense", ["e2e4", "e7e6", "d2d4", "d7d5"]),
    ("Caro-Kann Defense", ["e2e4", "c7c6", "d2d4", "d7d5"]),
    ("Scandinavian Defense", ["e2e4", "d7d5", "e4d5", "d8d5"]),
    ("Pirc Defense", ["e2e4", "d7d6", "d2d4", "g8f6"]),
    ("Queen's Gambit", ["d2d4", "d7d5", "c2c4"]),
    ("Queen's Gambit Declined", ["d2d4", "d7d5", "c2c4", "e7e6"]),
    ("King's Indian Defense", ["d2d4", "g8f6", "c2c4", "g7g6"]),
    ("Nimzo-Indian Defense", ["d2d4", "g8f6", "c2c4", "e7e6", "b1c3", "f8b4"]),
    ("English Opening", ["c2c4", "e7e5", "b1c3"]),
    ("Réti Opening", ["g1f3", "d7d5", "c2c4"]),
    ("Dutch Defense", ["d2d4", "f7f5", "c2c4"]),
    ("Vienna Game", ["e2e4", "e7e5", "b1c3"]),
    ("Four Knights Game", ["e2e4", "e7e5", "g1f3", "b8c6", "b1c3", "g8f6"]),
]


def choose_opening(rng, run_number=None):
    if run_number is not None and run_number > 0:
        # GitHub run numbers grow by one each new run of this workflow.
        # Neighboring runs start with a different opening until cycle wraps.
        return OPENINGS[(run_number - 1) % len(OPENINGS)]
    return rng.choice(OPENINGS)


def validate_openings():
    for name, sequence in OPENINGS:
        board = chess.Board()
        for text in sequence:
            move = chess.Move.from_uci(text)
            if move not in board.legal_moves:
                raise ValueError(f"Invalid opening {name}: {text}")
            board.push(move)


def make_game(engine_path, ply_count, think_time, seed, run_number=None):
    # Do not reuse the same RNG seed on each run.
    rng = random.Random(seed if seed is not None else secrets.randbits(64))
    opening_name, opening_moves = choose_opening(rng, run_number)
    board = chess.Board()
    game = chess.pgn.Game()
    game.headers["Event"] = "Random Chess Opening Short"
    game.headers["Date"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y.%m.%d")
    game.headers["White"] = "Stockfish White"
    game.headers["Black"] = "Stockfish Black"
    game.headers["Opening"] = opening_name
    node = game
    board_states = [(board.copy(), None, "Opening position", None)]

    # First play this run's named opening, saving each board position and move.
    for uci in opening_moves[:ply_count]:
        move = chess.Move.from_uci(uci)
        if move not in board.legal_moves:
            raise ValueError(f"Opening {opening_name} has illegal move {uci}")
        san = board.san(move)
        number = board.fullmove_number
        label = f"{number}. {san}" if board.turn == chess.WHITE else f"{number}... {san}"
        before = board.copy()
        node = node.add_variation(move)
        board.push(move)
        board_states.append((board.copy(), move, label, before))

    engine = chess.engine.SimpleEngine.popen_uci(engine_path)
    try:
        engine.configure({'Threads': 1, 'Hash': 32})
        for i in range(max(0, ply_count - len(opening_moves))):
            if board.is_game_over(claim_draw=True):
                break
            # Choose among multiple strong legal moves rather than deterministic
            # Stockfish best_move. A minority of moves pick alternatives.
            legal_count = board.legal_moves.count()
            multipv = min(4, legal_count)
            if multipv == 0:
                break
            lines = engine.analyse(board, chess.engine.Limit(time=think_time), multipv=multipv)
            if isinstance(lines, dict):
                lines = [lines]
            options = [entry["pv"][0] for entry in lines
                       if entry.get("pv") and entry["pv"][0] in board.legal_moves]
            if not options:
                break
            weights = [7, 4, 2, 1][:len(options)]
            pick = rng.choices(options, weights=weights, k=1)[0]
            san = board.san(pick)
            number = board.fullmove_number
            label = f'{number}. {san}' if board.turn == chess.WHITE else f'{number}... {san}'
            node = node.add_variation(pick)
            board.push(pick)
            board_states.append((board.copy(), pick, label, board_states[-1][0].copy()))
        game.headers['Result'] = board.result(claim_draw=True) if board.is_game_over(claim_draw=True) else '*'
    finally:
        engine.quit()
    return game, board_states, opening_name


def board_image(board, lastmove):
    # Fully self-contained: python-chess provides the pieces and board graphics.
    svg = chess.svg.board(
        board=board, lastmove=lastmove,
        size=800, coordinates=True,
        colors={'square light':'#E8E9E4', 'square dark':'#668475',
                'margin':'#18282D', 'coord light':'#E8E9E4', 'coord dark':'#668475'},
    )
    return Image.open(io.BytesIO(cairosvg.svg2png(bytestring=svg.encode('utf-8')))).convert('RGB')


def make_frame(board, lastmove, move_text, idx, count, w, h, opening_name="Chess Game"):
    canvas = Image.new('RGB',(w,h),(12,20,27))
    draw = ImageDraw.Draw(canvas)
    # modern vertical gradient
    for y in range(h):
        t=y/max(1,h-1)
        draw.line((0,y,w,y),fill=(round(13+6*t),round(26+10*t),round(32+14*t)))
    draw.text((w//2, int(.085*h)), 'CHESS  •  ENGINE DUEL', font=font(max(22,w//24)), fill='#C9FFE2',anchor='mm')
    draw.text((w//2, int(.145*h)), opening_name.upper(), font=font(max(24,min(w//21, 35))), fill='#FFFFFF',anchor='mm')
    bs=min(int(w*.93),int(h*.53))
    board_img=board_image(board,lastmove).resize((bs,bs),Image.Resampling.LANCZOS)
    bx=(w-bs)//2
    by=int(h*.235)
    canvas.paste(board_img,(bx,by))
    draw=ImageDraw.Draw(canvas)
    if idx == 0:
        status='THE GAME BEGINS'
    elif board.is_checkmate():
        status='CHECKMATE!'
    elif board.is_check():
        status=f'{move_text}   •   CHECK!'
    else:
        status=move_text
    draw.text((w//2, int(.79*h)),status,font=font(max(37,w//12)),fill='#FFFFFF',anchor='mm')
    draw.text((w//2,int(.844*h)),f'MOVE {idx} / {count}',font=font(max(18,w//29)),fill='#AAB9BC',anchor='mm')
    left=int(.08*w); right=int(.92*w)
    draw.rounded_rectangle((left,int(.886*h),right,int(.897*h)),radius=6,fill='#3A4C50')
    end=left+int((right-left)*idx/max(1,count))
    if end>left:
        draw.rounded_rectangle((left,int(.886*h),end,int(.897*h)),radius=6,fill='#C9FFE2')
    draw.text((w//2,int(.942*h)),'FOLLOW FOR MORE CHESS SHORTS',font=font(max(18,w//30)),fill='#C8D6D8',anchor='mm')
    return canvas


def create_music(path, seconds, states, seconds_per_move, music_gain=0.55, sfx_gain=1.0):
    """Original royalty-free ambient music plus one synthesized cue per move.

    Normal move = wooden tick; capture = low click/thump; check = bright bell;
    checkmate = larger final chime. Designed for mono 24 kHz audio.
    """
    sr = 24000
    count = max(1, round(seconds * sr))
    t = np.arange(count, dtype=np.float32) / sr
    # Slow, simple original ambient chord bed; no external audio assets.
    chord = (0.055 * np.sin(2 * np.pi * 130.81 * t)
             + 0.037 * np.sin(2 * np.pi * 164.81 * t)
             + 0.024 * np.sin(2 * np.pi * 196.0 * t))
    # Gentle pulse to make the bed sound less static.
    pulse = 0.78 + 0.22 * np.sin(2 * np.pi * 1.15 * t) ** 2
    envelope = np.minimum(1, t / 0.7) * np.minimum(1, np.maximum(0, seconds - t) / 1.0)
    audio = (chord * pulse * envelope * float(music_gain)).astype(np.float32)

    for index in range(1, len(states)):
        board, move, _label, previous = states[index]
        start = int(index * seconds_per_move * sr)
        if start >= count:
            continue
        duration = min(round(0.39 * sr), count - start)
        local_t = np.arange(duration, dtype=np.float32) / sr
        captured = previous.is_capture(move) if previous is not None and move is not None else False
        if board.is_checkmate():
            # Final chime: original layered fifth.
            fx = (0.20 * np.sin(2 * np.pi * 523.25 * local_t)
                  + 0.14 * np.sin(2 * np.pi * 783.99 * local_t)) * np.exp(-local_t * 8)
        elif board.is_check():
            fx = (0.16 * np.sin(2 * np.pi * 880 * local_t)
                  + 0.11 * np.sin(2 * np.pi * 1174.66 * local_t)) * np.exp(-local_t * 16)
        elif captured:
            fx = (0.24 * np.sin(2 * np.pi * (260 - 95 * local_t) * local_t)
                  + 0.10 * np.sin(2 * np.pi * 430 * local_t)) * np.exp(-local_t * 28)
        else:
            fx = (0.19 * np.sin(2 * np.pi * 650 * local_t)
                  + 0.10 * np.sin(2 * np.pi * 390 * local_t)) * np.exp(-local_t * 38)
        audio[start:start + duration] += fx.astype(np.float32) * float(sfx_gain)

    # Soft limiter so generated sounds cannot clip.
    audio = np.tanh(audio * 1.35) / 1.35
    with wave.open(str(path), 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes((np.clip(audio, -1, 1) * 32767).astype('<i2').tobytes())


def run():
    p=argparse.ArgumentParser()
    p.add_argument('--output',default='output.mp4')
    p.add_argument('--pgn',default='random_game.pgn')
    p.add_argument('--stockfish',default='')
    p.add_argument('--moves',type=int,default=24,help='Half moves / plies')
    p.add_argument('--seconds-per-move',type=float,default=1.65)
    p.add_argument('--think-time',type=float,default=.06)
    p.add_argument('--width',type=int,default=720)
    p.add_argument('--height',type=int,default=1280)
    p.add_argument('--seed',type=int,default=None)
    p.add_argument('--metadata',default='chess_metadata.json')
    p.add_argument('--music-gain',type=float,default=0.55)
    p.add_argument('--sfx-gain',type=float,default=1.0)
    args=p.parse_args()
    if args.moves<1 or args.moves>65 or args.width<300 or args.height<500:
        p.error('Invalid moves or dimensions')
    if not (0 <= args.music_gain <= 2 and 0 <= args.sfx_gain <= 2):
        p.error('Audio gains must be between 0 and 2')
    if args.seconds_per_move<=0 or args.think_time<=0:
        p.error('Durations must be positive')
    stockfish=find_stockfish(args.stockfish)
    validate_openings()
    run_number_string = os.getenv("GITHUB_RUN_NUMBER", "")
    run_number = int(run_number_string) if run_number_string.isdigit() else None
    game,states,opening_name=make_game(
        stockfish,args.moves,args.think_time,args.seed,run_number=run_number
    )
    metadata = {
        "opening": opening_name,
        "moves": len(states) - 1,
        "game_result": game.headers.get("Result", "*"),
        "run_id": os.getenv("GITHUB_RUN_ID", ""),
        "run_number": run_number,
        "title": f"{opening_name} | Stockfish Chess Battle ♟️ #Shorts",
    }
    Path(args.metadata).write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    Path(args.pgn).parent.mkdir(parents=True,exist_ok=True)
    Path(args.pgn).write_text(str(game)+'\n',encoding='utf-8')
    Path(args.output).parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='chess_render_') as work:
        work=Path(work)
        # Concat demuxer: 1 lossless still per move, FFmpeg makes efficient MP4.
        manifest=work/'frames.txt'
        entries=[]
        for idx,(board,lastmove,label,_) in enumerate(states):
            target=work/f'frame_{idx:03}.png'
            make_frame(board,lastmove,label,idx,len(states)-1,args.width,args.height,opening_name).save(target,optimize=True)
            entries.extend([f"file '{target.as_posix()}'",f'duration {args.seconds_per_move:.4f}'])
        entries.append(f"file '{(work/f'frame_{len(states)-1:03}.png').as_posix()}'")
        manifest.write_text('\n'.join(entries)+'\n')
        total=len(states)*args.seconds_per_move
        music=work/'background.wav'
        create_music(music,total,states,args.seconds_per_move,args.music_gain,args.sfx_gain)
        cmd=['ffmpeg','-hide_banner','-loglevel','error','-y',
             '-f','concat','-safe','0','-i',str(manifest),'-i',str(music),
             '-t',str(total),'-r','24','-c:v','libx264','-preset','veryfast',
             '-crf','24','-pix_fmt','yuv420p','-c:a','aac','-b:a','96k',
             '-movflags','+faststart',str(Path(args.output).resolve())]
        subprocess.run(cmd,check=True)
    print(f'Created {args.output} ({len(states)-1} moves; {total:.1f}s)')
    print(f'Saved {args.pgn}')
    print(f'Opening: {opening_name}; metadata: {args.metadata}')


if __name__=='__main__':
    run()
