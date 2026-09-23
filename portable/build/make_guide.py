"""生成《ExpoHub 试用版 · 使用说明》Word 文档。

读者是完全不懂技术的人，所以：只写"点哪里、看到什么"，
不出现任何命令行、路径、术语。

用法：
    python make_guide.py --out-dir <便携包目录> [--tools-dir <python-docx 所在目录>]

python-docx 装在构建工具目录（pytools）里，不进项目的 .venv，避免污染开发环境。
"""
from __future__ import annotations

import argparse
import os
import sys

_ap = argparse.ArgumentParser(description='生成便携试用包的使用说明 .docx')
_ap.add_argument('--out-dir', required=True, help='便携包目录，说明文档输出到这里')
_ap.add_argument('--tools-dir', default=None,
                 help='额外加入 sys.path 的目录（存放 python-docx）。'
                      '默认为工作区的 build\\pytools')
_args = _ap.parse_args()

if _args.tools_dir:
    sys.path.insert(0, _args.tools_dir)
else:
    # 默认：<仓库>/portable/build/make_guide.py -> 往上找到工作区的 build/pytools 不现实，
    # 因此默认落在仓库内的 .pytools（构建脚本会显式传 --tools-dir）
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '.pytools'))

try:
    from docx import Document
except ImportError:
    sys.exit('缺少 python-docx。先安装：\n'
             '  pip install python-docx --target <tools-dir>\n'
             '再带上 --tools-dir <tools-dir> 运行本脚本。')

from docx.enum.table import WD_TABLE_ALIGNMENT                # noqa: E402
from docx.enum.text import WD_ALIGN_PARAGRAPH                 # noqa: E402
from docx.oxml.ns import qn                                   # noqa: E402
from docx.shared import Cm, Pt, RGBColor                      # noqa: E402

OUT = os.path.join(_args.out_dir, '使用说明.docx')

FONT = '微软雅黑'
ACCENT = RGBColor(0x2B, 0x5C, 0xE6)
MUTED = RGBColor(0x60, 0x6B, 0x7B)

doc = Document()

# ---- 全局字体（中文必须单独设 eastAsia，否则 Word 回退成宋体）----
normal = doc.styles['Normal']
normal.font.name = FONT
normal.font.size = Pt(10.5)
normal.element.rPr.rFonts.set(qn('w:eastAsia'), FONT)

for sec in doc.sections:
    sec.top_margin = Cm(2.2)
    sec.bottom_margin = Cm(2.2)
    sec.left_margin = Cm(2.4)
    sec.right_margin = Cm(2.4)


def style_heading(level, size, color, space_before, space_after):
    st = doc.styles[f'Heading {level}']
    st.font.name = FONT
    st.font.size = Pt(size)
    st.font.color.rgb = color
    st.font.bold = True
    st.element.rPr.rFonts.set(qn('w:eastAsia'), FONT)
    st.paragraph_format.space_before = Pt(space_before)
    st.paragraph_format.space_after = Pt(space_after)


style_heading(1, 15, ACCENT, 18, 8)
style_heading(2, 12, RGBColor(0x1F, 0x2A, 0x37), 12, 6)


def para(text='', *, bold=False, size=10.5, color=None, indent=0, after=6, align=None):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(after)
    if indent:
        p.paragraph_format.left_indent = Cm(indent)
    if align:
        p.alignment = align
    if text:
        r = p.add_run(text)
        r.font.name = FONT
        r.element.rPr.rFonts.set(qn('w:eastAsia'), FONT)
        r.font.size = Pt(size)
        r.bold = bold
        if color:
            r.font.color.rgb = color
    return p


def bullet(text, level=0):
    p = doc.add_paragraph(style='List Bullet')
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.left_indent = Cm(0.75 + level * 0.6)
    r = p.add_run(text)
    r.font.name = FONT
    r.element.rPr.rFonts.set(qn('w:eastAsia'), FONT)
    r.font.size = Pt(10.5)
    return p


def rich(parts, indent=0, after=6):
    """parts: [(文本, 是否加粗, 颜色 or None), ...]"""
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(after)
    if indent:
        p.paragraph_format.left_indent = Cm(indent)
    for text, bold, color in parts:
        r = p.add_run(text)
        r.font.name = FONT
        r.element.rPr.rFonts.set(qn('w:eastAsia'), FONT)
        r.font.size = Pt(10.5)
        r.bold = bold
        if color:
            r.font.color.rgb = color
    return p


def make_table(headers, rows, widths=None):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = 'Light Grid Accent 1'
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, h in enumerate(headers):
        cell = t.rows[0].cells[i]
        cell.text = ''
        r = cell.paragraphs[0].add_run(h)
        r.font.name = FONT
        r.element.rPr.rFonts.set(qn('w:eastAsia'), FONT)
        r.font.size = Pt(10)
        r.bold = True
    for row in rows:
        cells = t.add_row().cells
        for i, val in enumerate(row):
            cells[i].text = ''
            r = cells[i].paragraphs[0].add_run(str(val))
            r.font.name = FONT
            r.element.rPr.rFonts.set(qn('w:eastAsia'), FONT)
            r.font.size = Pt(10)
    if widths:
        for row in t.rows:
            for i, w in enumerate(widths):
                row.cells[i].width = Cm(w)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return t


# ================================================================ 封面标题
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.paragraph_format.space_after = Pt(2)
r = p.add_run('ExpoHub 展会撮合平台')
r.font.name = FONT
r.element.rPr.rFonts.set(qn('w:eastAsia'), FONT)
r.font.size = Pt(22)
r.bold = True
r.font.color.rgb = ACCENT

