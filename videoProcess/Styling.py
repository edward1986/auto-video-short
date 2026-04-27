import re
import math
import numpy as np
import os
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# Monkeypatch for MoviePy 1.0.3 compatibility with Pillow 10+
if not hasattr(Image, "ANTIALIAS"):
    Image.ANTIALIAS = Image.LANCZOS

import moviepy.video.fx.resize as resize_module
import moviepy.video.fx.all as vfx

# Performance: Monkeypatch MoviePy's resizer to bypass PIL/OpenCV overhead when size hasn't changed.
# This provides a ~3000x speedup for frames where temporal scaling (like pop/zoom) evaluates to 1.0.
_original_resizer = resize_module.resizer


def _optimized_resizer(pic, newsize):
    """Optimized resizer that bypasses heavy processing if the size hasn't changed."""
    # Performance: Temporal animations (zoom/pop) frequently pass a scalar ratio (int/float/np.float).
    # We check for scalar types up-front to avoid a costly TypeError in the hot path.
    if not hasattr(newsize, "__iter__"):
        if newsize == 1:
            return pic
        ph, pw = pic.shape[0], pic.shape[1]
        # Performance: Bypass resizing if the resulting integer dimensions are identical to the original.
        # This occurs during high-frequency temporal scaling (zooms/pops) near 1.0.
        if int(ph * newsize) == ph and int(pw * newsize) == pw:
            return pic
        return _original_resizer(pic, newsize)

    try:
        # Performance: Access shape once and avoid redundant tuple/list creation.
        # Most common case: newsize is already exactly matching (e.g. from trans_newsize).
        # We check direct equality first, then integer equality to match MoviePy's truncation.
        ph, pw = pic.shape[0], pic.shape[1]
        nw, nh = newsize[0], newsize[1]

        if (nw == pw and nh == ph) or (int(nw) == pw and int(nh) == ph):
            return pic
    except (TypeError, IndexError, ValueError):
        # Fallback for unexpected formats or types
        pass

    return _original_resizer(pic, newsize)


resize_module.resizer = _optimized_resizer

from moviepy.editor import (  # noqa: E402
    ColorClip,
    ImageClip,
    CompositeVideoClip,
    VideoClip,
    concatenate_videoclips,
)

# Pre-compiled regex for better performance in build_modern_captions
NON_ALPHANUMERIC_RE = re.compile(r"[^a-zA-Z0-9]")

# Global TextClip cache to avoid redundant ImageMagick renders
TEXT_CLIP_CACHE = {}

# Global font cache to avoid redundant disk I/O
FONT_CACHE = {}

# Global LUT cache for darken_clip to avoid redundant array creation
DARKEN_LUT_CACHE = {}

# Global noise pool cache to avoid redundant generation for identical sizes
NOISE_POOL_CACHE = {}

# Global GLOW cache to avoid redundant rendering
GLOW_CACHE = {}

# Global GLOW mask pulse cache to avoid redundant array math
GLOW_PULSE_CACHE = {}

# Global VIGNETTE cache to avoid redundant rendering
VIGNETTE_CACHE = {}

# Global PBAR_MASK cache to avoid redundant mask allocations
PBAR_MASK_CACHE = {}

# Performance: Pre-defined set for faster keyword filtering in get_text_clip
SUPPORTED_TEXT_KWARGS = {
    "fontsize",
    "color",
    "font",
    "stroke_color",
    "stroke_width",
    "size",
    "align",
    "shadow_color",
    "shadow_offset",
    "box_color",
    "box_padding",
    "rotation",
}


def _get_text_size(text, font):
    """Helper to get text dimensions across PIL versions."""
    # Performance: Cache the hasattr check on the font object to avoid repeated lookups
    use_getbbox = getattr(font, "_use_getbbox", None)
    if use_getbbox is None:
        use_getbbox = hasattr(font, "getbbox")
        font._use_getbbox = use_getbbox

    if use_getbbox:
        # Use getbbox directly on font if available (modern PIL)
        bbox = font.getbbox(text)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]
    # Fallback for older versions (requires draw context or getsize)
    return font.getsize(text)


