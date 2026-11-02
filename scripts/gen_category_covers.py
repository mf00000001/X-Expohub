#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""gen_category_covers.py — 生成「按品类的展品占位图」到前端 public/categories/

为什么需要
==========
名录 67,357 件展品里只有 751 件有真实图；剩下 99% 只能靠兜底。
此前的兜底是「深蓝渐变 + 品名首字水印」——不破图，但整页灰蓝一片、识别度低。
本脚本按品类生成 16 张 + 1 张通用兜底的分类缩略图：品牌深蓝渐变底 + 各自的
代表色 + 几何母题（齿轮 / 电路 / 车轮 / 培养孔板 / 六方晶格 …），
列表里一眼能分出「这一类大概是什么东西」，又不会像真实照片那样误导。

风格约定
========
- 800×600（4:3，与前端卡片图位一致），PNG（optimize），无任何文字：
  前端会用真实品名/分类做文字层，图上再带字会重复且中文字体在部分环境缺失。
- 底：品牌深蓝竖渐变（#071528 → #123A6B 一族的微妙变化），叠加极淡白点阵/斜线；
- 主体：该类目代表色的几何母题，偏右构图，左侧留出文字空间；
- 兜底：_default.png 用中性蓝灰，母题是同心圆环。

产出
====
expo-hub-frontend/public/categories/
    machine-tool.png  mold-die.png       general-machinery.png  instruments.png
    electronics.png   auto-parts.png     home-appliance.png     photonics.png
    semiconductor.png robotics.png       energy.png             aerospace.png
    medical-device.png diagnostics.png   rehab.png              materials.png
    _default.png
可选：--sheet 额外输出 docs/evidence/categories-preview.png 拼版预览（人工审阅用）。

用法
====
    python scripts/gen_category_covers.py            # 生成全部（默认不写库）
    python scripts/gen_category_covers.py --sheet    # 额外输出预览拼版
    python scripts/gen_category_covers.py --out DIR  # 换输出目录
