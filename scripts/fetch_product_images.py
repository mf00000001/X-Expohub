#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""fetch_product_images.py — 把名录展品的外链图本地化到前端 public/products/

背景
====
catalog_products 共 67,357 条，只有 751 条带真实图，且这些地址绝大多数在
https://img.expocme.cn/ 上 —— 该子域名当前已无法解析（DNS 失败），浏览器里
必然破图。原始对象在 https://imgs.expocme.cn/ 上仍可访问（同 path 同文件名），
所以脚本内置「镜像改写」：先按原地址请求，失败后依次尝试
  1) img.expocme.cn -> imgs.expocme.cn
  2) http:// -> https://
再退化为「只保留 path 换到 imgs 主机」等组合。

做什么
====
1. 读 catalog_products.image 里所有 http(s) 地址（跳过已经本地化的 /products/xxx.jpg）；
2. 并发 ≤5 下载，带 Referer（同源首页）+ UA，超时与重试，失败跳过并归类统计；
3. 用 Pillow 统一重编码成 JPEG（长边 ≤ --max-edge，起始质量 --quality），
   并按 --max-bytes 逐级降档，保证 751 张总量可预期（默认 ≈16MB，与占位图合计 < 20MB）；
4. 下载成功 → 写 expo-hub-frontend/public/products/<id>.jpg，
   并把 catalog_products.image 与 products.images 同步改成 /products/<id>.jpg；
5. 打印成功 / 失败 / 跳过数量、字节数、失败原因分布。

用法
====
    python scripts/fetch_product_images.py --limit 20      # 试跑 20 条
    python scripts/fetch_product_images.py                 # 全量
    python scripts/fetch_product_images.py --no-db         # 只下图片，不动库
    python scripts/fetch_product_images.py --dry-run       # 只打印将要处理的清单
    python scripts/fetch_product_images.py --force         # 已存在的图也重下

约定
====
- 不改表结构，不新增字段；唯一写入的两列是 catalog_products.image / products.images
  （products 表没有 image 列，历史字段名就是 images，存的是 JSON 数组）。
- 幂等：图片存在且能解码时默认跳过网络请求，但仍会把库里已本地化好的行对齐。
- 可修复：如果 image 已经是 /products/xxx.jpg 但文件丢了，脚本会从 detail_html
  里第一张 <img src> 还原原始地址重新下载（原图地址就是导入时从那里取的）。
- 输出目录可被 Vite 直接以 /products/<id>.jpg 访问（public/ 为静态根）。
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sqlite3
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PUBLIC = REPO / "expo-hub-frontend" / "public"
DEFAULT_OUT = PUBLIC / "products"
DEFAULT_DB = REPO / "expohub-backend" / "expohub.db"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
# 原域名已停解析，同名对象在 imgs.* 上仍可访问（已用 6 条样本验证 200 + image/jpeg）
HOST_MIRRORS = {"img.expocme.cn": "imgs.expocme.cn"}

try:  # Pillow 只用于重编码，缺失时退化为「原样落盘」（浏览器仍能解码）
    from PIL import Image, ImageOps
except Exception:  # pragma: no cover
    Image = None
    ImageOps = None

_print_lock = threading.Lock()


def log(msg: str) -> None:
    with _print_lock:
        print(msg, flush=True)


def candidates(url: str) -> list[str]:
    """原地址优先，再按「镜像主机 / https 升级」组合出候选地址，去重保序。"""
    url = url.strip()
    seeds: list[str] = [url]
    if url.startswith("http://"):
        seeds.append("https://" + url[len("http://"):])
    ordered: list[str] = []
    for u in seeds:
        if u not in ordered:
            ordered.append(u)

    # 第二轮：把主机替换成镜像主机，并补齐 https 版本
    for u in list(ordered):
        parts = urllib.parse.urlsplit(u)
        mirrored = HOST_MIRRORS.get(parts.hostname or "")
        if not mirrored:
            continue
        netloc = mirrored + (f":{parts.port}" if parts.port else "")
        alt = urllib.parse.urlunsplit((parts.scheme, netloc, parts.path, parts.query, ""))
        if alt not in ordered:
            ordered.append(alt)
        https_alt = urllib.parse.urlunsplit(("https", netloc, parts.path, parts.query, ""))
        if https_alt not in ordered:
            ordered.append(https_alt)
    return ordered


