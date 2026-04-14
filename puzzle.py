from sys import argv
from json import loads
from io import StringIO
from chess import Move, pgn, parse_square, PAWN, KNIGHT, BISHOP, ROOK, QUEEN, KING
from stockfish import Stockfish

import moviepy.editor as editor
from moviepy.video.fx.resize import resize
from moviepy.audio.fx.volumex import volumex

from videoProcess.Styling import (
    get_text_clip,
    create_noise_overlay,
    create_gradient_glow,
    create_vignette,
    apply_kinetic_pop,
    apply_slide_in,
    darken_clip,
    apply_zoom,
    create_flash_transition,
)

from board import *  # noqa: F403

clip_durations = {"puzzle": 10, "move": 0.2, "solution": 2.5, "line_move": 1}

piece_values = {PAWN: 1, KNIGHT: 3, BISHOP: 3, ROOK: 5, QUEEN: 9, KING: 2**32}


def produce_short(
    output: str,
    game_pgn: str,
    background: str,
    font: str,
    music: str,
    music_drop_time: float,
):
    resolution = (1080, 1920)

    # Puzzle question text - 2026 Style
    question_text = get_text_clip(
        "Can you find the brilliant move?".upper(),
        font=font,
        fontsize=100,
        color="white",
        stroke_color="black",
        stroke_width=4,
        size=(900, None),
        align="center",
    ).set_duration(clip_durations["puzzle"])
    question_text = apply_slide_in(
        question_text, duration=0.5, direction="bottom", final_pos=("center", 0.55)
    )
    question_text = apply_kinetic_pop(question_text, duration=0.3, scale=1.2)

    # Puzzle countdown text clips - 2026 Style
    countdown_texts = [
        (
            get_text_clip(
                str(clip_durations["puzzle"] - i),
                font=font,
                fontsize=180,
                color="white",
                stroke_color="black",
                stroke_width=6,
                align="center",
            )
            .set_start(i)
            .set_duration(1)
            .set_position(("center", 0.65), relative=True)
        )
        for i in range(clip_durations["puzzle"])
    ]
    countdown_texts = [
        apply_kinetic_pop(c, duration=0.2, scale=1.4) for c in countdown_texts
    ]

    # Initial chess board elements
    game_moves = list(pgn.read_game(StringIO(game_pgn)).mainline())
    flipped = False

    for move_index, move_node in enumerate(game_moves):
        if pgn.NAG_BRILLIANT_MOVE in move_node.nags:
            game_moves = game_moves[move_index - 1 :]
            flipped = move_node.turn()

            break
    else:
        raise ValueError("brilliant move not found in provided PGN.")

    board_clips = [
        draw_board(  # noqa: F405
            fen=game_moves[0].board().fen(),
            flipped=flipped,
            duration=clip_durations["puzzle"],
        ),
        draw_board(  # noqa: F405
            fen=game_moves[0].board().fen(),
            flipped=flipped,
            highlighted_move=game_moves[1].uci(),
            animated=True,
            brilliancy=True,
            audio=True,
            duration=clip_durations["move"],
        ).set_start(clip_durations["puzzle"]),
        draw_board(  # noqa: F405
            fen=game_moves[1].board().fen(),
            flipped=flipped,
            highlighted_move=game_moves[1].uci(),
            brilliancy=True,
            duration=clip_durations["solution"],
        ).set_start(clip_durations["puzzle"] + clip_durations["move"]),
    ]

    # Take the sacrificed piece with lowest value attacker
    # Play through the top engine line after (max of 5 moves into line)
    line_board_clips = []

    brilliancy_board = game_moves[1].board()

    # Find legal moves that capture the sacrificed piece
    capturing_moves: list[Move] = []

    sacrifice_square = parse_square(game_moves[1].uci()[2:4])
    for legal_move in brilliancy_board.legal_moves:
        if legal_move.to_square == sacrifice_square:
            capturing_moves.append(legal_move)

    # If there are no pieces that can take the sacrificed piece
    if len(capturing_moves) == 0:
        raise ValueError("the sacrificed piece is not the one that just moved.")

    # Find the move with the lowest value capturer
    lowest_value_capture = min(
        capturing_moves,
        key=lambda atk: piece_values[
            brilliancy_board.piece_at(atk.from_square).piece_type
        ],
    )
    if lowest_value_capture.promotion is not None:
        lowest_value_capture.promotion = QUEEN

    # Add the board clips for this capture and play on the board
    line_clips_start_time = sum(
        [clip_durations["puzzle"], clip_durations["move"], clip_durations["solution"]]
    )

    line_board_clips.append(
        draw_move_with_preview(  # noqa: F405
            fen=brilliancy_board.fen(),
            flipped=flipped,
            highlighted_move=lowest_value_capture.uci(),
            audio=True,
            move_duration=clip_durations["move"],
            preview_duration=clip_durations["line_move"],
        ).set_start(line_clips_start_time)
    )

    brilliancy_board.push(lowest_value_capture)

    # Go through the next couple top engine moves and add their board clips
    sf_engine = Stockfish("./src/resources/bin/stockfish.exe")
    sf_engine.set_depth(18)
    sf_engine.set_fen_position(brilliancy_board.fen())

    for i in range(7):
        top_engine_move = sf_engine.get_best_move()
        if top_engine_move is None:
            break

        line_board_clips.append(
            draw_move_with_preview(  # noqa: F405
                fen=sf_engine.get_fen_position(),
                flipped=flipped,
                highlighted_move=top_engine_move,
                audio=True,
                move_duration=clip_durations["move"],
                preview_duration=clip_durations["line_move"],
            ).set_start(
                line_clips_start_time
                + len(line_board_clips)
                * (clip_durations["move"] + clip_durations["line_move"])
            )
        )

        sf_engine.make_moves_from_current_position([top_engine_move])

    # Calculate full short duration given these engine line clips
    full_duration = (
        sum(clip_durations.values())
        + -clip_durations["line_move"]
        + (
            len(line_board_clips)
            * (clip_durations["move"] + clip_durations["line_move"])
        )
    )

    # Background image - 2026 Style: Darken and Zoom
    background_clip = editor.ImageClip(background).set_duration(full_duration)
    background_clip = resize(background_clip, height=1920)
    background_clip = darken_clip(background_clip, factor=0.45)
    background_clip = apply_zoom(background_clip, full_duration)

    # Correct move text - 2026 Style
    solution_san = game_moves[1].san()

    solution_text = (
        get_text_clip(
            solution_san + "!!",
            font=font,
            fontsize=200,
            color="#00ff00",
            stroke_color="black",
            stroke_width=8,
            align="center",
            size=(1000, None),
        )
        .set_start(clip_durations["puzzle"])
        .set_end(full_duration)
        .set_position(("center", 0.55), relative=True)
    )
    solution_text = apply_kinetic_pop(solution_text, duration=0.4, scale=1.6)

    # Overlays - 2026 style (Noise/Grain, Gradient Glow, and Vignette)
    noise_overlay = create_noise_overlay(resolution, full_duration, opacity=0.12)
    glow_overlay = create_gradient_glow(
        resolution,
        full_duration,
        color=[(0, 255, 0), (255, 255, 255)],
        opacity=0.15,
    )
    vignette_overlay = create_vignette(resolution, full_duration, opacity=0.5)

    # 2026 Style: White flash transition at the start of the solution
    flash = create_flash_transition(resolution).set_start(clip_durations["puzzle"])

    # Background music
    music_start_time = max(0.01, music_drop_time - clip_durations["puzzle"])
    music_clip = volumex(
        (
            editor.AudioFileClip(music)
            .cutout(0, music_start_time)
            .set_duration(full_duration)
        ),
        0.5,
    )

    # Thunder sound effect on brilliant move
    thunder_sfx_clip = volumex(
        editor.AudioFileClip("src/resources/chess/thunder.mp3").set_start(
            clip_durations["puzzle"] - 0.4
        ),
        0.5,
    )

    result = editor.CompositeVideoClip(
        [
            background_clip,
            glow_overlay,
            noise_overlay,
            vignette_overlay,
            question_text,
            *countdown_texts,
            solution_text,
            flash,
            *board_clips,
            *line_board_clips,
        ],
        size=(1080, 1920),
    )
    result.audio.clips.append(music_clip)
    result.audio.clips.append(thunder_sfx_clip)

    result.write_videofile(
        filename=output,
        fps=24,
        audio_codec="aac",
        threads=4,
        temp_audiofile="out/TEMP_chess_puzzle.mp4",
    )


if __name__ == "__main__":
    args = loads(argv[1])

    produce_short(
        game_pgn=args["pgn"],
        background=args["assets"]["background"],
        font=args["assets"]["font"],
        music=args["assets"]["music"],
        music_drop_time=args["musicDropTime"],
        output=args["output"],
    )
