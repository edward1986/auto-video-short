import re
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from moviepy.editor import TextClip, ColorClip, ImageClip, CompositeVideoClip

def create_noise_overlay(size, duration, opacity=0.08):
    """Creates a textured grain overlay."""
    w, h = size
    # Create a small noise texture and scale it up to save memory/cpu and create a 'gritty' look
    noise = np.random.randint(0, 255, (h // 4, w // 4, 3), dtype="uint8")
    img_clip = ImageClip(noise).set_duration(duration).set_opacity(opacity).resize(size)
    return img_clip

def create_gradient_glow(size, duration, color=(200, 200, 255), opacity=0.15):
    """Creates a soft radial gradient glow in the center."""
    w, h = size
    inner_color = (*color, int(255 * opacity))

    base = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(base)

    circle_size = min(w, h) * 0.9
    left = (w - circle_size) / 2
    top = (h - circle_size) / 2
    draw.ellipse([left, top, left + circle_size, top + circle_size], fill=inner_color)

    glow = base.filter(ImageFilter.GaussianBlur(radius=circle_size / 3))
    glow_array = np.array(glow)

    return (
        ImageClip(glow_array)
        .set_duration(duration)
        .set_position("center")
        .set_opacity(opacity)
    )

def apply_kinetic_pop(clip, duration=0.1, scale=1.2):
    """Applies a 'pop' scale animation at the beginning of the clip."""
    return clip.resize(lambda t: scale if t < duration else 1.0)

def apply_zoom(clip, total_duration, start_scale=1.0, end_scale=1.1):
    """Applies a slow zoom (Ken Burns) effect."""
    return clip.resize(lambda t: start_scale + (end_scale - start_scale) * (t / total_duration))

def create_hook_clip(text, duration=2.0, font="Arial-Bold", fontsize=180):
    """Creates a high-impact 2-second hook title card with a pop animation."""
    hook = (
        TextClip(
            text.upper(),
            fontsize=fontsize,
            color="white",
            font=font,
            stroke_color="black",
            stroke_width=5,
            method="label",
        )
        .set_start(0)
        .set_duration(duration)
        .set_position(("center", "center"))
    )
    # Strong kinetic pop for the hook
    return hook.resize(lambda t: 1.1 + 0.2 * (1 - (t / duration) ** 2) if t < duration else 1.0)

def build_modern_captions(words, video_size, highlight_word="", font="Arial-Bold"):
    """Builds word-by-word captions with kinetic animations and keyword highlighting."""
    clips = []
    highlight_word = highlight_word.lower() if highlight_word else ""

    for item in words:
        word = str(item.get("word", "")).strip()
        start = float(item.get("start", 0))
        end = float(item.get("end", start + 0.5))

        if not word:
            continue

        duration = max(end - start, 0.3)
        clean_word = re.sub(r"[^a-zA-Z0-9]", "", word).lower()

        # Modern highlighting: Yellow for keywords or long words
        is_highlight = clean_word == highlight_word or len(clean_word) > 7
        color = "#FFFF00" if is_highlight else "white"
        font_size = 140 if is_highlight else 120

        # Text clip - Bold, high-contrast
        txt = (
            TextClip(
                word.upper(),
                fontsize=font_size,
                color=color,
                font=font,
                stroke_color="black",
                stroke_width=3,
                method="label",
                align="center",
            )
            .set_start(start)
            .set_duration(duration)
            .set_position(("center", "center"))
        )

        # Kinetic "pop" animation
        txt = apply_kinetic_pop(txt, duration=0.1, scale=1.2)

        # Minimal shadow for depth
        shadow = (
            TextClip(
                word.upper(),
                fontsize=font_size,
                color="black",
                font=font,
                method="label",
                align="center",
            )
            .set_start(start)
            .set_duration(duration)
            .set_position(("center", "center"))
            .set_opacity(0.4)
        )
        # Apply pop animation to shadow
        shadow = shadow.resize(lambda t: 1.25 if t < 0.1 else 1.05)

        clips.extend([shadow, txt])

    return clips

def create_end_card(video_size, duration=2.0, text="FOLLOW FOR MORE", font="Arial-Bold"):
    """Creates a polished branded end card."""
    w, h = video_size
    cta_bg = ColorClip(size=video_size, color=(0, 0, 0)).set_duration(duration)

    # Adding a subtle glow to the end card
    glow = create_gradient_glow(video_size, duration, color=(255, 255, 255), opacity=0.2)

    cta_text = (
        TextClip(
            text,
            fontsize=100,
            color="white",
            font=font,
            method="label",
        )
        .set_duration(duration)
        .set_position("center")
    )
    # Gentle pulse for the CTA
    cta_text = cta_text.resize(lambda t: 1.0 + 0.05 * np.sin(2 * np.pi * t))

    return CompositeVideoClip([cta_bg, glow, cta_text], size=video_size)
