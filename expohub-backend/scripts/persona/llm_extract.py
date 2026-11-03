"""
批次 1b：用 LLM 从已落盘的正文里抽字段（补正则抽不出的部分）。

为什么单独一个脚本、而不是塞进 collect_skeleton.py：
  · 抓取和抽取必须解耦。正文一旦落盘，抽取可以反复重跑、换模型、调 prompt，
    而抓取只有一次机会（网站会变、robots 会变、档期会翻页）。
  · LLM 有成本、有速率限制、有鉴权失败。把它挂在采集流程里，
    一旦 401 就会让"今天一个字段都没采到"，而实际上网页早就抓好了。

没有 key 时**必须大声失败**，不能静默降级：
app/modules/ai/llm.py 的 gateway 在缺 key 时会返回 MockLLMProvider 的
"【generic·mock】AI 服务未配置…"，那句提示如果被当成抽取结果写进数据集，
下游会得到 94 条格式合法、内容全错的字段——比空着危险得多。
所以这里直接调 _build_real_provider()，拿不到就 sys.exit(2)。

用法：
    python scripts/persona/llm_extract.py --dry-run        # 检查 key 与待处理量
    python scripts/persona/llm_extract.py                  # 全量（可中断，重跑续采）
    python scripts/persona/llm_extract.py --only cimt,cmef
    python scripts/persona/llm_extract.py --force          # 忽略已有结果重抽
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BATCH_DIR = ROOT / "data" / "batch1"
RAW_DIR = BATCH_DIR / "raw"
RENDERED_DIR = BATCH_DIR / "rendered"
SUB_DIR = BATCH_DIR / "sub"          # 批次 2b 补采的子页（展会概况/上届回顾）
SKELETON = BATCH_DIR / "skeleton.json"
OUT = BATCH_DIR / "llm_extract.json"

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from app.modules.ai.llm import OpenAICompatProvider, _build_real_provider  # noqa: E402
# 复用批次 1 已测过的日期正则与分隔符归一化，而不是在核验环节再写一套
from collect_skeleton import _norm_sep, extract_dates  # noqa: E402

FIELDS = ("title", "start_date", "end_date", "venue", "city",
          "organizer", "edition", "deadline")

SYSTEM = (
    "你是展会信息抽取器。只做抽取，不做推测。"
    "输出必须是单个 JSON 对象，不要 markdown 代码块，不要解释。"
)

PROMPT = """从下面的展会网页正文里抽取字段。规则：

1. 每个字段返回 {"value": ..., "evidence": "..."}
   · evidence 必须是正文里**逐字出现**的一段原文（10~60 字），用来证明这个值不是猜的
   · 正文里找不到依据的字段，value 直接给 null，evidence 给空串
2. 日期一律 ISO 格式 YYYY-MM-DD
   · start_date / end_date 只填**尚未结束**的那一届；如果页面只剩往届日期，
     把 start_date / end_date 填 null，改填 prev_start_date / prev_end_date
   · deadline 是「参展报名/展位申请截止日」，不是开展日
3. edition 是阿拉伯数字届次（"第二十五届" → 25）
4. venue 填展馆全名（如"国家会展中心（上海）"），city 填城市名
5. organizer 填主办单位，多个用顿号连接；承办/协办不算主办
6. 绝不编造。宁可 null。

输出格式：
{"title":{"value":null,"evidence":""},"start_date":{"value":null,"evidence":""},
 "end_date":{"value":null,"evidence":""},"prev_start_date":{"value":null,"evidence":""},
 "prev_end_date":{"value":null,"evidence":""},"venue":{"value":null,"evidence":""},
 "city":{"value":null,"evidence":""},"organizer":{"value":null,"evidence":""},
 "edition":{"value":null,"evidence":""},"deadline":{"value":null,"evidence":""}}

