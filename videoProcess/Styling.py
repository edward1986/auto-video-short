import re
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# Monkey-patch PIL.Image.ANTIALIAS for MoviePy compatibility with Pillow 10+
if not hasattr(Image, "ANTIALIAS"):
    Image.ANTIALIAS = Image.LANCZOS
from moviepy.editor import ColorClip, ImageClip, CompositeVideoClip

# Pre-compiled regex for better performance in build_modern_captions
NON_ALPHANUMERIC_RE = re.compile(r"[^a-zA-Z0-9]")

# Global TextClip cache to avoid redundant ImageMagick renders
TEXT_CLIP_CACHE = {}

# Global LUT cache for darken_clip to avoid redundant array creation
DARKEN_LUT_CACHE = {}

# Global noise pool cache to avoid redundant generation for identical sizes
NOISE_POOL_CACHE = {}


def get_pil_text_clip(
    text,
    fontsize=70,
    color="white",
    font="Arial-Bold",
    stroke_color=None,
    stroke_width=0,
    method="label",
    size=None,
    align="center",
    **kwargs,
):
    """Renders text using PIL and returns an ImageClip.
    Provides a reliable fallback for environments without ImageMagick.
    """
    # 2026 Style: High contrast, bold, mobile-first
    # Default to standard font if specific one fails
    try:
        pil_font = ImageFont.truetype(font, fontsize)
    except Exception:
        try:
            pil_font = ImageFont.truetype("default.ttf", fontsize)
        except Exception:
            # Fallback to a default font (requires Pillow 10.1.0+ for size)
            try:
                pil_font = ImageFont.load_default(size=fontsize)
            except Exception:
                pil_font = ImageFont.load_default()

    # Handle text scaling for 2026 style (ensure text fits within screen/margins)
    if size and size[0]:
        target_w = size[0]
        test_bbox = ImageDraw.Draw(Image.new("L", (1, 1))).textbbox(
            (0, 0), text, font=pil_font
        )
        current_w = test_bbox[2] - test_bbox[0]
        if current_w > target_w:
            scale_f = target_w / current_w
            new_size = max(20, int(fontsize * scale_f))
            try:
                pil_font = ImageFont.truetype(font, new_size)
            except Exception:
                try:
                    pil_font = ImageFont.load_default(size=new_size)
                except Exception:
                    pil_font = ImageFont.load_default()

    # Handle text wrapping for 'caption' method
    lines = [text]
    if method == "caption" and size and size[0]:
        max_width = size[0]
        words = text.split()
        lines = []
        current_line = []
        for word in words:
            test_line = " ".join(current_line + [word])
            # Use textbbox instead of deprecated textsize
            bbox = ImageDraw.Draw(Image.new("L", (1, 1))).textbbox(
                (0, 0), test_line, font=pil_font
            )
            if bbox[2] - bbox[0] <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(" ".join(current_line))
                    current_line = [word]
                else:
                    lines.append(word)  # Word itself is too long
        if current_line:
            lines.append(" ".join(current_line))

    # Calculate total dimensions
    draw_test = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    line_heights = []
    max_line_width = 0
    for line in lines:
        bbox = draw_test.textbbox((0, 0), line, font=pil_font)
        max_line_width = max(max_line_width, bbox[2] - bbox[0])
        line_heights.append(bbox[3] - bbox[1])

    total_height = sum(line_heights) + (len(lines) - 1) * (fontsize // 4)
    if size and size[0]:
        canvas_w = size[0]
    else:
        canvas_w = max_line_width + stroke_width * 2 + 20

    if size and size[1]:
        canvas_h = size[1]
    else:
        canvas_h = total_height + stroke_width * 2 + 20

    # Create canvas
    img = Image.new("RGBA", (int(canvas_w), int(canvas_h)), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Draw lines
    current_y = (canvas_h - total_height) // 2
    for i, line in enumerate(lines):
        line_bbox = draw.textbbox((0, 0), line, font=pil_font)
        line_w = line_bbox[2] - line_bbox[0]

        if align == "center":
            x = (canvas_w - line_w) // 2
        elif align == "right":
            x = canvas_w - line_w - 10
        else:
            x = 10

        # Optional Stroke/Outline
        if stroke_color and stroke_width > 0:
            for offset_x in range(-stroke_width, stroke_width + 1):
                for offset_y in range(-stroke_width, stroke_width + 1):
                    draw.text(
                        (x + offset_x, current_y + offset_y),
                        line,
                        font=pil_font,
                        fill=stroke_color,
                    )

        draw.text((x, current_y), line, font=pil_font, fill=color)
        current_y += line_heights[i] + (fontsize // 4)

    return ImageClip(np.array(img))


def get_text_clip(text, **kwargs):
    """Retrieves a cached ImageClip (rendered via PIL) or creates a new one."""
    # Create a unique cache key based on text and all styling parameters
    sorted_params = sorted(kwargs.items(), key=lambda x: str(x[0]))
    cache_key = (text, tuple(sorted_params))

    if cache_key in TEXT_CLIP_CACHE:
        return TEXT_CLIP_CACHE[cache_key].copy()

    # Use PIL-based renderer instead of MoviePy TextClip
    clip = get_pil_text_clip(text, **kwargs)
    TEXT_CLIP_CACHE[cache_key] = clip
    return clip.copy()


def darken_clip(clip, factor=0.45):
    """Darkens a clip by multiplying all pixel values by a factor (0.0 to 1.0).
    Higher factor = brighter, lower factor = darker. 0.45 is ideal for 2026 'bold minimal' contrast.
    Performance: Uses a Look-Up Table (LUT) for uint8 to avoid per-pixel floating point math.
    """

    def apply_darken(image):
        # Optimized path for standard uint8 images
        if image.dtype == np.uint8:
            if factor not in DARKEN_LUT_CACHE:
                DARKEN_LUT_CACHE[factor] = (np.arange(256) * factor).astype("uint8")
            return DARKEN_LUT_CACHE[factor][image]

        # Fallback for other dtypes (float, uint16, etc.)
        return (image * factor).astype(image.dtype)

    return clip.fl_image(apply_darken)


def create_noise_overlay(size, duration, opacity=0.08):
    """Creates a dynamic textured grain overlay with layered noise scales (2026 trend).
    Performance: Caches the noise pool by size and uses NumPy for fast resizing of chunky grain.
    """
    # Defensive: Ensure size is a hashable tuple
    size_tuple = tuple(size) if isinstance(size, (list, tuple)) else size

    if size_tuple in NOISE_POOL_CACHE:
        pool = NOISE_POOL_CACHE[size_tuple]
    else:
        w, h = size_tuple
        # Layer 1: Chunky grain for texture (1/4 resolution)
        sw1, sh1 = w // 4, h // 4
        # Layer 2: Fine grain for depth (1/2 resolution)
        sw2, sh2 = w // 2, h // 2

        pool = []
        for _ in range(24):
            noise1 = np.random.randint(0, 255, (sh1, sw1, 3), dtype="uint8")
            noise2 = np.random.randint(0, 255, (sh2, sw2, 3), dtype="uint8")

            # Optimized path for integer scaling factors (1/4 scale)
            if w % 4 == 0 and h % 4 == 0:
                layer1 = noise1.repeat(4, axis=0).repeat(4, axis=1)
            else:
                # Fallback to PIL for non-integer scales or remainder pixels
                layer1 = np.array(
                    Image.fromarray(noise1).resize(size_tuple, Image.NEAREST)
                )

            # Layer 2: Still requires BILINEAR for a soft organic feel
            layer2 = np.array(
                Image.fromarray(noise2).resize(size_tuple, Image.BILINEAR)
            )

            # Blend layers (50/50 mix) for a richer organic look
            combined = (layer1.astype("uint16") + layer2.astype("uint16")) // 2
            pool.append(combined.astype("uint8"))

        NOISE_POOL_CACHE[size_tuple] = pool

    def make_frame(t):
        idx = int(t * 24) % 24
        return pool[idx]

    # Robust fix for MoviePy 1.0.3: Start with ColorClip and transform
    noise_clip = ColorClip(size=size, color=(0, 0, 0), duration=duration)

    return noise_clip.fl(lambda get_frame, t: make_frame(t)).set_opacity(opacity)


def create_gradient_glow(size, duration, color=(200, 200, 255), opacity=0.2):
    """Creates a soft radial gradient glow in the center.
    Performance: Generates at 1/10th scale to minimize Gaussian Blur cost.
    2026 Style: High-impact breathing pulse effect.
    """
    w, h = size
    # Downscale for performance
    scale = 10
    small_size = (max(1, w // scale), max(1, h // scale))
    inner_color = (*color, 255)  # Use full alpha for the base, control via MoviePy

    base = Image.new("RGBA", small_size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(base)

    circle_size = min(small_size) * 0.9
    left = (small_size[0] - circle_size) / 2
    top = (small_size[1] - circle_size) / 2
    draw.ellipse([left, top, left + circle_size, top + circle_size], fill=inner_color)

    glow = base.filter(ImageFilter.GaussianBlur(radius=circle_size / 3))
    glow_array = np.array(glow)

    # 2026 Style: Breathing pulse effect by modulating opacity
    # We use .fl() for temporal opacity because .set_opacity() is static in v1.0.3
    glow_clip = (
        ImageClip(glow_array)
        .set_duration(duration)
        .set_position("center")
        .resize(size)
    )

    def pulse_opacity(get_frame, t):
        # Organic pulse: sine wave with slight exponential decay for 'entry' feel
        # Base opacity + pulse amplitude
        current_op = opacity * (0.8 + 0.2 * math.sin(t * 3))
        return (get_frame(t).astype("float") * current_op).astype("uint8")

    return glow_clip.fl(pulse_opacity)


def create_flash_transition(size, duration=0.1, opacity=0.8):
    """Creates a white flash overlay with a snappy fade-out for high-energy transitions."""
    return (
        ColorClip(size=size, color=(255, 255, 255))
        .set_duration(duration)
        .set_opacity(opacity)
        .fadeout(duration)
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


def apply_zoom(clip, total_duration, start_scale=1.0, end_scale=1.15):
    """Applies a smooth exponential zoom effect for a premium feel (2026 trend)."""
    inv_duration = 1.0 / max(total_duration, 0.001)
    # Using exponential curve: scale = start * (end/start)^(t/duration)
    ratio = end_scale / start_scale
    log_ratio = math.log(ratio)

    return clip.resize(lambda t: start_scale * math.exp(log_ratio * t * inv_duration))


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


def apply_shake(clip, duration=0.2, amplitude=5):
    """Applies a high-frequency jitter/shake effect (2026 trend)."""

    def shake(t):
        if t > duration:
            return "center", "center"
        # High frequency noise-like oscillation
        dx = amplitude * math.sin(t * 80) * math.exp(-t * 10)
        dy = amplitude * math.cos(t * 70) * math.exp(-t * 10)
        return dx, dy

    # apply_shake usually works best on clips already positioned at center
    # This assumes the clip has a 'center' relative position
    return clip.set_position(shake, relative=True)


def apply_float(clip, duration, amplitude=0.01):
    """Applies a slow, organic floating motion."""

    def float_pos(t):
        # Slow Lissajous-like movement
        dx = amplitude * math.sin(t * 1.5)
        dy = amplitude * math.cos(t * 1.2)
        return 0.5 + dx, 0.5 + dy

    return clip.set_position(float_pos, relative=True)


def create_vignette(size, duration, opacity=0.4):
    """Creates a soft dark vignette to focus attention (2026 'bold minimal' look)."""
    w, h = size
    # Create at 1/4 scale to save memory/processing
    vw, vh = w // 4, h // 4
    vignette_img = Image.new("L", (vw, vh), 255)
    draw = ImageDraw.Draw(vignette_img)

    # Draw centered oval
    draw.ellipse([0, 0, vw, vh], fill=0)
    # Intense blur for soft falloff
    vignette_img = vignette_img.filter(ImageFilter.GaussianBlur(radius=vw / 4))

    vignette_array = np.array(vignette_img)
    # Convert to black RGBA with varying alpha
    rgba = np.zeros((vh, vw, 4), dtype="uint8")
    rgba[..., 3] = (vignette_array.astype("float") * opacity).astype("uint8")

    return ImageClip(rgba).set_duration(duration).set_position("center").resize(size)


def create_hook_clip(text, duration=2.0, font="Arial-Bold", fontsize=220):
    """Creates a high-impact 2-second hook title card with aggressive kinetic animations.
    2026 Trend: Oversized bold typography for immediate scroll-stop.
    """
    # Performance: Pre-calculate constants for the temporal lambda
    decay = -8.0
    freq = 15.0

    def hook_scale(t):
        # Snappier oscillation for 2026 'vibrate' feel
        return 1.0 + 0.4 * math.exp(decay * t) * math.cos(freq * t)

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
        .resize(hook_scale)
        .rotate(-2)  # High-impact tilt
    )

    return hook


def build_modern_captions(
    words, video_size, highlight_word="", font="Arial-Bold", phrase_mode=False
):
    """Builds word-by-word or phrase-based captions with kinetic animations.
    phrase_mode=True groups words into chunks for a 'minimal' look.
    """
    clips = []
    highlight_word = highlight_word.lower() if highlight_word else ""

    # Group words into phrases if requested
    if phrase_mode:
        chunks = []
        current_chunk = []
        for i, item in enumerate(words):
            current_chunk.append(item)
            if len(current_chunk) >= 3 or i == len(words) - 1:
                chunks.append(current_chunk)
                current_chunk = []
        process_items = []
        for chunk in chunks:
            process_items.append(
                {
                    "word": " ".join(str(x.get("word", "")).strip() for x in chunk),
                    "start": float(chunk[0].get("start", 0)),
                    "end": float(chunk[-1].get("end", 0)),
                }
            )
    else:
        process_items = words

    # Pre-compiled high-impact keywords for 2026 design style
    impact_keywords = {"NOT", "WHAT", "WHY", "HOW", "BEST", "FAST", "EASY", "NEW", "TOP"}

    for item in process_items:
        word = str(item.get("word", "")).strip()
        start = float(item.get("start", 0))
        end = float(item.get("end", start + 0.5))

        if not word:
            continue

        duration = max(end - start, 0.4)
        clean_word = NON_ALPHANUMERIC_RE.sub("", word).lower()

        # Modern highlighting: Bright Neon Green (#00FF00)
        # Highlight based on target word, length, or impact keywords
        is_highlight = (
            (highlight_word and highlight_word in clean_word)
            or len(clean_word) > 8
            or word.upper() in impact_keywords
        )
        color = "#00FF00" if is_highlight else "white"

        # 2026 Style: Aggressive sizing for focus
        font_size = 190 if is_highlight else 145
        if phrase_mode:
            font_size = int(font_size * 0.85)

        # Text clip - Bold, high-contrast (ensure it fits in safe margins)
        safe_width = int(video_size[0] * 0.85)
        txt = (
            get_text_clip(
                word.upper(),
                fontsize=font_size,
                color=color,
                font=font,
                stroke_color="black",
                stroke_width=7,
                method="caption" if " " in word else "label",
                size=(safe_width, None),
                align="center",
            )
            .set_start(start)
            .set_duration(duration)
            .set_position(("center", "center"))
        )

        # Kinetic "pop" animation (Aggressive 1.5 scale for 2026)
        txt = apply_kinetic_pop(txt, duration=0.15, scale=1.5)

        # 2026 Style: Subtle float
        txt = apply_float(txt, duration, amplitude=0.005)

        # Drop shadow (Modern Offset)
        shadow = (
            get_text_clip(
                word.upper(),
                fontsize=font_size,
                color="black",
                font=font,
                method="caption" if " " in word else "label",
                size=(safe_width, None),
                align="center",
            )
            .set_start(start)
            .set_duration(duration)
            .set_position(("center", "center"))
            .set_opacity(0.8)
        )
        # Offset shadow slightly
        # Performance: Use a static tuple instead of a lambda to avoid thousands of function calls
        shadow = shadow.set_position((0.505, 0.505), relative=True)

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
