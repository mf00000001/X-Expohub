#!/usr/bin/env python3
"""
生成 ExpoHub 桌面图标 (assets/expohub.ico)

设计：靛蓝→紫罗兰斜向渐变圆角方块 + 白色交叠双环。
双环取"撮合/匹配"的意象——平台的核心语义；且在 16x16 下仍可辨认。

用法：python make_icon.py
依赖：Pillow（本机 .venv 内已有 12.3.0）
"""
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent

S = 1024                      # 超采样画布尺寸
C1 = (79, 70, 229)            # #4F46E5 indigo-600
C2 = (139, 92, 246)           # #8B5CF6 violet-500


def lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def make_gradient(size: int) -> Image.Image:
    """斜向线性渐变。用小图插值放大，避免百万级 Python 像素循环。"""
    small = 128
    g = Image.new("RGB", (small, small))
    px = g.load()
    for y in range(small):
        for x in range(small):
            px[x, y] = lerp(C1, C2, (x + y) / (2 * (small - 1)))
    return g.resize((size, size), Image.BICUBIC)


def main() -> None:
    # --- 圆角方块遮罩 ---
    radius_mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(radius_mask).rounded_rectangle(
        [0, 0, S - 1, S - 1], radius=int(S * 0.22), fill=255
    )

    base = make_gradient(S).convert("RGBA")
    base.putalpha(radius_mask)

    # --- 白色交叠双环 ---
    mark = Image.new("L", (S, S), 0)
    d = ImageDraw.Draw(mark)
    r = int(S * 0.200)          # 环半径
    w = int(S * 0.055)          # 环粗细
    cy = S // 2
    offset = int(S * 0.086)     # 两环中心相对画布中心的偏移

    for cx in (S // 2 - offset, S // 2 + offset):
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=255, width=w)

    white = Image.new("RGBA", (S, S), (255, 255, 255, 255))
    icon = Image.composite(white, base, mark)

    # --- 输出多尺寸 ico + 预览 png ---
    preview = icon.resize((256, 256), Image.LANCZOS)
    preview.save(HERE / "expohub-preview.png")

    preview.save(
        HERE / "expohub.ico",
        format="ICO",
        sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)],
    )
    print(f"OK  {HERE / 'expohub.ico'}")
    print(f"OK  {HERE / 'expohub-preview.png'}")


if __name__ == "__main__":
    main()
