import re
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from moviepy.editor import TextClip, ColorClip, ImageClip, CompositeVideoClip

# Pre-compiled regex for better performance in build_modern_captions
NON_ALPHANUMERIC_RE = re.compile(r"[^a-zA-Z0-9]")

# Global TextClip cache to avoid redundant ImageMagick renders
TEXT_CLIP_CACHE = {}


def get_text_clip(text, **kwargs):
    """Retrieves a cached TextClip or creates a new one if not found."""
    # Create a unique cache key based on text and all styling parameters
    # Sort kwargs to ensure consistent key generation
    sorted_params = sorted(kwargs.items())
    cache_key = (text, tuple(sorted_params))

    if cache_key in TEXT_CLIP_CACHE:
        # Return a copy to avoid side-effects from duration/start/position settings
        return TEXT_CLIP_CACHE[cache_key].copy()

    # Create new clip
    clip = TextClip(text, **kwargs)
    TEXT_CLIP_CACHE[cache_key] = clip
    return clip.copy()


def darken_clip(clip, factor=0.45):
    """Darkens a clip by multiplying all pixel values by a factor (0.0 to 1.0).
    Higher factor = brighter, lower factor = darker. 0.45 is ideal for 2026 'bold minimal' contrast.
    """
    return clip.fl_image(lambda image: (image * factor).astype(image.dtype))


def create_noise_overlay(size, duration, opacity=0.08):
    """Creates a dynamic textured grain overlay (living grain) with optimized frame pooling."""
    w, h = size
    # Optimization: Pre-resize noise to target resolution using NEAREST interpolation
    # for a bold 2026 'chunky' grain look and zero per-frame CPU resizing.
    sw, sh = w // 2, h // 2
    pool = []
    for _ in range(24):
        noise = np.random.randint(0, 255, (sh, sw, 3), dtype="uint8")
        resized = np.array(Image.fromarray(noise).resize(size, Image.NEAREST))
        pool.append(resized)

    def make_frame(t):
        idx = int(t * 24) % 24
        return pool[idx]

    # Fixed: In MoviePy 1.0.3, VideoClip doesn't take 'size' in __init__ and size/w/h are read-only.
    # Robust fix: Start with a ColorClip (which has size) and transform it with the noise generator.
    noise_clip = ColorClip(size=size, color=(0, 0, 0), duration=duration)

    def apply_noise(get_frame, t):
        return make_frame(t)

    return noise_clip.fl(apply_noise).set_opacity(opacity)


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

    # Fixed: set_opacity in MoviePy 1.0.3 does not support functions.
    # Reverting to static opacity for stability.
    return (
        ImageClip(glow_array)
        .set_duration(duration)
        .set_position("center")
        .set_opacity(opacity)
        .resize(size)
    )


def create_flash_transition(size, duration=0.1, opacity=0.8):
    """Creates a 0.1s white flash overlay for high-energy transitions (2026 trend)."""
    return (
        ColorClip(size=size, color=(255, 255, 255))
        .set_duration(duration)
        .set_opacity(opacity)
    )


def apply_kinetic_pop(clip, duration=0.1, scale=1.3):
    """Applies a snappy 'pop' scale animation with power-4 ease-out decay."""
    # Performance: Pre-calculate constants for the temporal lambda
    diff = scale - 1.0
    inv_duration = 1.0 / max(duration, 0.001)

    def pop_scale(t):
        if t >= duration:
            return 1.0
        # Snappy power-4 ease-out (2026 trend)
        offset = (1 - (t * inv_duration)) ** 4
        return 1.0 + diff * offset

    return clip.resize(pop_scale)


def apply_zoom(clip, total_duration, start_scale=1.0, end_scale=1.1):
    """Applies a slow zoom (Ken Burns) effect."""
    # Performance: Pre-calculate slope for the temporal lambda
    slope = (end_scale - start_scale) / max(total_duration, 0.001)
    return clip.resize(lambda t: start_scale + slope * t)


