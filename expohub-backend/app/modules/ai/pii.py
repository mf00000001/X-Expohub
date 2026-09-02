"""
AI 原生层 —— PII 脱敏工具（P5）

在任何文本发往 LLM 之前脱敏；不落库原文，从机制上避免隐私泄露。
"""
from __future__ import annotations

import re

# 中国大陆手机号：1[3-9]xxxxxxxxx
_RE_PHONE = re.compile(r"(?<!\d)(1[3-9]\d{9})(?!\d)")
# 邮箱
_RE_EMAIL = re.compile(r"([\w.+-]+)@([\w-]+\.)+[\w-]+")
# 身份证 18 位（含 X）
_RE_IDCARD = re.compile(r"(?<!\d)(\d{6})\d{8}(\d{3}[\dXx])(?!\d)")
# 银行卡/长数字串（≥13 位连续数字）
_RE_LONGNUM = re.compile(r"(?<!\d)(\d{13,19})(?!\d)")


def redact_pii(text: str) -> str:
    """对手机号/邮箱/身份证/长数字串做脱敏（保留前后缀与后4位样式）"""
    out = _RE_PHONE.sub(lambda m: m.group(1)[:3] + "****" + m.group(1)[-4:], text)
    out = _RE_IDCARD.sub(lambda m: m.group(1) + "********" + m.group(2), out)
    out = _RE_EMAIL.sub(lambda m: m.group(1)[:2] + "***@***", out)
    out = _RE_LONGNUM.sub(lambda m: m.group(1)[:4] + "****" + m.group(1)[-4:], out)
    return out