def referer_of(url: str) -> str:
    parts = urllib.parse.urlsplit(url)
    scheme = parts.scheme or "https"
    host = parts.hostname or ""
    return f"{scheme}://{host}/" if host else ""


def http_get(url: str, timeout: float) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Referer": referer_of(url),
            "Accept": "image/avif,image/webp,image/jpeg,image/png,image/*;q=0.8,*/*;q=0.5",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
    if not data:
        raise ValueError("empty body")
    return data


def download_with_retry(url: str, timeout: float, retries: int) -> tuple[bytes, str, str | None]:
    """返回 (bytes, 命中的 URL, None) 或 (b'', '', 失败原因)。"""
    last_err = ""
    for attempt in range(retries + 1):
        for u in candidates(url):
            try:
                return http_get(u, timeout), u, None
            except urllib.error.HTTPError as e:
                last_err = f"HTTP {e.code}"
            except urllib.error.URLError as e:
                reason = getattr(e, "reason", e)
                last_err = f"URL({reason})" if "getaddrinfo" not in str(reason) else "DNS"
            except Exception as e:  # socket timeout、SSL、空响应
                last_err = type(e).__name__
        if attempt < retries:
            time.sleep(0.6 * (attempt + 1))
    return b"", "", last_err or "unknown"


def encode_jpeg(data: bytes, max_edge: int, quality: int, max_bytes: int) -> tuple[bytes, str, int, int]:
    """重编码为 JPEG；返回 (bytes, 说明, 宽, 高)。

    体积控制用「逐级降档」而不是固定质量：先按 --max-edge + --quality 编码，
    超预算就依次降长边（720/640/560/480/420/360）和降质量（78..48），
    取第一个落进 --max-bytes 的组合 —— 每张图都尽量保住清晰度，
    总目录体积却可预期（751 × max_bytes ≈ 16MB）。Pillow 缺失时原样返回。
    """
    if Image is None:
        return data, "raw", 0, 0
    with Image.open(io.BytesIO(data)) as im:
        im = ImageOps.exif_transpose(im)
        src_fmt = "jpeg" if data[:2] == b"\xff\xd8" else "other"
        # 统一白底：PNG 透明图直接转 JPEG 会出黑块
        if im.mode in ("RGBA", "LA", "P"):
            im = im.convert("RGBA")
            canvas = Image.new("RGB", im.size, (255, 255, 255))
            canvas.paste(im, mask=im.split()[-1])
            im = canvas
        else:
            im = im.convert("RGB")

        edges = [max_edge] + [e for e in (720, 640, 560, 480, 420, 360) if 0 < e < max_edge]
        qualities = [quality] + [q for q in (78, 72, 66, 60, 54, 48) if 0 < q < quality]
        best = b""
        best_wh = (im.width, im.height)
        for edge in edges:
            base = im
            if edge and max(im.size) > edge:
                scale = edge / float(max(im.size))
                base = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.LANCZOS)
            for q in qualities:
                buf = io.BytesIO()
                base.save(buf, format="JPEG", quality=q, optimize=True, progressive=True)
                out = buf.getvalue()
                best, best_wh = out, base.size
                if not max_bytes or len(out) <= max_bytes:
                    return out, src_fmt, base.width, base.height
        return best, src_fmt, best_wh[0], best_wh[1]


def already_localized(src: str) -> bool:
    s = (src or "").strip()
    return s.startswith("/products/")


def existing_ok(path: Path) -> bool:
    try:
        if path.stat().st_size < 256:
            return False
        if Image is None:
            return True
        with Image.open(path) as im:
            im.verify()
        return True
    except Exception:
        return False


IMG_SRC_RE = re.compile(r"""<img\b[^>]*?\bsrc\s*=\s*["']([^"']+)["']""", re.I)


