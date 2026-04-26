from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "scratch" / "bilibili_covers_v1"
FRAME_DIR = OUT_DIR / "source_frames"
WIDTH, HEIGHT = 1920, 1200

FONT_BOLD = Path(r"C:\Windows\Fonts\msyhbd.ttc")
FONT_REGULAR = Path(r"C:\Windows\Fonts\msyh.ttc")


def font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size=size)


def cover_resize(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    src_w, src_h = image.size
    dst_w, dst_h = size
    scale = max(dst_w / src_w, dst_h / src_h)
    new_w = int(src_w * scale + 0.5)
    new_h = int(src_h * scale + 0.5)
    resized = image.resize((new_w, new_h), Image.Resampling.LANCZOS)
    left = (new_w - dst_w) // 2
    top = (new_h - dst_h) // 2
    return resized.crop((left, top, left + dst_w, top + dst_h))


def add_gradients(base: Image.Image, accent: tuple[int, int, int]) -> Image.Image:
    image = base.convert("RGBA")
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    for x in range(WIDTH):
        alpha = int(190 * max(0, 1 - x / 1250))
        draw.line((x, 0, x, HEIGHT), fill=(0, 0, 0, alpha))

    for y in range(HEIGHT):
        bottom_alpha = int(155 * max(0, (y - 560) / 640))
        top_alpha = int(80 * max(0, 1 - y / 420))
        alpha = min(210, bottom_alpha + top_alpha)
        draw.line((0, y, WIDTH, y), fill=(0, 0, 0, alpha))

    draw.polygon(
        [(0, HEIGHT), (WIDTH, HEIGHT), (WIDTH, HEIGHT - 170), (0, HEIGHT - 20)],
        fill=(*accent, 45),
    )
    draw.polygon(
        [(WIDTH - 540, 0), (WIDTH, 0), (WIDTH, 460)],
        fill=(*accent, 36),
    )
    return Image.alpha_composite(image, overlay)


def text_bbox(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, fnt: ImageFont.FreeTypeFont):
    return draw.textbbox(xy, text, font=fnt)


def draw_shadow_text(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    fnt: ImageFont.FreeTypeFont,
    fill: tuple[int, int, int, int],
    shadow: tuple[int, int, int, int] = (0, 0, 0, 210),
    offset: int = 4,
) -> None:
    x, y = xy
    draw.text((x + offset, y + offset), text, font=fnt, fill=shadow)
    draw.text((x, y), text, font=fnt, fill=fill)


def draw_chip(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    fnt: ImageFont.FreeTypeFont,
    accent: tuple[int, int, int],
) -> int:
    x, y = xy
    bbox = text_bbox(draw, (x, y), text, fnt)
    w = bbox[2] - bbox[0] + 44
    h = bbox[3] - bbox[1] + 26
    draw.rounded_rectangle(
        (x, y, x + w, y + h),
        radius=24,
        fill=(10, 12, 14, 180),
        outline=(*accent, 230),
        width=3,
    )
    draw.text((x + 22, y + 10), text, font=fnt, fill=(245, 245, 238, 255))
    return x + w + 22


def build_cover(
    frame_path: Path,
    out_path: Path,
    part_label: str,
    accent: tuple[int, int, int],
    tone: str,
) -> None:
    frame = Image.open(frame_path).convert("RGB")
    base = cover_resize(frame, (WIDTH, HEIGHT))
    base = ImageEnhance.Contrast(base).enhance(1.08)
    base = ImageEnhance.Color(base).enhance(0.95)
    base = base.filter(ImageFilter.UnsharpMask(radius=1.6, percent=125, threshold=4))
    image = add_gradients(base, accent)
    draw = ImageDraw.Draw(image)

    f_ghost = font(FONT_BOLD, 140)
    f_part = font(FONT_BOLD, 52)
    f_sub = font(FONT_BOLD, 62)
    f_line = font(FONT_REGULAR, 42)
    f_chip = font(FONT_BOLD, 34)
    f_note = font(FONT_REGULAR, 30)

    x = 112
    y = 128
    draw.rounded_rectangle((x - 28, y - 34, x + 1030, y + 380), radius=36, fill=(0, 0, 0, 86))
    draw.rectangle((x - 28, y - 34, x - 12, y + 380), fill=(*accent, 255))

    draw_shadow_text(draw, (x, y), "Ghost Yotei", f_ghost, (255, 248, 226, 255), offset=5)
    draw_shadow_text(draw, (x + 4, y + 154), part_label, f_part, (*accent, 255), offset=3)
    draw_shadow_text(draw, (x + 4, y + 226), "Codex 工作流 AI 试验 Beta", f_sub, (255, 255, 255, 255), offset=4)
    draw.text((x + 8, y + 310), tone, font=f_line, fill=(226, 230, 224, 245))

    chip_y = 820
    chip_x = 112
    chip_x = draw_chip(draw, (chip_x, chip_y), "英语学习自用", f_chip, accent)
    chip_x = draw_chip(draw, (chip_x, chip_y), "官方英文硬字幕", f_chip, accent)
    draw_chip(draw, (chip_x, chip_y), "官方中文字幕", f_chip, accent)

    draw.rounded_rectangle((112, 925, 1035, 1048), radius=28, fill=(0, 0, 0, 154))
    draw.text((142, 946), "非完整精校｜字幕时间轴可能存在误差", font=f_line, fill=(255, 242, 214, 255))
    draw.text((142, 998), "workflow proof / beta release", font=f_note, fill=(215, 218, 212, 235))

    draw.rounded_rectangle((1490, 100, 1810, 205), radius=26, fill=(*accent, 220))
    draw.text((1533, 124), "中英字幕", font=f_part, fill=(16, 18, 20, 255))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(out_path, quality=95)


def main() -> None:
    covers = [
        ("part01", "PART 01", (226, 174, 76), "官方中英字幕匹配｜Codex AI 工作流实验"),
        ("part02", "PART 02", (120, 196, 108), "翻译校对 + 时间轴匹配｜英语学习自用"),
        ("part03", "PART 03", (210, 82, 72), "OCR 清洗与字幕复核｜非商业精校版本"),
        ("part04", "PART 04", (88, 184, 220), "硬字幕烧录成品｜Codex workflow beta"),
    ]
    for stem, label, accent, tone in covers:
        build_cover(
            FRAME_DIR / f"{stem}.png",
            OUT_DIR / f"ghost_yotei_{stem}_cover.png",
            label,
            accent,
            tone,
        )

    build_cover(
        FRAME_DIR / "part01.png",
        OUT_DIR / "ghost_yotei_workflow_beta_cover.png",
        "WORKFLOW BETA",
        (238, 190, 84),
        "英语学习自用｜官方中英字幕匹配流程｜非完整精校",
    )


if __name__ == "__main__":
    main()