网页正文：
---
%s
---
"""

_LOCK = threading.Lock()


def body_path(rid: str) -> Path | None:
    """优先用无头浏览器渲染过的正文——但**只有它确实更丰富时**才用。

    浏览器渲染不是单调变好的：反爬拦截、脚本没跑完、地区跳转，
    都可能让渲染结果比静态页还少（实测 auto-shanghai 静态 1143 字、渲染后仅 143 字）。
    无条件优先渲染会把本来够用的数据换成空壳。

    渲染结果单独放在 rendered/ 而不是覆盖 raw/：静态页说没说、说了什么，
    是判断"这个站该不该上浏览器"的唯一依据，覆盖掉就回不去了。
    """
    r = RENDERED_DIR / f"{rid}.txt"
    p = RAW_DIR / f"{rid}.txt"
    have_r, have_p = r.exists(), p.exists()
    if have_r and have_p:
        return r if r.stat().st_size > p.stat().st_size else p
    if have_r:
        return r
    return p if have_p else None


def load_body(rid: str) -> str | None:
    """抽取用的正文 = 主正文 + 补充子页（如果有）。

    子页是**增量**，不是替代：首页讲日期和场馆，子页（展会概况/上届回顾）
    才讲规模数字。所以不能像 rendered 那样二选一，必须拼起来。
    同一段文字如果在首页已经出现过就不重复塞，否则同一句话出现两次，
    模型可能把同一个数字当成本届和上届各报一遍。
    """
    p = body_path(rid)
    if p is None:
        return None
    base = p.read_text(encoding="utf-8")
    s = SUB_DIR / f"{rid}.txt"
    if not s.exists():
        return base
    added = []
    for seg in s.read_text(encoding="utf-8").split("\n\n---- "):
        seg = seg.strip()
        if len(seg) < 60:
            continue
        if _flat(seg)[:150] and _flat(seg)[:150] in _flat(base):
            continue
        added.append(seg)
    if not added:
        return base
    return base + "\n\n[补充子页]\n" + "\n\n".join(added)


def all_ids() -> list[str]:
    ids = {p.stem for p in RAW_DIR.glob("*.txt")} | {p.stem for p in RENDERED_DIR.glob("*.txt")}
    return sorted(ids)


def _slices(text: str, kws: tuple[str, ...] | None = None, tail: int = 11000) -> str:
    """正文最长 4 万字，全发既贵又容易让模型分心。

    留头部 6000 字（标题+首屏，展期和场馆基本都在这），
    再挑几段最相关的上下文补到 1 万字。

    kws 必须按**任务**换：日期要从"截止/主办"附近找，规模数据在页面深处的
    "展会规模 / Fair Statistics"里，用日期的关键词去找规模等于没找。
    """
    kws = kws or ("截止", "主办单位", "展馆", "举办时间", "参展")
    head = text[:6000]
    extra = []
    for kw in kws:
        i = text.find(kw, 6000)
        if i > 0:
            extra.append(text[max(0, i - 250): i + 700])
    return (head + "\n...[略]...\n" + "\n...\n".join(extra))[:tail]


def _json_of(s: str) -> dict:
    s = s.strip()
    s = re.sub(r"^```(?:json)?|```$", "", s, flags=re.M).strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    # 模型偶尔会加前言后语，退一步取最外层花括号
    i, j = s.find("{"), s.rfind("}")
    if 0 <= i < j:
        try:
            return json.loads(s[i:j + 1])
        except json.JSONDecodeError:
            return {}
    return {}


def _norm_date(v) -> str | None:
    if not v or not isinstance(v, str):
        return None
    v = v.strip().replace("/", "-").replace(".", "-")
    m = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})", v)
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
    except ValueError:
        return None


def _flat(s: str) -> str:
    return re.sub(r"\s+", "", s)


# 连字符的归一化在 collect_skeleton 里统一维护（采集与核验必须用同一套，
# 否则会出现"采集抽不出、核验又判不对"的两头不一致）。


def _seg_in(seg: str, ev: str) -> bool:
    """判断一段取值是否被依据支持。允许"去掉括号内容"后命中。

    展馆名是重灾区：词典里是"国家会展中心（上海）"，页面写"上海国家会展中心（NECC）"
    或"上海虹桥·国家会展中心"。括号里的城市/英文缩写各家写法不同，
    但核心名一致，去掉括号再比是对的。

    落库的值和依据都要做同样的归一化（全角括号→半角），否则
    "国家会展中心（上海）"和页面上的"国家会展中心(上海)"会被判成两个名字。
    """
    s = _flat(_norm_sep(seg))
    if s in ev:
        return True
    core = re.sub(r"[（(][^）)]*[）)]", "", s)
    return len(core) >= 2 and core in ev


def _month_days(ev_flat: str) -> set[tuple[int, int]]:
    """从"没有年份"的中文写法里解析出 (月, 日) 集合。

    页面极常见的两种："7月24-26日"、"10月12日—14日"。
    年份在展名里（CWP2027）或压根没写，extract_dates 拿不到完整日期，
    但"这个展在哪几天办"这个事实是确定的，可以只核月日。
    """
    out: set[tuple[int, int]] = set()
    for m in re.finditer(r"(\d{1,2})月(\d{1,2})日?(?:\s*[-—至到]\s*(\d{1,2})日?)?", ev_flat):
        mo = int(m.group(1))
        d1 = int(m.group(2))
        d2 = int(m.group(3)) if m.group(3) else d1
        if not (1 <= mo <= 12):
            continue
        # 只收区间两端，不收中间。依据"3月17-20日"能支持 17 日（开展）和 20 日（闭幕），
        # 不能支持 18 日——那不是展期，只是展期里的一天。放宽到整数区间会让
        # "随便填一个落在展会期间的日期"也通过核验，等于闸门失效。
        for d in {d1, d2}:
            if 1 <= d <= 31:
                out.add((mo, d))
    return out


def _date_supported(iso: str, ev_text: str, ev_flat: str) -> tuple[bool, str]:
    """日期是否被依据支持。两级判定：

    Tier 1（严格）：拿依据跑 extract_dates，取值必须等于抽出的起止日之一。
    Tier 2（月日 + 年份核对）：依据没写年份或写法超出正则时，退一步——
            依据里要出现同样的"月日"，且若依据含年份必须一致。
            这一级覆盖了"10月12日—14日，CWP2027 将在…"这类写法，
            年份在展名里而不在日期里。

    两个入参：ev_text 保留空格（英文日期靠空格分词，"1-3 September 2027"
    去空白后变 "1-3September2027"，正则里的 \\s+ 就失配了）；
    ev_flat 去空白，用于做月日的紧凑匹配。
    """
    s, e, _ = extract_dates(ev_text)
    if s and iso in (s, e):
        return True, ""

    try:
        y, m, d = (int(x) for x in iso.split("-"))
    except ValueError:
        return False, "取值格式异常"

    # 依据里出现过的年份（含展名里的 2027）
    years = set(re.findall(r"(20\d{2})", ev_flat))
    if years and str(y) not in years:
        return False, f"依据年份 {sorted(years)} 与取值 {y} 不符"

    md_patterns = (
        rf"{m}月{d}日", rf"{m}月{d}号",
        rf"(?<!\d){m}[-/.]{d}(?!\d)",
        rf"(?<!\d){d}(?!\d)[^0-9]{{0,3}}{m}月",       # 日在前：12日-14日
    )
    if any(re.search(p, ev_flat) for p in md_patterns):
        return True, ""
    # 无年份的中文区间：7月24-26日 / 10月12日—14日
    if (m, d) in _month_days(ev_flat):
        return True, ""
    # 英文月份也认
    m_abbr = ["jan", "feb", "mar", "apr", "may", "jun",
              "jul", "aug", "sep", "oct", "nov", "dec"][m - 1]
    if re.search(rf"{m_abbr}[a-z]*\.?\s*{d}(?!\d)", ev_text, re.I) or \
       re.search(rf"(?<!\d){d}(?!\d)[^0-9]{{0,4}}{m_abbr}", ev_text, re.I):
        return True, ""
    return False, f"依据里找不到 {m} 月 {d} 日"


def _verify(value, evidence: str, body_flat: str, kind: str = "text") -> tuple[bool, str]:
    """evidence 必须真的在正文里出现，且能撑住 value。

    这一步是整套 LLM 抽取唯一的防幻觉闸门。没有它，模型会给出
    格式完美、日期合理、但页面上根本不存在的展期——而且看起来毫无破绽。

    kind 决定"撑住"怎么判：
      date  —— 拿依据去跑 extract_dates，取值必须等于抽出来的起止日之一。
               不能只比数字：依据若是"3月17-20日"，取值 2027-03-17 的数字串
               "20270317" 在这段文字里根本连不起来，会误杀正确答案。
      text  —— 取值本身要出现在依据里（依据可以比取值长，但不能反过来）
    """
    if value is None:
        return False, "null"
    ev_text = _norm_sep(str(evidence or "")).strip()
    ev = _flat(ev_text)
    # 门槛按类型分开：城市名"深圳"可以由"深圳站"三个字撑住，
    # 但"举办"这种两字片段撑不起任何日期或机构名。
    min_len = 4 if kind == "date" else 2
    if len(ev) < min_len:
        return False, "依据过短"
    if ev not in body_flat:
        return False, "依据不在正文中"

    if kind == "date":
        ok, why = _date_supported(str(value)[:10], ev_text, ev)
        return ok, why

    # text：取值可能是顿号连接的多个机构/场馆，逐段核验。
    # 整串比对会误杀：模型把"上海市国际贸易促进委员会 中国汽车工业协会"（原文空格分隔）
    # 写成"上海市国际贸易促进委员会、中国汽车工业协会"，整串当然对不上，但每段都在。
    segs = [s for s in re.split(r"[、，,;；/／\s]+", str(value)) if len(s) >= 2]
    if not segs:
        segs = [str(value)]
    missing = [s for s in segs if not _seg_in(s, ev)]
    if missing:
        return False, f"取值不在依据中（缺 {'、'.join(missing)[:24]}）"
    return True, ""


def extract_one(provider: OpenAICompatProvider, rid: str, body: str, today: date) -> dict:
    prompt = PROMPT % _slices(body)
    raw = provider.complete_full(prompt, system=SYSTEM, temperature=0.0, max_tokens=800)
    out = shape(rid, body, raw, today)
    out["model"] = provider._model
    return out


def shape(rid: str, body: str, raw: str, today: date) -> dict:
    """把模型原始输出变成可入库的字段集合。**不联网**，只做解析与核验。

    与 extract_one 分开，是为了让"调用"和"核验"能各自重跑：
    · 核验规则改了（比如漏传 kind 导致 47 个日期被误杀）→ 不必再花钱调一遍模型
    · 模型换了 → 可以拿同一批正文对比两版输出，成本只有调用那一次
    所以原始响应用 raw 字段存下来，--reverify 直接复用。
    """
    data = _json_of(raw)
    # 正文和依据都用同一套归一化（去空白 + 统一破折号/间隔号），
    # 否则"依据不在正文中"会被一个 en dash 差异触发
    body_flat = _flat(_norm_sep(body))

    out: dict = {"id": rid, "fields": {}, "dropped": {}, "moved": {}, "ok": False,
                 "raw": raw[:1200]}
    if not data:
        out["error"] = "LLM 未返回可解析 JSON"
        return out

    for k in FIELDS + ("prev_start_date", "prev_end_date"):
        cell = data.get(k)
        if not isinstance(cell, dict):
            continue
        v, ev = cell.get("value"), cell.get("evidence", "")

        if k.endswith("_date") or k == "deadline":
            v = _norm_date(v)
        elif k == "edition":
            try:
                v = int(str(v).strip())
                if not 1 <= v <= 200:
                    v = None
            except (TypeError, ValueError):
                v = None
        elif isinstance(v, str):
            v = v.strip() or None

        if v is None:
            continue

        if k == "edition":
            # 中文届次："25" 对不上"第二十五届"的阿拉伯数字，改用届次字样核验
            ok = ("届" in (ev or "") and _flat(ev) in body_flat)
            ok = ok and (_cn(ev) == v) if ok else ok
            if not ok:
                out["dropped"][k] = {"value": v, "why": "届次依据不成立"}
                continue
        else:
            # 日期必须走 date 口径：拿依据解析出起止日再比，
            # 不能拿 "2027-03-27" 去跟 "2027年3月27日-4月5日" 做子串匹配
            kind = "date" if (k.endswith("_date") or k == "deadline") else "text"
            ok, why = _verify(v, ev, body_flat, kind)
            if not ok:
                out["dropped"][k] = {"value": v, "why": why, "evidence": ev[:40]}
                continue

        out["fields"][k] = {"value": v, "method": "llm", "evidence": (ev or "")[:80],
                            "conf": "medium"}

    # 截止日必须是还没到的日子。往届页面上的"报名截止"早已过期，
    # 留着会让 E4 得到"通道已关闭"——那是去年那届的关闭，不是这一届。
    dl = out["fields"].get("deadline")
    if dl:
        try:
            if date.fromisoformat(str(dl["value"])[:10]) < today:
                out["dropped"]["deadline"] = {"value": dl["value"],
                                              "why": "截止日已过去，属往届"}
                out["fields"].pop("deadline")
        except ValueError:
            out["fields"].pop("deadline")

    # 日期归属修正：不丢弃，改"搬家"。
    # 模型经常把往届日期填进 start_date（页面标题里的年份是上一届的），
    # 直接删掉等于浪费一次调用，而且它给出的确实是"这个展上一次办在什么时候"这个真实信息。
    # 原则仍是硬的：prev_* 绝不冒充本届，只是把放错格子的数据挪回该在的格子。
    for cur, prv in (("start_date", "prev_start_date"), ("end_date", "prev_end_date")):
        cell = out["fields"].get(cur)
        if not cell:
            continue
        try:
            s = date.fromisoformat(str(cell["value"])[:10])
        except ValueError:
            continue
        if s < today:
            inp = out["fields"].pop(cur)
            if prv not in out["fields"]:
                inp["conf"] = "low"
                inp["note"] = "模型原填为 start_date，已按日期归属移入往届"
                out["fields"][prv] = inp
                out["moved"][cur] = {"value": s.isoformat(), "to": prv}
            else:
                out["dropped"][cur] = {"value": s.isoformat(),
                                       "why": f"已过去，且 {prv} 已有值"}

    # 反向：模型把未来日期填进 prev_* 也要挪回本届
    for prv, cur in (("prev_start_date", "start_date"), ("prev_end_date", "end_date")):
        cell = out["fields"].get(prv)
        if not cell:
            continue
        try:
            s = date.fromisoformat(str(cell["value"])[:10])
        except ValueError:
            continue
        if s >= today:
            out["fields"].pop(prv)
            out["dropped"][prv] = {"value": s.isoformat(), "why": "日期尚未到来，不属于往届"}

    out["ok"] = bool(out["fields"])
    out["filled"] = sum(1 for k in FIELDS if k in out["fields"])
    return out


_CN = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
       "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def _cn(s: str) -> int | None:
    m = re.search(r"第\s*([0-9]{1,3}|[零〇一二两三四五六七八九十百]{1,6})\s*届", s or "")
    if not m:
        return None
    t = m.group(1)
    if t.isdigit():
        return int(t)
    total = 0
    if "百" in t:
        h, _, t = t.partition("百")
        total += (_CN.get(h, 0) if h else 1) * 100
    if "十" in t:
        h, _, t = t.partition("十")
        total += (_CN.get(h, 0) if h else 1) * 10
    for ch in t:
        total += _CN.get(ch, 0)
    return total or None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--reverify", action="store_true",
                    help="不调用模型，用已存下的 raw 重跑核验（改了闸门规则后用）")
    args = ap.parse_args()

    if not RAW_DIR.is_dir():
        print("✗ 没有找到 %s" % RAW_DIR, file=sys.stderr)
        print("  先跑 collect_skeleton.py 把正文落盘（它默认会存）", file=sys.stderr)
        return 2

    ids = all_ids()
    if args.only:
        want = {s.strip() for s in args.only.split(",") if s.strip()}
        ids = [i for i in ids if i in want]
    if args.limit:
        ids = ids[: args.limit]

    # ---- 只重跑核验：不联网、不花钱 ----
    if args.reverify:
        if not OUT.exists():
            print("✗ 没有 %s，无从重跑" % OUT, file=sys.stderr)
            return 2
        prev = json.loads(OUT.read_text(encoding="utf-8"))
        today = date.today()
        added = removed = 0
        new_recs = []
        for r in prev.get("records", []):
            if not r.get("raw"):
                new_recs.append(r)          # 旧记录没有 raw，原样保留
                continue
            # 必须复用**模型当时看到的那份正文**。渲染前后正文不同，
            # 拿渲染版去核验基于静态版产出的字段，会把正确答案判成"依据不在正文中"。
            src = r.get("body_src", "raw")
            body_file = (RENDERED_DIR if src == "rendered" else RAW_DIR) / f"{r['id']}.txt"
            if not body_file.exists():
                body_file = body_path(r["id"])
            if body_file is None:
                new_recs.append(r)
                continue
            before = len(r.get("fields", {}))
            fixed = shape(r["id"], body_file.read_text(encoding="utf-8"), r["raw"], today)
            fixed["model"] = r.get("model")
            new_recs.append(fixed)
            delta = len(fixed["fields"]) - before
            added += max(0, delta)
            removed += max(0, -delta)
            print("  %-20s %d → %d" % (r["id"], before, len(fixed["fields"])))
        prev["records"] = new_recs
        prev["reverified_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        OUT.write_text(json.dumps(prev, ensure_ascii=False, indent=2), encoding="utf-8")
        print("\n重核验完成：净增 %d 个字段（另降级 %d 个）｜模型未被调用" % (added, removed))
        return 0

    done: dict[str, dict] = {}
    if OUT.exists() and not args.force:
        try:
            prev = json.loads(OUT.read_text(encoding="utf-8"))
            done = {r["id"]: r for r in prev.get("records", []) if r.get("ok")}
        except (json.JSONDecodeError, KeyError):
            done = {}
    todo = [i for i in ids if i not in done and body_path(i) is not None]

    provider = _build_real_provider()
    if provider is None:
        print("✗ 没有可用的 LLM key，无法抽取。", file=sys.stderr)
        print("  需要以下任一（写在 expohub-backend/.env）：", file=sys.stderr)
        print("    AI_PROVIDER=deepseek      DEEPSEEK_API_KEY=sk-...", file=sys.stderr)
        print("    AI_PROVIDER=siliconflow   SILICONFLOW_API_KEY=sk-...", file=sys.stderr)
        print("    AI_PROVIDER=openai-compat OPENAI_COMPAT_API_KEY=... OPENAI_COMPAT_BASE_URL=...", file=sys.stderr)
        print("\n  正文已落盘 %d 个，key 到位后直接重跑本脚本即可，不需要重新抓取。" % len(ids),
              file=sys.stderr)
        return 2

    print("待抽 %d 个（已完成 %d）｜模型 %s @ %s" % (
        len(todo), len(done), provider._model, provider._base_url))
    if args.dry_run:
        return 0

    today = date.today()
    results = list(done.values())
    t0 = time.time()
    # 正文来源在提交时就定下来，并随结果一起存。
    # 后面 --reverify 要拿"模型当时看到的那一份"重跑，不能拿现在磁盘上的最新版，
    # 否则渲染前后正文一变，核验就会把正确答案判成"依据不在正文中"。
    bodies = {i: body_path(i) for i in todo}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(extract_one, provider, i,
                            bodies[i].read_text(encoding="utf-8"), today): i
                for i in todo}
        for i, fut in enumerate(as_completed(futs), 1):
            rid = futs[fut]
            try:
                r = fut.result()
            except Exception as ex:
                r = {"id": rid, "ok": False, "fields": {}, "dropped": {}, "moved": {},
                     "error": f"{type(ex).__name__}: {str(ex)[:60]}"}
            r["body_src"] = bodies[rid].parent.name
            with _LOCK:
                results.append(r)
                # 每条都落盘：LLM 有速率限制，中断后不该从头再来
                OUT.write_text(json.dumps(
                    {"model": provider._model,
                     "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                     "records": results}, ensure_ascii=False, indent=2), encoding="utf-8")
            print("  [%3d/%3d] %d/8 %-20s %s" % (
                i, len(todo), r.get("filled", 0), r["id"], r.get("error", "")))

    ok = [r for r in results if r.get("ok")]
    print("\n完成 %d ｜ 有用字段 %d ｜ 拦下 %d ｜ 搬家 %d ｜ 用时 %.0f 秒" % (
        len(ok), sum(r.get("filled", 0) for r in ok),
        sum(len(r.get("dropped", {})) for r in results),
        sum(len(r.get("moved", {})) for r in results), time.time() - t0))
    print("→ %s" % OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