"""
from __future__ import annotations

import argparse
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

REPO = Path(__file__).resolve().parents[1]
DEFAULT_OUT = REPO / "expo-hub-frontend" / "public" / "categories"
EVIDENCE = REPO / "docs" / "evidence"

W, H = 800, 600

# slug -> (中文品类说明, 底色顶/底, 代表色 accent, 母题)
# 中文只出现在本注释与预览清单里，绝不画进图里（避免字体缺失变豆腐块）。
CATEGORIES = {
    "machine-tool":      ("机床工具 / 数控机床",   (0x06, 0x14, 0x2C), (0x12, 0x38, 0x6E), (0x60, 0xA5, 0xFA), "gear"),
    "mold-die":          ("模具制造",              (0x07, 0x17, 0x30), (0x14, 0x3A, 0x6A), (0x3B, 0x82, 0xF6), "layers"),
    "general-machinery": ("通用机械 / 重型机械",   (0x05, 0x14, 0x2A), (0x10, 0x36, 0x60), (0x22, 0xD3, 0xEE), "pipes"),
    "instruments":       ("仪表仪器 / 测量",       (0x08, 0x18, 0x32), (0x13, 0x3C, 0x70), (0x38, 0xBD, 0xF8), "gauge"),
    "electronics":       ("3C 电子 / 消费电子",    (0x0A, 0x12, 0x2E), (0x1B, 0x2F, 0x74), (0xA7, 0x8B, 0xFA), "circuit"),
    "auto-parts":        ("汽车 / 汽车零部件",     (0x0B, 0x14, 0x28), (0x1A, 0x33, 0x5C), (0xF9, 0x73, 0x16), "wheel"),
    "home-appliance":    ("家用电器",              (0x0C, 0x15, 0x2C), (0x1C, 0x34, 0x5E), (0xF4, 0x3F, 0x5E), "appliance"),
    "photonics":         ("光电 / 光学 / 激光",    (0x04, 0x14, 0x2B), (0x0C, 0x30, 0x5E), (0x2D, 0xD4, 0xBF), "lens"),
    "semiconductor":     ("半导体 / 集成电路",     (0x08, 0x10, 0x2B), (0x1A, 0x2A, 0x6A), (0x8B, 0x5C, 0xF6), "wafer"),
    "robotics":          ("人工智能 / 机器人",     (0x07, 0x11, 0x2F), (0x18, 0x2C, 0x74), (0x63, 0x66, 0xF1), "nodes"),
    "energy":            ("新能源 / 电力能源",     (0x05, 0x18, 0x28), (0x0C, 0x3E, 0x55), (0x34, 0xD3, 0x99), "energy"),
    "aerospace":         ("航空航天 / 低空经济",   (0x08, 0x13, 0x2E), (0x1C, 0x30, 0x62), (0x93, 0xC5, 0xFD), "orbit"),
    "medical-device":    ("医疗器械 / 医疗设备",   (0x04, 0x18, 0x30), (0x0E, 0x3D, 0x66), (0x22, 0xD3, 0xEE), "cross"),
    "diagnostics":       ("诊断试剂 / 体外诊断",   (0x05, 0x18, 0x2B), (0x10, 0x3B, 0x5E), (0x2D, 0xD4, 0xBF), "wells"),
    "rehab":             ("康复理疗 / 康养",       (0x0B, 0x14, 0x2C), (0x22, 0x30, 0x5E), (0xF4, 0x72, 0xB6), "pulse"),
    "materials":         ("新材料 / 高分子",       (0x09, 0x15, 0x28), (0x1E, 0x33, 0x4A), (0xFB, 0xBF, 0x24), "hex"),
    "_default":          ("通用兜底（无品类映射）", (0x07, 0x12, 0x26), (0x17, 0x2E, 0x52), (0x94, 0xA3, 0xB8), "rings"),
}

ORDER = list(CATEGORIES.keys())


# ---------------------------------------------------------------------------
# 底图工具
# ---------------------------------------------------------------------------
def vertical_gradient(top, bottom) -> Image.Image:
    """1px 竖条渐变再拉伸：比逐像素快几个数量级。"""
    strip = Image.new("RGB", (1, H))
    d = ImageDraw.Draw(strip)
    for y in range(H):
        t = y / (H - 1)
        d.point((0, y), fill=tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    return strip.resize((W, H))


def add_glow(img: Image.Image, cx: float, cy: float, r: float, color, alpha: int) -> None:
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=tuple(color) + (alpha,))
    layer = layer.filter(ImageFilter.GaussianBlur(radius=r * 0.55))
    img.alpha_composite(layer)


def add_diagonal_lines(img: Image.Image, alpha: int = 9, spacing: int = 34) -> None:
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for x in range(-H, W + H, spacing):
        d.line([(x, H), (x + H, 0)], fill=(255, 255, 255, alpha), width=1)
    img.alpha_composite(layer)


def add_dot_grid(img: Image.Image, x0: int, y0: int, cols: int, rows: int, step: int,
                 radius: int = 2, alpha: int = 26) -> None:
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for i in range(cols):
        for j in range(rows):
            cx, cy = x0 + i * step, y0 + j * step
            d.ellipse([cx - radius, cy - radius, cx + radius, cy + radius],
                      fill=(255, 255, 255, alpha))
    img.alpha_composite(layer)


def add_vignette(img: Image.Image) -> None:
    """底部压暗 + 四角轻压，缩到卡片尺寸时主体更聚焦。"""
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for y in range(H):
        t = max(0.0, (y - H * 0.55) / (H * 0.45))
        a = int(86 * t * t)
        if a:
            d.line([(0, y), (W, y)], fill=(0, 0, 0, a))
    img.alpha_composite(layer)


# ---------------------------------------------------------------------------
# 几何母题（全部只用 accent 调透明度绘制，无文字）
# ---------------------------------------------------------------------------
def _a(accent, alpha: int):
    return tuple(accent) + (alpha,)


def motif_gear(img, accent, rng):
    """机床：齿轮 + 中心轴孔。"""
    d = ImageDraw.Draw(img)
    cx, cy, r = 560, 300, 150
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=_a(accent, 190), width=30)
    for k in range(12):
        ang = k * math.pi / 6
        ca, sa = math.cos(ang), math.sin(ang)
        d.line([(cx + ca * (r + 8), cy + sa * (r + 8)),
                (cx + ca * (r + 40), cy + sa * (r + 40))],
               fill=_a(accent, 190), width=22)
    d.ellipse([cx - 74, cy - 74, cx + 74, cy + 74], outline=_a(accent, 110), width=6)
    d.ellipse([cx - 26, cy - 26, cx + 26, cy + 26], fill=_a(accent, 230))


def motif_layers(img, accent, rng):
    """模具：三层错位的「型腔板」+ 定位孔。"""
    d = ImageDraw.Draw(img)
    for i in range(4):
        ox, oy = 400 + i * 34, 150 + i * 52
        d.rounded_rectangle([ox, oy, ox + 260, oy + 150], radius=18,
                            outline=_a(accent, 60 + i * 46), width=6)
    for i in range(3):
        cx = 452 + i * 34
        d.ellipse([cx - 9, 208 + i * 52 - 9, cx + 9, 208 + i * 52 + 9], fill=_a(accent, 170))
        d.ellipse([cx + 200 - 9, 208 + i * 52 - 9, cx + 200 + 9, 208 + i * 52 + 9],
                  fill=_a(accent, 120))


def motif_pipes(img, accent, rng):
    """通用机械：管路网络 + 法兰节点。"""
    d = ImageDraw.Draw(img)
    path = [(360, 470), (360, 340), (470, 340), (470, 200), (640, 200), (640, 320), (720, 320)]
    d.line(path, fill=_a(accent, 170), width=26, joint="curve")
    for p in [(360, 470), (470, 340), (640, 200), (720, 320)]:
        d.ellipse([p[0] - 26, p[1] - 26, p[0] + 26, p[1] + 26], fill=_a(accent, 235))
        d.ellipse([p[0] - 11, p[1] - 11, p[0] + 11, p[1] + 11], fill=(255, 255, 255, 70))
    for i in range(5):
        y = 190 + i * 34
        d.line([(500, y), (600, y)], fill=_a(accent, 55), width=4)


def motif_gauge(img, accent, rng):
    """仪表：表盘刻度弧 + 指针。"""
    d = ImageDraw.Draw(img)
    cx, cy, r = 560, 330, 160
    d.arc([cx - r, cy - r, cx + r, cy + r], 150, 30, fill=_a(accent, 190), width=14)
    for i in range(13):
        ang = math.radians(150 + i * 20)
        ca, sa = math.cos(ang), math.sin(ang)
        r1 = r - 26 if i % 3 else r - 40
        d.line([(cx + ca * r1, cy + sa * r1), (cx + ca * (r - 6), cy + sa * (r - 6))],
               fill=_a(accent, 200 if i % 3 else 240), width=5 if i % 3 else 8)
    ang = math.radians(-38)
    d.line([(cx, cy), (cx + math.cos(ang) * (r - 44), cy + math.sin(ang) * (r - 44))],
           fill=_a(accent, 245), width=8)
    d.ellipse([cx - 16, cy - 16, cx + 16, cy + 16], fill=_a(accent, 245))
    d.line([(cx - 110, cy + 96), (cx + 110, cy + 96)], fill=_a(accent, 45), width=5)


def motif_circuit(img, accent, rng):
    """电子：PCB 走线 + 焊盘 + 芯片。"""
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([470, 190, 620, 300], radius=10, outline=_a(accent, 210), width=7)
    for i in range(4):
        d.line([(470, 214 + i * 24), (430, 214 + i * 24)], fill=_a(accent, 150), width=6)
        d.line([(620, 214 + i * 24), (660, 214 + i * 24)], fill=_a(accent, 150), width=6)
    traces = [
        [(660, 214), (720, 214), (720, 150), (760, 150)],
        [(660, 262), (700, 262), (700, 380), (560, 380), (560, 440)],
        [(430, 238), (380, 238), (380, 330), (300, 330)],
        [(430, 286), (360, 286), (360, 470), (520, 470)],
    ]
    for t in traces:
        d.line(t, fill=_a(accent, 130), width=6, joint="curve")
    for p in [(760, 150), (560, 440), (300, 330), (520, 470)]:
        d.ellipse([p[0] - 12, p[1] - 12, p[0] + 12, p[1] + 12], outline=_a(accent, 240), width=6)
    for i in range(4):
        for j in range(3):
            d.rounded_rectangle([492 + i * 30, 212 + j * 28, 510 + i * 30, 230 + j * 28],
                                radius=3, fill=_a(accent, 70))


def motif_wheel(img, accent, rng):
    """汽车：轮毂 + 辐条 + 胎面。"""
    d = ImageDraw.Draw(img)
    cx, cy, r = 560, 310, 170
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=_a(accent, 120), width=26)
    for k in range(5):
        ang = math.radians(-90 + k * 72)
        ca, sa = math.cos(ang), math.sin(ang)
        d.line([(cx + ca * 40, cy + sa * 40), (cx + ca * (r - 26), cy + sa * (r - 26))],
               fill=_a(accent, 200), width=18)
    d.ellipse([cx - 62, cy - 62, cx + 62, cy + 62], outline=_a(accent, 160), width=8)
    d.ellipse([cx - 24, cy - 24, cx + 24, cy + 24], fill=_a(accent, 240))
    d.line([(300, 520), (700, 520)], fill=_a(accent, 40), width=6)


def motif_appliance(img, accent, rng):
    """家电：圆角机身 + 旋钮 + 散热格栅。"""
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([400, 130, 660, 470], radius=26, outline=_a(accent, 200), width=8)
    d.ellipse([500, 176, 576, 252], outline=_a(accent, 220), width=8)
    d.line([(538, 178), (538, 214)], fill=_a(accent, 240), width=6)
    for i in range(5):
        d.line([(432, 300 + i * 26), (620, 300 + i * 26)], fill=_a(accent, 95), width=6)
    d.rounded_rectangle([470, 430, 590, 448], radius=9, fill=_a(accent, 70))


def motif_lens(img, accent, rng):
    """光电：透镜 + 向左扩散的扇形光束 + 焦点弧。"""
    d = ImageDraw.Draw(img)
    cx, cy = 610, 300
    # 扇形光束：从透镜向左侧张开，越远越淡
    for i in range(11):
        ang = math.radians(152 + i * 5.6)
        ca, sa = math.cos(ang), math.sin(ang)
        d.line([(cx + ca * 92, cy + sa * 92), (cx + ca * 250, cy + sa * 250)],
               fill=_a(accent, 46 + (i % 3) * 26), width=4)
    # 焦点弧（以透镜为圆心的同心弧）
    for i, rr in enumerate((150, 196, 242)):
        d.arc([cx - rr, cy - rr, cx + rr, cy + rr], 156, 204,
              fill=_a(accent, 92 - i * 22), width=5)
    # 透镜本体
    d.ellipse([cx - 96, cy - 96, cx + 96, cy + 96], outline=_a(accent, 190), width=10)
    d.ellipse([cx - 56, cy - 56, cx + 56, cy + 56], outline=_a(accent, 225), width=7)
    d.ellipse([cx - 16, cy - 16, cx + 16, cy + 16], fill=_a(accent, 240))


def motif_wafer(img, accent, rng):
    """半导体：晶圆 + 芯片阵列 + 缺口。"""
    d = ImageDraw.Draw(img)
    cx, cy, r = 560, 300, 175
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=_a(accent, 190), width=8)
    step = 30
    for gx in range(cx - 150, cx + 150, step):
        for gy in range(cy - 150, cy + 150, step):
            if (gx + step / 2 - cx) ** 2 + (gy + step / 2 - cy) ** 2 < (r - 16) ** 2:
                d.rounded_rectangle([gx + 4, gy + 4, gx + step - 6, gy + step - 6],
                                    radius=4, outline=_a(accent, 92), width=3)
    d.ellipse([cx - 26, cy - 26, cx + 26, cy + 26], fill=_a(accent, 90))
    d.arc([cx - r, cy - r, cx + r, cy + r], 300, 330, fill=(7, 16, 44, 255), width=26)


def motif_nodes(img, accent, rng):
    """AI / 机器人：节点网络。"""
    rng = random.Random(11)
    d = ImageDraw.Draw(img)
    pts = [(rng.uniform(340, 740), rng.uniform(120, 490)) for _ in range(12)]
    for i, a in enumerate(pts):
        near = sorted(((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2, j) for j, b in enumerate(pts) if j != i)
        for dist, j in near[:2]:
            if dist < 200 ** 2 and j > i:
                d.line([a, pts[j]], fill=_a(accent, 62), width=2)
    for i, p in enumerate(pts):
        rr = 20 if i % 3 else 28
        d.ellipse([p[0] - rr, p[1] - rr, p[0] + rr, p[1] + rr], fill=_a(accent, 200 if i % 3 else 235))


def motif_energy(img, accent, rng):
    """新能源：太阳 + 光线 + 波浪。"""
    d = ImageDraw.Draw(img)
    cx, cy = 590, 300
    d.ellipse([cx - 84, cy - 84, cx + 84, cy + 84], fill=_a(accent, 225))
    for i in range(16):
        ang = math.radians(i * 22.5)
        ca, sa = math.cos(ang), math.sin(ang)
        d.line([(cx + ca * 108, cy + sa * 108), (cx + ca * 178, cy + sa * 178)],
               fill=_a(accent, 150), width=8)
    for i in range(4):
        r = 150 + i * 62
        d.arc([cx - r, cy - r, cx + r, cy + r], 196, 344, fill=_a(accent, 70 - i * 12), width=7)


def motif_orbit(img, accent, rng):
    """航空航天：轨道椭圆 + 飞行器 + 尾迹点。"""
    d = ImageDraw.Draw(img)
    cx, cy = 560, 300
    for i, (rw, rh, ang) in enumerate(((250, 110, 0), (200, 88, 34), (300, 132, -22))):
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        ld.ellipse([cx - rw, cy - rh, cx + rw, cy + rh], outline=_a(accent, 70 + i * 30), width=5)
        layer = layer.rotate(ang, center=(cx, cy), resample=Image.BICUBIC)
        img.alpha_composite(layer)
    d.ellipse([cx - 34, cy - 34, cx + 34, cy + 34], fill=_a(accent, 235))
    for k in range(6):
        d.ellipse([cx + 120 + k * 26 - 5, cy - 88 - k * 12 - 5, cx + 120 + k * 26 + 5,
                   cy - 88 - k * 12 + 5], fill=_a(accent, 150 - k * 20))


def motif_cross(img, accent, rng):
    """医疗器械：医疗十字 + 心电线。"""
    d = ImageDraw.Draw(img)
    cx, cy, L, w = 560, 300, 120, 46
    d.rectangle([cx - w / 2, cy - L, cx + w / 2, cy + L], fill=_a(accent, 220))
    d.rectangle([cx - L, cy - w / 2, cx + L, cy + w / 2], fill=_a(accent, 220))
    for i, r in enumerate((200, 254)):
        d.arc([cx - r, cy - r, cx + r, cy + r], 200 + i * 20, 340 - i * 20,
              fill=_a(accent, 80), width=5)
    x, y = 320, 470
    pts = [(x, y)]
    for dx, dy in ((44, 0), (24, -42), (26, 84), (30, -120), (26, 78), (44, 0)):
        x += dx
        y += dy
        pts.append((x, y))
    d.line(pts, fill=_a(accent, 170), width=6, joint="curve")


def motif_wells(img, accent, rng):
    """体外诊断：96 孔板 + 试剂滴。"""
    d = ImageDraw.Draw(img)
    x0, y0, step, r = 380, 170, 64, 22
    for i in range(6):
        for j in range(5):
            cx, cy = x0 + i * step, y0 + j * step
            filled = (i * 5 + j) % 7 == 0
            if filled:
                d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=_a(accent, 200))
            else:
                d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=_a(accent, 120), width=4)
    d.polygon([(700, 170), (738, 250), (700, 286), (662, 250)], fill=_a(accent, 170))


def motif_pulse(img, accent, rng):
    """康复理疗：波形 + 同心动环。"""
    d = ImageDraw.Draw(img)
    for i, rr in enumerate((220, 175, 130)):
        d.arc([700 - rr, 300 - rr, 700 + rr, 300 + rr], 150, 210, fill=_a(accent, 80 - i * 18), width=6)
    x, y = 330, 320
    pts = [(x, y)]
    for dx, dy in ((46, 0), (26, -54), (28, 108), (34, -150), (28, 96), (46, 0)):
        x += dx
        y += dy
        pts.append((x, y))
    d.line(pts, fill=_a(accent, 225), width=9, joint="curve")
    d.ellipse([330 - 10, 320 - 10, 330 + 10, 320 + 10], fill=_a(accent, 245))


def motif_hex(img, accent, rng):
    """新材料：六方晶格。"""
    d = ImageDraw.Draw(img)
    R = 46
    dx = R * math.sqrt(3)
    dy = R * 1.5
    for row in range(-1, 6):
        for col in range(-1, 6):
            cx = 380 + col * dx + (row % 2) * dx / 2
            cy = 140 + row * dy
            if not (300 < cx < 820 and 60 < cy < 560):
                continue
            pts = [(cx + R * math.cos(math.radians(60 * k)), cy + R * math.sin(math.radians(60 * k)))
                   for k in range(6)]
            d.polygon(pts, outline=_a(accent, 90), width=4)
    d.polygon([(520 + 70 * math.cos(math.radians(60 * k)), 300 + 70 * math.sin(math.radians(60 * k)))
               for k in range(6)], fill=_a(accent, 190))


def motif_rings(img, accent, rng):
    """兜底：同心圆环 + 中心点。"""
    d = ImageDraw.Draw(img)
    cx, cy = 560, 300
    for i, r in enumerate((220, 168, 118, 70)):
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=_a(accent, 40 + i * 22), width=5)
    d.ellipse([cx - 22, cy - 22, cx + 22, cy + 22], fill=_a(accent, 210))


MOTIFS = {
    "gear": motif_gear, "layers": motif_layers, "pipes": motif_pipes, "gauge": motif_gauge,
    "circuit": motif_circuit, "wheel": motif_wheel, "appliance": motif_appliance,
    "lens": motif_lens, "wafer": motif_wafer, "nodes": motif_nodes, "energy": motif_energy,
    "orbit": motif_orbit, "cross": motif_cross, "wells": motif_wells, "pulse": motif_pulse,
    "hex": motif_hex, "rings": motif_rings,
}


# ---------------------------------------------------------------------------
# 合成
# ---------------------------------------------------------------------------
def gen_cover(slug: str) -> Path:
    _label, top, bottom, accent, motif = CATEGORIES[slug]
    rng = random.Random(slug)  # 同 slug 每次生成完全一致（可重复构建）
    img = vertical_gradient(top, bottom).convert("RGBA")

    # 氛围：左上白光 + 右下 accent 光晕（位置按 index 微调，17 张不至于完全同构）
    idx = ORDER.index(slug)
    add_glow(img, 150 + (idx % 3) * 30, 90, 300, (255, 255, 255), 12)
    add_glow(img, 600, 520, 380, accent, 40)
    add_glow(img, 700, 130, 220, accent, 26)
    add_diagonal_lines(img, alpha=8, spacing=36)
    add_dot_grid(img, 60, 400, 9, 5, 32, radius=2, alpha=22)
    add_vignette(img)

    MOTIFS[motif](img, accent, rng)

    # 左上角细色条：卡片小尺寸下的品类识别锚点
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([36, 36, 36 + 76, 36 + 8], radius=4, fill=tuple(accent) + (235,))
    d.rounded_rectangle([36, 56, 36 + 34, 56 + 4], radius=2, fill=(255, 255, 255, 60))

    out = DEFAULT_OUT / f"{slug}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(out, format="PNG", optimize=True)
    return out


def make_sheet(paths: list[Path], out: Path) -> Path:
    cols, rows = 4, 5
    tw, th = 320, 240
    pad = 14
    sheet = Image.new("RGB", (cols * tw + pad * (cols + 1), rows * th + pad * (rows + 1)), (18, 22, 32))
    for i, p in enumerate(paths):
        im = Image.open(p).resize((tw, th), Image.LANCZOS)
        x = pad + (i % cols) * (tw + pad)
        y = pad + (i // cols) * (th + pad)
        sheet.paste(im, (x, y))
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out, format="PNG", optimize=True)
    return out


def main() -> int:
    global DEFAULT_OUT
    ap = argparse.ArgumentParser(description="生成按品类的展品占位图")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="输出目录")
    ap.add_argument("--sheet", action="store_true", help="额外输出拼版预览到 docs/evidence/")
    args = ap.parse_args()
    DEFAULT_OUT = Path(args.out)

    total = 0
    paths: list[Path] = []
    for slug in ORDER:
        p = gen_cover(slug)
        size = p.stat().st_size
        total += size
        paths.append(p)
        print(f"  {p.relative_to(REPO) if str(p).startswith(str(REPO)) else p}  {size//1024} KB")
    print(f"共 {len(paths)} 张，合计 {total/1024/1024:.2f} MB（800x600 PNG）")
    if args.sheet:
        sheet = make_sheet(paths, EVIDENCE / "categories-preview.png")
        print(f"拼版预览 {sheet.relative_to(REPO)}  {sheet.stat().st_size//1024} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