p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.paragraph_format.space_after = Pt(20)
r = p.add_run('试 用 版 · 使 用 说 明')
r.font.name = FONT
r.element.rPr.rFonts.set(qn('w:eastAsia'), FONT)
r.font.size = Pt(12)
r.font.color.rgb = MUTED

# ================================================================ 一
doc.add_heading('一、打开方式', level=1)
para('三步，不需要安装任何软件，也不需要联网。')

rich([('第 1 步　', True, ACCENT),
      ('把「ExpoHub-试用版」整个文件夹解压到任意位置（建议放桌面）。', False, None)])
rich([('第 2 步　', True, ACCENT),
      ('双击文件夹里的 ', False, None),
      ('「双击启动.bat」', True, None),
      ('。', False, None)])
rich([('第 3 步　', True, ACCENT),
      ('稍等几秒，会自动弹出一个窗口——那就是平台，可以直接开始使用。', False, None)])

para()
para('请注意：', bold=True, after=4)
bullet('第一次启动稍慢（几秒到十几秒），之后再启动只要两三秒。')
bullet('整个文件夹要一起解压，不要只解压其中一部分文件。')
bullet('如果 Windows 弹出安全提示，选择「允许」即可——本程序不联网，也不修改系统。')
bullet('启动过程中弹出的黑色小窗口可以随时关掉，不影响使用。')

# ================================================================ 二
doc.add_heading('二、演示账号', level=1)
para('平台内有五种角色，用下面的账号可以分别体验。密码区分大小写。')

make_table(
    ['角色', '账号', '密码', '能看到什么'],
    [
        ['平台管理员', 'admin', 'admin123', '全部数据、用户管理、平台运营'],
        ['主办方', 'organizer_canton', 'org123', '展会管理、展位、报名、数据统计'],
        ['展商', 'exhibitor_huawei', 'exh123', '微展位、展品、智能匹配'],
        ['买家', 'buyer_li', 'buyer123', '发布采购、找展商'],
        ['观众', 'visitor_chen', 'visitor123', '逛展会、报名参展'],
    ],
    widths=[2.6, 4.0, 2.4, 5.4],
)

rich([('提示：', True, None),
      ('也支持自己注册新账号，随便填即可，演示数据可以随意修改，不会影响到任何人。', False, None)])

# ================================================================ 三
doc.add_heading('三、建议的体验顺序', level=1)
para('如果想快速了解平台能力，可以按这个顺序看：')

rich([('1. 先看首页　', True, None),
      ('用任意账号登录，首页会推荐展会、展商和产品。', False, None)], indent=0.4)
rich([('2. 智能匹配　', True, None),
      ('换 ', False, None), ('exhibitor_huawei', True, None),
      (' 登录，进「展商工作台」，可以看到系统自动推荐给该展商的采购需求，并附有匹配理由。',
       False, None)], indent=0.4)
rich([('3. 发布采购　', True, None),
      ('换 ', False, None), ('buyer_li', True, None),
      (' 登录，发布一条采购需求，再到展商账号去看匹配结果。', False, None)], indent=0.4)
rich([('4. 主办方视角　', True, None),
      ('换 ', False, None), ('organizer_canton', True, None),
      (' 登录，可以管理展会、展位、报名，并查看数据统计。', False, None)], indent=0.4)
rich([('5. 后台管理　', True, None),
      ('最后用 ', False, None), ('admin', True, None),
      (' 登录，可以看到整体运营数据。', False, None)], indent=0.4)

# ================================================================ 四
doc.add_heading('四、关闭程序', level=1)
rich([('关掉应用窗口', True, None),
      ('并不会', False, None),
      ('停止服务', True, None),
      ('——它仍在后台运行。要彻底关闭，请双击文件夹里的 ', False, None),
      ('「停止运行.bat」', True, None),
      ('。', False, None)])
para('服务在后台运行不会有任何害处；如果下次还要用，直接再双击「双击启动.bat」即可，不会重复启动。',
     color=MUTED, size=10)

# ================================================================ 五
doc.add_heading('五、遇到问题怎么办', level=1)
make_table(
    ['遇到的情况', '怎么处理'],
    [
        ['窗口没有自动弹出来',
         '手动打开浏览器（Edge / Chrome 都行），在地址栏输入：\n'
         'http://127.0.0.1:8002\n'
         '如果打不开，把末尾的 8002 依次改成 8003、8004 再试。'],
        ['双击「双击启动.bat」后没有任何反应',
         '这是 Windows 给「从网上下载的文件」加的安全标记。\n'
         '右键点「双击启动.bat」→ 属性 → 在窗口下方勾选「解除锁定」→ 确定，然后再双击一次。'],
        ['提示「启动失败」',
         '把程序目录里的 logs 文件夹整个打包发回给开发者，里面记录了失败原因。'],
        ['页面显示不正常 / 打不开',
         '先双击「停止运行.bat」，再重新双击「双击启动.bat」。'],
        ['杀毒软件提示风险',
         '本程序不联网、不修改系统设置，属于误报，选择「允许 / 信任」即可。'],
    ],
    widths=[4.6, 9.8],
)

# ================================================================ 六
doc.add_heading('六、关于演示数据', level=1)
bullet('所有展会、企业、产品、采购需求均为虚构的演示数据。')
bullet('您可以随意注册、发布、修改，用来体验完整流程。')
bullet('所有改动只保存在本机，不会影响线上服务，也不会影响其他人。')

para()
para('祝使用愉快。', bold=True, color=ACCENT)

doc.save(OUT)
print(f'已生成: {OUT}')
print(f'段落数: {len(doc.paragraphs)}  表格数: {len(doc.tables)}')