def apply_slide_in(
    clip, duration=0.4, direction="bottom", final_pos=("center", "center")
):
    """Applies a snappy slide-in animation toward a final target position."""
    # Performance: Pre-calculate constants and semantic mapping
    tx, ty = final_pos
    rel_x = 0.5 if tx == "center" else tx
    rel_y = 0.5 if ty == "center" else ty
    inv_duration = 1.0 / max(duration, 0.001)

    def pos(t):
        if t >= duration:
            return final_pos

        # Snappy ease-out (2026 trend)
        offset = (1 - (t * inv_duration)) ** 4

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
    # Fixed: use built-in fadein method as set_opacity doesn't support functions
    return clip.fadein(duration)


def create_hook_clip(text, duration=2.0, font="Arial-Bold", fontsize=220):
    """Creates a high-impact 2-second hook title card with aggressive kinetic animations."""
    # 2026 Trend: Oversized bold typography for immediate scroll-stop.
    hook = (
        get_text_clip(
            text.upper(),
            fontsize=fontsize,
            color="white",
            font=font,
            stroke_color="black",
            stroke_width=8,
            method="label",
        )
        .set_start(0)
        .set_duration(duration)
        .set_position(("center", "center"))
    )

    # Performance: Aggressive kinetic scaling (exponential decay with cosine oscillation)
    # Constants pre-calculated for the temporal lambda
    def hook_scale(t):
        # Snappier oscillation for 2026 'vibrate' feel
        return 1.0 + 0.4 * math.exp(-8 * t) * math.cos(15 * t)

    # Fixed: Use a static slight tilt for style instead of a lambda to avoid MoviePy 1.0.3 errors
    return hook.resize(hook_scale).rotate(-3)


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

        # Modern highlighting: Bright Neon Green (#00FF00)
        is_highlight = clean_word == highlight_word or len(clean_word) > 7
        color = "#00FF00" if is_highlight else "white"
        font_size = 160 if is_highlight else 125

        # Text clip - Bold, high-contrast
        txt = (
            get_text_clip(
                word.upper(),
                fontsize=font_size,
                color=color,
                font=font,
                stroke_color="black",
                stroke_width=5,
                method="label",
                align="center",
            )
            .set_start(start)
            .set_duration(duration)
            .set_position(("center", "center"))
        )

        # 2026 Trend: Semi-transparent neon highlight background box for keywords
        if is_highlight:
            # Optimization: Use existing txt clip size to avoid double-rendering
            tw, th = txt.size
            highlight_bg = (
                ColorClip(size=(int(tw * 1.2), int(th * 1.1)), color=(0, 255, 0))
                .set_start(start)
                .set_duration(duration)
                .set_opacity(0.3)
                .set_position(("center", "center"))
            )
            # Apply same pop to background for sync
            highlight_bg = apply_kinetic_pop(highlight_bg, duration=0.1, scale=1.3)
            clips.append(highlight_bg)

        # Kinetic "pop" animation
        txt = apply_kinetic_pop(txt, duration=0.1, scale=1.3)

        # Drop shadow for readability
        shadow = (
            get_text_clip(
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
            .set_opacity(0.7)
        )
        # 2026 style: Soft glow shadow (slight scale offset)
        shadow = shadow.resize(lambda t: 1.35 if t < 0.1 else 1.05)

        clips.extend([shadow, txt])

    return clips


def create_end_card(
    video_size, duration=2.5, text="FOLLOW FOR MORE", font="Arial-Bold"
):
    """Creates a polished branded end card with punchy motion and minimal layout."""
    w, h = video_size
    # 2026 Trend: Minimal pitch-black background with subtle glow
    cta_bg = ColorClip(size=video_size, color=(0, 0, 0)).set_duration(duration)

    glow = create_gradient_glow(
        video_size,
        duration,
        color=(0, 255, 0),
        opacity=0.2,  # Neon green glow accent
    )

    cta_text = get_text_clip(
        text.upper(),
        fontsize=130,
        color="white",
        font=font,
        stroke_color="black",
        stroke_width=3,
        method="label",
    ).set_duration(duration)

    # Kinetic pulse and snappy slide-in from bottom
    cta_text = apply_slide_in(
        cta_text, duration=0.5, direction="bottom", final_pos=("center", "center")
    )
    # Performance: Pre-calculate pulse constants
    pulse_freq = 6 * math.pi
    # Snappier breathing pulse
    cta_text = cta_text.resize(
        lambda t: 1.0 + 0.1 * math.exp(-3 * t) * math.sin(pulse_freq * t)
    )

    return CompositeVideoClip([cta_bg, glow, cta_text], size=video_size)
