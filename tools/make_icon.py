"""วาดไอคอน QuickNote (sticky note แบบ flat) แล้วบันทึกเป็น assets/icon.ico

ใช้งาน:
    python tools/make_icon.py [--preview PATH.png]

WHY: วาดแต่ละขนาดแยกกันที่ความละเอียด 4 เท่าแล้วย่อลง เพื่อให้ขนาดเล็ก (16/20/24)
ตัดเส้นข้อความออกได้ และยังคมชัด ถ้าปล่อยให้ Pillow ย่อจากภาพ 256 ตัวเดียว
เส้นข้อความจะกลายเป็นจุดเทาเบลอที่ 16px
"""
from __future__ import annotations

import argparse
import struct
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
ICO_PATH = ROOT / "assets" / "icon.ico"

SIZES = [16, 20, 24, 32, 48, 256]
TEXT_MIN_SIZE = 32  # ต่ำกว่านี้เส้นข้อความจะเป็นแค่ noise จึงไม่วาด
SUPERSAMPLE = 4

BODY = (255, 224, 102, 255)    # #FFE066 ตัวกระดาษ
FOLD = (232, 195, 59, 255)     # #E8C33B มุมพับ
OUTLINE = (212, 175, 55, 255)  # เส้นขอบเข้มกว่าตัวกระดาษเล็กน้อย
TEXT = (150, 150, 150, 255)    # เส้นข้อความสีเทา
PREVIEW_BG = (242, 242, 244, 255)


def render(size: int) -> Image.Image:
    """วาดไอคอนหนึ่งขนาด คืนค่าเป็น RGBA ที่ย่อจาก supersample แล้ว"""
    k = SUPERSAMPLE
    S = size * k

    def px(frac: float) -> int:
        return round(frac * S)

    margin = 0.0625  # 1/16 ของความกว้าง -> 1px ที่ 16 และ 16px ที่ 256
    radius = px(0.12)
    fold = px(0.22)
    outline_w = k  # 1 pixel ในขนาดจริง
    overshoot = 2 * k

    left, top = px(margin), px(margin)
    right, bottom = px(1 - margin), px(1 - margin)  # ขอบแบบ exclusive
    outer = (left, top, right - 1, bottom - 1)

    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # ขอบ = วาดรูปเต็มด้วยสีขอบ แล้ววาดตัวกระดาษทับให้ขอบเหลือหนึ่งพิกเซล
    draw.rounded_rectangle(outer, radius=radius, fill=OUTLINE)
    draw.rounded_rectangle(
        (left + outline_w, top + outline_w, right - 1 - outline_w, bottom - 1 - outline_w),
        radius=max(0, radius - outline_w),
        fill=BODY,
    )

    # มุมพับ: สามเหลี่ยมด้านในมุมขวาล่าง (มุมฉากอยู่ที่ C) ดูเป็นกระดาษพับกลับ
    ax, ay = right - fold, bottom - 1  # A บนขอบล่าง
    bx, by = right - 1, bottom - 1 - fold  # B บนขอบขวา
    cx, cy = right - fold, bottom - 1 - fold  # C มุมด้านในของสามเหลี่ยม
    draw.polygon([(ax, ay), (bx, by), (cx, cy)], fill=FOLD)

    # เส้นข้อความ 3 บรรทัด (ข้ามในขนาดเล็ก)
    if size >= TEXT_MIN_SIZE:
        thick = max(k, round(0.018 * S))
        x0 = px(margin + 0.16)
        x_full = px(1 - margin - 0.16)
        x_short = x0 + round((x_full - x0) * 0.6)
        for frac, x_end in ((0.30, x_full), (0.46, x_full), (0.62, x_short)):
            y = px(frac)
            half = thick // 2
            draw.rounded_rectangle((x0, y - half, x_end, y + half), radius=half, fill=TEXT)

    # ตัดมุมขวาล่างออกให้โปร่งใส โดยใช้ silhouette เป็น alpha
    mask = Image.new("L", (S, S), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle(outer, radius=radius, fill=255)
    mask_draw.polygon(
        [
            (ax - overshoot, ay + overshoot),
            (ax, ay),
            (bx, by),
            (bx + overshoot, by - overshoot),
            (bx + overshoot, ay + overshoot),
        ],
        fill=0,
    )
    img.putalpha(mask)

    return img.resize((size, size), Image.Resampling.LANCZOS)


def write_ico(images: list[Image.Image], path: Path) -> None:
    """เขียน ICO แบบ PNG-compressed ทุกขนาด (รองรับ Windows Vista ขึ้นไป)

    Pillow บันทึก ICO จากภาพเดียวแล้วย่อเอง จึงเขียน header เองเพื่อให้แต่ละขนาดเป็นภาพที่วาดแยกกัน
    """
    blobs = []
    for im in images:
        buf = BytesIO()
        im.save(buf, format="PNG", optimize=True)
        blobs.append(buf.getvalue())

    header = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    directory = b""
    for im, blob in zip(images, blobs):
        w, h = im.size
        directory += struct.pack(
            "<BBBBHHII",
            0 if w >= 256 else w,  # 0 หมายถึง 256 ใน ICO
            0 if h >= 256 else h,
            0,
            0,
            1,
            32,
            len(blob),
            offset,
        )
        offset += len(blob)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(header + directory + b"".join(blobs))


def write_preview(images: list[Image.Image], path: Path) -> None:
    """ภาพตัวอย่างทุกขนาดวางเรียงกัน ชิดฐานล่าง มีป้ายกำกับขนาด"""
    pad, gap, label_gap = 24, 28, 10
    font = ImageFont.load_default()
    max_h = max(im.height for im in images)
    width = pad * 2 + sum(im.width for im in images) + gap * (len(images) - 1)
    height = pad * 2 + max_h + label_gap + 16

    canvas = Image.new("RGBA", (width, height), PREVIEW_BG)
    draw = ImageDraw.Draw(canvas)
    x = pad
    for im in images:
        canvas.alpha_composite(im, (x, pad + max_h - im.height))
        label = f"{im.width}px"
        label_w = draw.textlength(label, font=font)
        draw.text((x + (im.width - label_w) / 2, pad + max_h + label_gap), label, fill=(60, 60, 60, 255), font=font)
        x += im.width + gap

    path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate QuickNote icon")
    parser.add_argument("--preview", type=Path, help="ไฟล์ PNG สำหรับดูตัวอย่างทุกขนาด (ไม่ระบุก็ได้)")
    args = parser.parse_args()

    images = [render(s) for s in SIZES]
    write_ico(images, ICO_PATH)

    # ตรวจซ้ำว่าไฟล์ที่เขียนอ่านได้และมีครบทุกขนาด
    with Image.open(ICO_PATH) as check:
        found = sorted(check.info.get("sizes", []))
    print(f"wrote {ICO_PATH} sizes={[w for w, _ in found]}")

    if args.preview:
        write_preview(images, args.preview)
        print(f"wrote preview {args.preview}")


if __name__ == "__main__":
    main()
