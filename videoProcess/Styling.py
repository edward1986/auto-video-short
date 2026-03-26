import re
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from moviepy.editor import TextClip, ColorClip, ImageClip, CompositeVideoClip, VideoClip

# Pre-compiled regex for better performance in build_modern_captions
NON_ALPHANUMERIC_RE = re.compile(r"[^a-zA-Z0-9]")


def create_noise_overlay(size, duration, opacity=0.08):
    """Creates a dynamic textured grain overlay (living grain) with optimized frame pooling."""
    w, h = size
    sw, sh = w // 4, h // 4
    # Pre-generate a pool of 24 frames to reduce CPU overhead per frame call
    pool = [np.random.randint(0, 255, (sh, sw, 3), dtype="uint8") for _ in range(24)]

    def make_frame(t):
        # Cycle through the pool at 24fps
        idx = int(t * 24) % 24
        return pool[idx]

    return (
        VideoClip(make_frame, duration=duration)
        .set_opacity(opacity)
        .resize(size)
    )


def create_gradient_glow(size, duration, color=(200, 200, 255), opacity=0.2):
    """Creates a soft radial gradient glow in the center.
    Performance: Generates at 1/10th scale to minimize Gaussian Blur cost.
    """
    w, h = size
    # Downscale for performance
    scale = 10
    small_size = (w // scale, h // scale)
    inner_color = (*color, int(255 * opacity))

    base = Image.new("RGBA", small_size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(base)

    circle_size = min(small_size) * 0.9
    left = (small_size[0] - circle_size) / 2
    top = (small_size[1] - circle_size) / 2
    draw.ellipse([left, top, left + circle_size, top + circle_size], fill=inner_color)

    glow = base.filter(ImageFilter.GaussianBlur(radius=circle_size / 3))
    glow_array = np.array(glow)

    clip = (
        ImageClip(glow_array)
        .set_duration(duration)
        .set_position("center")
        .resize(size)
    )
    # 2026 style: Subtle breathing/pulsing opacity
    return clip.set_opacity(lambda t: opacity * (0.8 + 0.2 * math.sin(2 * t)))


def apply_kinetic_pop(clip, duration=0.1, scale=1.2):
    """Applies a smooth 'pop' scale animation with exponential decay."""
    # Performance: Using math module for scalar operations in temporal lambda
    return clip.resize(lambda t: 1.0 + (scale - 1.0) * math.exp(-15 * t))


def apply_zoom(clip, total_duration, start_scale=1.0, end_scale=1.1):
    """Applies a slow zoom (Ken Burns) effect."""
    return clip.resize(
        lambda t: start_scale + (end_scale - start_scale) * (t / total_duration)
    )


def apply_slide_in(clip, duration=0.4, direction="bottom", final_pos=("center", "center")):
    """Applies a snappy slide-in animation toward a final target position."""

    def pos(t):
        if t >= duration:
            return final_pos

        # Snappy ease-out (2026 trend)
        offset = (1 - (t / duration)) ** 4

        tx, ty = final_pos
        # Convert semantic positions to relative floats for calculations
        rel_x = 0.5 if tx == "center" else tx
        rel_y = 0.5 if ty == "center" else ty

        if direction == "bottom":
            return (rel_x, rel_y + offset)
        if direction == "top":
            return (rel_x, rel_y - offset)
        if direction == "left":
            return (rel_x - offset, rel_y)
        if direction == "right":
            return (rel_x + offset, rel_y)
        return final_pos

    return clip.set_position(pos, relative=True)


def apply_fade_in(clip, duration=0.3):
    """Applies a simple fade-in effect."""
    return clip.set_opacity(lambda t: min(1.0, t / duration))


def create_hook_clip(text, duration=2.0, font="Arial-Bold", fontsize=180):
    """Creates a high-impact 2-second hook title card with aggressive kinetic animations."""
    hook = (
        TextClip(
            text.upper(),
            fontsize=fontsize,
            color="white",
            font=font,
            stroke_color="black",
            stroke_width=6,
            method="label",
        )
        .set_start(0)
        .set_duration(duration)
        .set_position(("center", "center"))
    )

    # Aggressive kinetic scaling (exponential decay with cosine oscillation)
    def hook_scale(t):
        return 1.0 + 0.3 * math.exp(-5 * t) * math.cos(10 * t)

    # Fixed: Use a static slight tilt for style instead of a lambda to avoid MoviePy 1.0.3 errors
    return hook.resize(hook_scale).rotate(-2)


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
        clean_word = NON_ALPHANUMERIC_RE.sub("", word).lower()

        # Modern highlighting: Bright Neon Green or Yellow
        is_highlight = clean_word == highlight_word or len(clean_word) > 7
        color = "#00FF00" if is_highlight else "white"
        font_size = 150 if is_highlight else 120

        # Text clip - Bold, high-contrast
        txt = (
            TextClip(
                word.upper(),
                fontsize=font_size,
                color=color,
                font=font,
                stroke_color="black",
                stroke_width=4,
                method="label",
                align="center",
            )
            .set_start(start)
            .set_duration(duration)
            .set_position(("center", "center"))
        )

        # Kinetic "pop" animation
        txt = apply_kinetic_pop(txt, duration=0.1, scale=1.3)

        # Drop shadow for readability
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
            .set_opacity(0.6)
        )
        # Using a slightly larger scale for shadow to create a 'glow' effect
        shadow = shadow.resize(lambda t: 1.35 if t < 0.1 else 1.05)

        clips.extend([shadow, txt])

    return clips


def create_end_card(
    video_size, duration=2.5, text="FOLLOW FOR MORE", font="Arial-Bold"
):
    """Creates a polished branded end card with punchy motion."""
    w, h = video_size
    cta_bg = ColorClip(size=video_size, color=(0, 0, 0)).set_duration(duration)

    # Adding a subtle glow to the end card
    glow = create_gradient_glow(
        video_size, duration, color=(255, 255, 255), opacity=0.3
    )

    cta_text = (
        TextClip(
            text,
            fontsize=110,
            color="white",
            font=font,
            method="label",
        )
        .set_duration(duration)
    )

    # Kinetic pulse and snappy slide-in from bottom
    cta_text = apply_slide_in(cta_text, duration=0.6, direction="bottom", final_pos=("center", "center"))
    cta_text = cta_text.resize(lambda t: 1.0 + 0.08 * math.sin(4 * math.pi * t))

    return CompositeVideoClip([cta_bg, glow, cta_text], size=video_size)