def url_from_html(html: str | None) -> str:
    """从 detail_html 的第一张 <img src> 还原原始地址（导入时就是从这取的图）。

    兼容 `//host/path`、`/path`（补 expocme 主机）、裸域名，以及 data: 占位图。
    """
    if not html:
        return ""
    m = IMG_SRC_RE.search(html)
    if not m:
        return ""
    src = (m.group(1) or "").strip()
    if not src or src.lower().startswith("data:"):
        return ""
    if src.startswith("//"):
        return "https:" + src
    if src.lower().startswith(("http://", "https://")):
        return src
    if src.startswith("/"):
        return "https://img.expocme.cn" + src
    return "https://" + src


def collect(
    conn: sqlite3.Connection, out_dir: Path, limit: int | None
) -> tuple[list[tuple[int, str, str]], Counter]:
    """返回 (待办[(id, url, 类型)], 跳过统计)。类型: 'download' | 'repair'。"""
    rows = conn.execute(
        "SELECT id, image, detail_html FROM catalog_products "
        "WHERE image IS NOT NULL AND TRIM(image) <> '' ORDER BY id"
    ).fetchall()
    todo: list[tuple[int, str, str]] = []
    skipped = Counter()
    for pid, img, html in rows:
        pid = int(pid)
        img = (img or "").strip()
        target = out_dir / f"{pid}.jpg"
        if already_localized(img):
            # 库里已是本地路径：文件在就跳过；文件丢了就从 detail_html 还原地址补齐
            if existing_ok(target):
                skipped["already_local"] += 1
                continue
            recovered = url_from_html(html)
            if recovered:
                skipped["repair_needed"] += 1
                todo.append((pid, recovered, "repair"))
            else:
                skipped["local_missing_no_source"] += 1
            continue
        if not img.lower().startswith(("http://", "https://")):
            # 形如 file:C:\... 的本地绝对路径，任何浏览器都取不到，只能跳过
            skipped["not_http"] += 1
            continue
        if "file:///" in img.lower() or img.lower().startswith("file:"):
            # 导入残留：https://file:///C:\Users\...\wps1.png（Word/ksohtml 临时路径）
            skipped["broken_file_url"] += 1
            continue
        todo.append((pid, img, "download"))
    if limit:
        todo = todo[:limit]
    return todo, skipped


def write_db(conn: sqlite3.Connection, done: list[int]) -> int:
    """把本地化成功的 id 写回 catalog_products.image 与 products.images（JSON 数组）。"""
    n = 0
    for pid in done:
        rel = f"/products/{pid}.jpg"
        conn.execute("UPDATE catalog_products SET image = ? WHERE id = ?", (rel, pid))
        conn.execute("UPDATE products SET images = ? WHERE id = ?", (json.dumps([rel]), pid))
        n += 1
    conn.commit()
    return n