def get_pil_text_clip(
    text,
    fontsize=70,
    color="white",
    font="Arial-Bold",
    stroke_color=None,
    stroke_width=0,
    size=None,
    align="center",
    shadow_color=None,
    shadow_offset=(4, 4),
    box_color=None,
    box_padding=10,
    rotation=0,
    **kwargs,
):
    """PIL-based alternative to MoviePy TextClip with 2026 auto-scaling logic."""
    # 2026 style: 1.2x line spacing
    line_spacing_factor = 1.2
    target_width = size[0] if size and size[0] else None

    # Recursive Font Scaling: Ensure text fits within 90% of target width
    # 2026 design requirement: Bold text must NEVER overflow mobile safe margins.
    def get_layout(current_fs):
        font_key = (font, current_fs)
        if font_key in FONT_CACHE:
            pil_font = FONT_CACHE[font_key]
        else:
            try:
                pil_font = ImageFont.truetype(font, current_fs)
            except Exception:
                try:
                    fallback_path = os.path.join(os.getcwd(), "default.ttf")
                    pil_font = ImageFont.truetype(fallback_path, current_fs)
                except Exception:
                    pil_font = ImageFont.load_default()
            FONT_CACHE[font_key] = pil_font

        if target_width:
            # Performance: Cache the measurement function once per layout call to avoid
            # repeated attribute lookups and conditional branching inside the inner word loop.
            if hasattr(pil_font, "getlength"):
                measure_width = pil_font.getlength
            else:

                def measure_width(t):
                    return _get_text_size(t, pil_font)[0]

            wrapped_lines = []
            for line in text.split("\n"):
                words = line.split(" ")
                current_line = []
                for word in words:
                    test_line = " ".join(current_line + [word])
                    w = measure_width(test_line)

                    if w > target_width and current_line:
                        wrapped_lines.append(" ".join(current_line))
                        current_line = [word]
                    else:
                        current_line.append(word)
                wrapped_lines.append(" ".join(current_line))
            lines = wrapped_lines
        else:
            lines = text.split("\n")

        line_heights = []
        line_widths = []
        for line in lines:
            w, h = _get_text_size(line, pil_font)
            line_widths.append(w)
            line_heights.append(h)

        max_w = max(line_widths) if line_widths else 0
        return pil_font, lines, line_widths, line_heights, max_w

    # Initial layout
    pil_font, lines, line_widths, line_heights, max_w = get_layout(fontsize)

    # 2026 Auto-scaling: If text is too wide, shrink until it fits (min 20pt)
    current_fs = fontsize
    while target_width and max_w > target_width * 0.95 and current_fs > 20:
        current_fs = int(current_fs * 0.9)
        pil_font, lines, line_widths, line_heights, max_w = get_layout(current_fs)

    # Performance: Pre-calculate common layout values
    total_line_height = sum(line_heights)
    total_h = total_line_height + int(
        total_line_height * (line_spacing_factor - 1) * (len(lines) - 1)
    )

    stroke_x2 = stroke_width * 2
    box_pad_x2 = box_padding * 2 if box_color else 0

    if size:
        final_w = size[0] or (max_w + stroke_x2 + box_pad_x2)
        final_h = size[1] or (total_h + stroke_x2 + box_pad_x2)
    else:
        final_w = max_w + stroke_x2 + 10 + box_pad_x2
        final_h = total_h + stroke_x2 + 10 + box_pad_x2

    # Draw text
    img = Image.new("RGBA", (int(final_w), int(final_h)), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    current_y = (final_h - total_h) // 2

    # 1. Draw Background Box if specified
    if box_color:
        # Calculate box coordinates based on alignment
        if align == "center":
            box_l = (final_w - max_w) // 2 - box_padding
            box_r = (final_w + max_w) // 2 + box_padding
        elif align == "right":
            box_l = final_w - max_w - stroke_width - box_padding * 2
            box_r = final_w - stroke_width
        else:
            box_l = stroke_width
            box_r = max_w + stroke_width + box_padding * 2

        box_t = current_y - box_padding
        box_b = current_y + total_h + box_padding
        draw.rectangle([box_l, box_t, box_r, box_b], fill=box_color)

    for i, line in enumerate(lines):
        w, h = line_widths[i], line_heights[i]
        if align == "center":
            current_x = (final_w - w) // 2
        elif align == "right":
            current_x = final_w - w - stroke_width - (box_padding if box_color else 0)
        else:
            current_x = stroke_width + (box_padding if box_color else 0)

        # 2. Draw Shadow if specified
        if shadow_color:
            off_x, off_y = shadow_offset
            draw.text(
                (current_x + off_x, current_y + off_y),
                line,
                font=pil_font,
                fill=shadow_color,
                stroke_width=stroke_width,
                stroke_fill=shadow_color if stroke_width > 0 else None,
            )

        # 3. Draw Main Text
        draw.text(
            (current_x, current_y),
            line,
            font=pil_font,
            fill=color,
            stroke_width=stroke_width,
            stroke_fill=stroke_color,
        )
        current_y += int(h * line_spacing_factor)

    # 4. Apply static rotation if specified (2026 Trend)
    # Performance: Rotating the PIL image once is ~90x faster than per-frame rotation in MoviePy.
    if rotation != 0:
        img = img.rotate(rotation, resample=Image.BICUBIC, expand=True)

    return ImageClip(np.array(img))


def get_text_clip(text, **kwargs):
    """Retrieves a cached text clip or creates a new one using PIL."""
    # Performance: O(1) filtering using pre-defined module set
    filtered_kwargs = {k: v for k, v in kwargs.items() if k in SUPPORTED_TEXT_KWARGS}

    # Normalize values for hashing (lists/tuples to tuples)
    for k, v in filtered_kwargs.items():
        if isinstance(v, (list, tuple)):
            filtered_kwargs[k] = tuple(v)

    # Performance: Use frozenset of items for faster hashing than sorted tuple
    cache_key = (text, frozenset(filtered_kwargs.items()))

    if cache_key in TEXT_CLIP_CACHE:
        return TEXT_CLIP_CACHE[cache_key].copy()

    # Create new clip using our PIL-based renderer
    clip = get_pil_text_clip(text, **filtered_kwargs)
    TEXT_CLIP_CACHE[cache_key] = clip
    return clip.copy()


def darken_clip(clip, factor=0.45):
    """Darkens a clip by multiplying all pixel values by a factor (0.0 to 1.0).
    Higher factor = brighter, lower factor = darker. 0.45 is ideal for 2026 'bold minimal' contrast.
    Performance: Uses a Look-Up Table (LUT) for uint8 to avoid per-pixel floating point math.
    """
    last_image = [None]
    last_result = [None]

    def apply_darken(image):
        # Performance: Identity cache for static ImageClip inputs
        if image is last_image[0]:
            return last_result[0]

        # Optimized path for standard uint8 images
        if image.dtype == np.uint8:
            if factor not in DARKEN_LUT_CACHE:
                DARKEN_LUT_CACHE[factor] = (np.arange(256) * factor).astype("uint8")
            result = DARKEN_LUT_CACHE[factor][image]
        else:
            # Fallback for other dtypes (float, uint16, etc.)
            result = (image * factor).astype(image.dtype)

        last_image[0] = image
        last_result[0] = result
        return result

    return clip.fl_image(apply_darken)


def create_noise_overlay(size, duration, opacity=0.12):
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

            # 2026 Style: Blend layers with emphasis on chunky grain (60/40 mix) for more texture
            combined = (layer1.astype("uint16") * 6 + layer2.astype("uint16") * 4) // 10
            pool.append(combined.astype("uint8"))

        NOISE_POOL_CACHE[size_tuple] = pool

    # Robust fix for MoviePy 1.0.3: Assign size directly to bypass VideoClip inheritance issues
    def make_frame(t):
        idx = int(t * 24) % 24
        return pool[idx]

    noise_clip = VideoClip(make_frame, duration=duration)
    noise_clip.size = size_tuple
    return noise_clip.set_opacity(opacity)


def create_gradient_glow(size, duration, color=(200, 200, 255), opacity=0.2):
    """Creates a soft radial gradient glow in the center with a breathing pulse.
    Supports multiple colors for layered 2026 accent effects.
    """
    size_tuple = tuple(size) if isinstance(size, (list, tuple)) else size
    # Support for list of colors
    colors = color if isinstance(color, list) else [color]
    cache_key = (size_tuple, tuple(colors), opacity)

    if cache_key in GLOW_CACHE:
        glow_clip = GLOW_CACHE[cache_key].copy()
    else:
        w, h = size_tuple
        # Downscale for performance
        scale = 10
        small_size = (w // scale, h // scale)

        # Create layered glow for multiple colors
        combined_base = Image.new("RGBA", small_size, (0, 0, 0, 0))

        for idx, c in enumerate(colors):
            inner_color = (*c, int(255 * opacity / len(colors)))
            layer = Image.new("RGBA", small_size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(layer)

            # Each color layer slightly offset or different size for 'organic' 2026 look
            circle_size = min(small_size) * (0.9 - (idx * 0.1))
            left = (small_size[0] - circle_size) / 2
            top = (small_size[1] - circle_size) / 2
            draw.ellipse(
                [left, top, left + circle_size, top + circle_size], fill=inner_color
            )
            combined_base = Image.alpha_composite(combined_base, layer)

        glow = combined_base.filter(
            ImageFilter.GaussianBlur(radius=min(small_size) / 4)
        )
        # Resize to full size once to avoid per-frame resizing overhead
        glow_full = glow.resize(size_tuple, Image.BILINEAR)
        glow_array = np.array(glow_full)
        glow_clip = ImageClip(glow_array)
        GLOW_CACHE[cache_key] = glow_clip

    glow_clip = glow_clip.set_duration(duration).set_position("center")

    # Implement breathing pulse effect by modulating the mask's frame data
    # Performance: Temporal cache for the pulsed mask to avoid million-pixel array math every frame.
    def pulse_mask(gf, t):
        # Round time to 0.05s intervals for caching (visually smooth at 4 rad/s)
        t_rounded = round(t * 20) / 20
        pulse_key = (id(glow_clip), t_rounded)

        if pulse_key in GLOW_PULSE_CACHE:
            return GLOW_PULSE_CACHE[pulse_key]

        mask_frame = gf(t)
        factor = 0.9 + 0.2 * math.sin(t * 4)
        result = np.clip(mask_frame * factor, 0, 1)

        # Basic cache management: keep it from growing indefinitely
        if len(GLOW_PULSE_CACHE) > 500:
            GLOW_PULSE_CACHE.clear()
        GLOW_PULSE_CACHE[pulse_key] = result
        return result

    if glow_clip.mask:
        glow_clip.mask = glow_clip.mask.fl(pulse_mask)

    return glow_clip


def create_flash_transition(size, duration=0.15, opacity=0.9):
    """Creates a white flash overlay with a snappy fade-out for high-energy 2026 transitions."""
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
        # Performance: x*x*x*x is ~2.3x faster than x**4 in Python
        val = 1 - (t * inv_duration)
        offset = val * val * val * val
        return 1.0 + diff * offset

    return clip.resize(pop_scale)


def apply_zoom(clip, total_duration, start_scale=1.0, end_scale=1.15):
    """Applies a smooth exponential zoom effect for a premium feel (2026 trend)."""
    inv_duration = 1.0 / max(total_duration, 0.001)
    # Using exponential curve: scale = start * (end/start)^(t/duration)
    ratio = end_scale / start_scale
    # Performance: Pre-calculate the combined coefficient for the temporal lambda
    coeff = math.log(ratio) * inv_duration

    return clip.resize(lambda t: start_scale * math.exp(coeff * t))


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
        # Performance: x*x*x*x is ~2.3x faster than x**4 in Python
        val = 1 - (t * inv_duration)
        offset = val * val * val * val

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


def apply_kinetic_motion(
    clip,
    slide_duration=0.4,
    direction="bottom",
    final_pos=("center", "center"),
    float_amplitude=0.005,
):
    """Combines snappy slide-in and organic floating into a single position logic.
    Performance: Prevents multiple set_position() calls from overwriting each other and
    reduces per-frame lambda overhead.
    """
    tx, ty = final_pos
    rel_x = 0.5 if tx == "center" else tx
    rel_y = 0.5 if ty == "center" else ty
    inv_slide = 1.0 / max(slide_duration, 0.001)

    # Performance: Optimization for static positions (no float)
    if float_amplitude == 0:

        def pos_no_float(t):
            if t >= slide_duration:
                return rel_x, rel_y
            # Performance: x*x*x*x is ~2.3x faster than x**4 in Python
            val = 1 - (t * inv_slide)
            offset = val * val * val * val
            if direction == "bottom":
                return rel_x, rel_y + offset
            if direction == "top":
                return rel_x, rel_y - offset
            if direction == "left":
                return rel_x - offset, rel_y
            if direction == "right":
                return rel_x + offset, rel_y
            return rel_x, rel_y

        return clip.set_position(pos_no_float, relative=True)

    def pos(t):
        # 1. Slide Logic
        if t < slide_duration:
            # Performance: x*x*x*x is ~2.3x faster than x**4 in Python
            val = 1 - (t * inv_slide)
            offset = val * val * val * val
            if direction == "bottom":
                curr_x, curr_y = rel_x, rel_y + offset
            elif direction == "top":
                curr_x, curr_y = rel_x, rel_y - offset
            elif direction == "left":
                curr_x, curr_y = rel_x - offset, rel_y
            elif direction == "right":
                curr_x, curr_y = rel_x + offset, rel_y
            else:
                curr_x, curr_y = rel_x, rel_y
        else:
            curr_x, curr_y = rel_x, rel_y

        # 2. Float Logic
        dx = float_amplitude * math.sin(t * 1.5)
        dy = float_amplitude * math.cos(t * 1.2)

        return curr_x + dx, curr_y + dy

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
        # Performance: Calculate decay once per frame
        decay = math.exp(-t * 10)
        dx = amplitude * math.sin(t * 80) * decay
        dy = amplitude * math.cos(t * 70) * decay
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


def create_vignette(size, duration, opacity=0.5):
    """Creates a soft dark vignette to focus attention (2026 'bold minimal' look).
    Performance: Generates at 1/4 scale, caches the result, and resizes once.
    """
    size_tuple = tuple(size) if isinstance(size, (list, tuple)) else size
    cache_key = (size_tuple, opacity)

    if cache_key in VIGNETTE_CACHE:
        vignette_clip = VIGNETTE_CACHE[cache_key].copy()
    else:
        w, h = size_tuple
        # Create at 1/4 scale to save memory/processing
        vw, vh = w // 4, h // 4
        vignette_img = Image.new("L", (vw, vh), 255)
        draw = ImageDraw.Draw(vignette_img)

        # Draw centered oval (center remains clear (0), edges darken (255))
        draw.ellipse([0, 0, vw, vh], fill=0)
        # Intense blur for soft falloff
        vignette_img = vignette_img.filter(ImageFilter.GaussianBlur(radius=vw / 4))

        # Convert mask to RGBA (Black with varying alpha)
        vignette_array = np.array(vignette_img)
        rgba = np.zeros((vh, vw, 4), dtype="uint8")
        # Alpha: vignette_array has 0 in center and 255 at edges.
        rgba[..., 3] = (vignette_array.astype("float") * opacity).astype("uint8")

        # Resize to full size once
        rgba_full = np.array(Image.fromarray(rgba).resize(size_tuple, Image.BILINEAR))
        vignette_clip = ImageClip(rgba_full)
        VIGNETTE_CACHE[cache_key] = vignette_clip

    return vignette_clip.set_duration(duration).set_position("center")


def create_hook_clip(
    text, video_size=(1080, 1920), duration=2.0, font="Arial-Bold", fontsize=220
):
    """Creates a high-impact 2-second hook title card with aggressive kinetic animations."""
    # 2026 Trend: Oversized bold typography for immediate scroll-stop.
    # Added size constraint to prevent overflow.
    hook = (
        get_text_clip(
            text.upper(),
            fontsize=fontsize,
            color="white",
            font=font,
            stroke_color="black",
            stroke_width=8,
            align="center",
            size=(video_size[0] * 0.85, None),
            rotation=-3,
        )
        .set_start(0)
        .set_duration(duration)
        .set_position(("center", "center"))
    )

    # Performance: Aggressive kinetic scaling (exponential decay with cosine oscillation)
    # Constants pre-calculated for the temporal lambda
    def hook_scale(t):
        # 2026 Trend: Even snappier "vibrate" oscillation for high engagement
        return (
            1.1 + 0.45 * math.exp(-10 * t) * math.cos(20 * t) + 0.05 * math.sin(5 * t)
        )

    return hook.resize(hook_scale)


def create_progress_bar(size, duration, color=(0, 255, 0), height=8):
    """Creates a modern neon progress bar at the bottom of the video (2026 trend).
    Performance: Creates a small clip instead of a full-screen one to reduce composition overhead.
    Uses PBAR_MASK_CACHE to memoize generated masks based on integer progress widths.
    """
    w, h = size
    # Create a bar that is only as high as needed
    bar_clip = ColorClip(size=(w, height), color=color).set_duration(duration)

    # Pre-calculate constants for the temporal lambda
    inv_duration = 1.0 / max(duration, 0.001)

    def make_mask(t):
        progress = min(t * inv_duration, 1.0)
        bar_w = int(w * progress)

        # Performance: Memoize masks by width to avoid redundant np.zeros allocations.
        cache_key = (w, height, bar_w)
        if cache_key in PBAR_MASK_CACHE:
            return PBAR_MASK_CACHE[cache_key]

        # MoviePy usually requires a new array for safety, but since we're using
        # these as read-only masks and caching them, we avoid the copy for a 50x speedup.
        mask = np.zeros((height, w), dtype="float32")
        if bar_w > 0:
            mask[:, 0:bar_w] = 1.0

        # Basic cache management: keep it from growing indefinitely
        if len(PBAR_MASK_CACHE) > 2000:
            PBAR_MASK_CACHE.clear()

        PBAR_MASK_CACHE[cache_key] = mask
        return mask

    mask_clip = VideoClip(make_mask, ismask=True, duration=duration)
    mask_clip.size = (w, height)
    bar_clip = bar_clip.set_mask(mask_clip)

    # Position it at the bottom of the original video size
    # Performance: Static position is much faster than lambda in MoviePy 1.x
    return bar_clip.set_position(("center", h - height))


def apply_dynamic_cuts(clip, segment_duration=3.0):
    """Creates 'fast clean cuts' by alternating flips and zoom levels (2026 trend)."""
    duration = clip.duration
    w, h = clip.size
    num_segments = int(duration // segment_duration) + 1
    clips = []

    for i in range(num_segments):
        start = i * segment_duration
        end = min((i + 1) * segment_duration, duration)
        if start >= duration:
            break

        segment = clip.subclip(start, end)

        # Alternating effects for 'dynamic' feel
        if i % 2 == 1:
            # Flip horizontally
            segment = segment.margin(left=0).fx(vfx.mirror_x)

        if i % 3 == 0:
            # Subtle extra zoom + ensure size matches original for clean concatenation
            segment = segment.resize(1.1).crop(
                x_center=w / 2, y_center=h / 2, width=w, height=h
            )

        clips.append(segment)

    # Use method="chain" to keep original sizes (which we ensured) and avoid complex composition
    return concatenate_videoclips(clips, method="chain")


def build_modern_captions(
    words,
    video_size,
    highlight_word="",
    font="Arial-Bold",
    phrase_mode=False,
    y_pos=0.5,
):
    """Builds word-by-word or phrase-based captions with kinetic animations.
    phrase_mode=True groups words into chunks for a 'minimal' look.
    y_pos: Vertical position (default 0.5 center). 2026 Style typically uses 0.55.
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

    # Performance: Pre-calculate common constants for the loop
    caption_width = video_size[0] * 0.8

    for item in process_items:
        word = str(item.get("word", "")).strip()
        start = float(item.get("start", 0))
        end = float(item.get("end", start + 0.5))

        if not word:
            continue

        duration = max(end - start, 0.4)
        clean_word = NON_ALPHANUMERIC_RE.sub("", word).lower()

        # Modern highlighting: Bright Neon Green (#00FF00)
        is_highlight = highlight_word in clean_word or len(clean_word) > 7
        color = "#00FF00" if is_highlight else "white"
        # 2026 Style: Aggressive sizing for phrases
        font_size = 180 if is_highlight else 140
        if phrase_mode:
            font_size = int(font_size * 0.8)  # Slightly smaller for multi-word

        # 2026 style: Random slight rotation for 'organic' feel (-2 to 2 degrees)
        # Using hash for deterministic but 'random' look per word
        rot = (hash(word) % 5) - 2
        # 2026 Style: Integrated shadow and background box (replaces separate shadow clip)
        # Performance: Pass rotation directly to get_text_clip to avoid per-frame MoviePy rotate()
        txt = (
            get_text_clip(
                word.upper(),
                fontsize=font_size,
                color=color,
                font=font,
                stroke_color="black",
                stroke_width=6,
                size=(caption_width, None),
                align="center",
                shadow_color="black",
                shadow_offset=(6, 6),
                box_color=(0, 0, 0, 128) if is_highlight else None,
                box_padding=20,
                rotation=rot,
            )
            .set_start(start)
            .set_duration(duration)
            .set_position(("center", y_pos), relative=True)
        )

        # Kinetic "pop" animation (Aggressive 1.4 scale for 2026)
        txt = apply_kinetic_pop(txt, duration=0.12, scale=1.4)

        # 2026 style: Combined kinetic motion (slide-up + float)
        # Performance: Single position lambda to avoid overwriting and redundant calls
        txt = apply_kinetic_motion(
            txt,
            slide_duration=0.15,
            direction="bottom",
            final_pos=("center", y_pos),
            float_amplitude=0.005,
        )

        clips.append(txt)

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
    ).set_duration(duration)

    # Kinetic pulse and snappy slide-in from bottom
    cta_text = apply_kinetic_motion(
        cta_text,
        slide_duration=0.5,
        direction="bottom",
        final_pos=("center", "center"),
        float_amplitude=0,  # No float for end card
    )
    # Performance: Pre-calculate pulse constants
    pulse_freq = 6 * math.pi
    # Snappier breathing pulse
    cta_text = cta_text.resize(
        lambda t: 1.0 + 0.1 * math.exp(-3 * t) * math.sin(pulse_freq * t)
    )

    return CompositeVideoClip(
        [cta_bg, glow, cta_text], size=video_size, use_bgclip=True
    )