def main() -> int:
    ap = argparse.ArgumentParser(description="本地化名录展品外链图")
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--limit", type=int, default=0, help="只处理前 N 条（试跑用）")
    ap.add_argument("--concurrency", type=int, default=5, help="并发数，上限 5")
    ap.add_argument("--timeout", type=float, default=20.0)
    ap.add_argument("--retries", type=int, default=2)
    ap.add_argument("--max-edge", type=int, default=720, help="长边像素上限，0 表示不缩放")
    ap.add_argument("--quality", type=int, default=80, help="JPEG 起始质量 60-95")
    ap.add_argument("--max-bytes", type=int, default=22000,
                    help="单张字节预算，超出则逐级降长边/质量；0 表示不限")
    ap.add_argument("--force", action="store_true", help="已存在的图也重新下载")
    ap.add_argument("--no-db", action="store_true", help="不回写数据库")
    ap.add_argument("--dry-run", action="store_true", help="只打印待处理清单")
    args = ap.parse_args()

    workers = max(1, min(5, args.concurrency))
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    db_path = Path(args.db)
    if not db_path.exists():
        print(f"数据库不存在: {db_path}", file=sys.stderr)
        return 2

    conn = sqlite3.connect(db_path, timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")
    try:
        todo, skipped = collect(conn, out_dir, args.limit or None)
        print(f"候选项: {len(todo)} 条（跳过: {dict(skipped) or '无'}）")
        if args.dry_run:
            for pid, url, kind in todo[:50]:
                print(f"  #{pid} [{kind}] {url}")
            if len(todo) > 50:
                print(f"  ... 其余 {len(todo) - 50} 条省略")
            return 0

        stats = Counter()
        reasons = Counter()
        failures: list[tuple[int, str, str]] = []
        done_ids: list[int] = []
        bytes_written = 0
        started = time.time()
        lock = threading.Lock()

        def work(item: tuple[int, str, str]) -> None:
            nonlocal bytes_written
            pid, url, kind = item
            target = out_dir / f"{pid}.jpg"
            # repair 的语义就是「库里说本地化好了但文件不在」，必须重下，不能走 skip
            if kind != "repair" and not args.force and existing_ok(target):
                with lock:
                    stats["exist"] += 1
                    done_ids.append(pid)
                return
            try:
                raw, hit, err = download_with_retry(url, args.timeout, args.retries)
                if err:
                    raise RuntimeError(err)
                jpg, fmt, w, h = encode_jpeg(raw, args.max_edge, args.quality, args.max_bytes)
                tmp = target.with_suffix(".jpg.part")
                tmp.write_bytes(jpg)
                tmp.replace(target)
                with lock:
                    stats["success"] += 1
                    stats["repair" if kind == "repair" else "download"] += 1
                    stats["mirror" if hit != url else "direct"] += 1
                    stats[f"fmt_{fmt}"] += 1
                    done_ids.append(pid)
                    bytes_written += len(jpg)
                    n = stats["success"] + stats["exist"]
                    if n % 25 == 0:
                        log(f"  ...已处理 {n}/{len(todo)}，成功 {stats['success']}，失败 {len(failures)}")
            except Exception as e:
                reason = str(e) or type(e).__name__
                with lock:
                    stats["failed"] += 1
                    reasons[reason] += 1
                    failures.append((pid, url, reason))

        with ThreadPoolExecutor(max_workers=workers) as pool:
            list(pool.map(work, todo))

        elapsed = time.time() - started
        ok_ids = sorted(set(done_ids))
        print("\n===== 结果 =====")
        print(f"成功下载 {stats['success']} 张（原地址直连 {stats['direct']}，经镜像 {stats['mirror']}；"
              f"其中修复已本地化缺图 {stats['repair']} 张）")
        print(f"跳过已存在 {stats['exist']} 张，失败 {stats['failed']} 张")
        print(f"写入字节 {bytes_written / 1024 / 1024:.2f} MB，用时 {elapsed:.1f}s，并发 {workers}")
        if skipped.get("not_http"):
            print(f"跳过非 http 地址（file: 本地盘符，浏览器无法访问）{skipped['not_http']} 条")
        if skipped.get("broken_file_url"):
            print(f"跳过坏地址（https://file:///C:\\... 导入残留，前端会落品类占位图）{skipped['broken_file_url']} 条")
        if skipped.get("local_missing_no_source"):
            print(f"警告：{skipped['local_missing_no_source']} 条已本地化行缺图且 detail_html 里没有原图地址")
        if reasons:
            print("失败原因分布：")
            for reason, n in reasons.most_common(8):
                print(f"  {reason}: {n}")
        if failures:
            print("失败样例（最多 10 条）：")
            for pid, url, reason in failures[:10]:
                print(f"  #{pid} {reason} :: {url[:90]}")
        if Image is None:
            print("注意：未安装 Pillow，图片按原始字节落盘（未重编码/未缩放）")

        if ok_ids and not args.no_db:
            n = write_db(conn, ok_ids)
            print(f"数据库已同步 {n} 行（catalog_products.image + products.images）")
        elif args.no_db:
            print("--no-db：数据库未改动")

        total_bytes = sum(p.stat().st_size for p in out_dir.glob("*.jpg")) if out_dir.exists() else 0
        print(f"public/products 现有 {len(list(out_dir.glob('*.jpg')))} 张 / {total_bytes / 1024 / 1024:.2f} MB")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
