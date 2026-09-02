#!/usr/bin/env python3
"""
ExpoHub 后端质量门禁（P7）

运行 expohub-backend 全量测试 + 覆盖率统计，并与基线比对：
  - 默认：覆盖率不得低于基线（防回退）
  - --update-baseline：把当前覆盖率记为基线
  - --threshold N：以 N(%) 为门限（覆盖默认基线）

用法：
  python scripts/quality_gate.py                    # 门禁检查
  python scripts/quality_gate.py --update-baseline  # 刷新基线
  python scripts/quality_gate.py --threshold 70     # 自定义门限

退出码：0=通过；1=未达标或测试失败
"""
import argparse
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(ROOT, "expohub-backend")
BASELINE_FILE = os.path.join(BACKEND, "coverage_baseline.txt")
COVERAGE_JSON = os.path.join(BACKEND, "coverage.json")


def run_tests() -> int:
    """返回覆盖率百分比（测试失败返回 -1）"""
    cmd = [
        sys.executable, "-m", "pytest", "tests",
        "--no-header", "-p", "no:cacheprovider",
        "--cov=app", "--cov-report=json",
    ]
    proc = subprocess.run(cmd, cwd=BACKEND, capture_output=True, text=True)
    if proc.returncode != 0:
        print("[gate] 测试未通过，退出码", proc.returncode)
        print(proc.stdout[-1500:])
        print(proc.stderr[-1500:])
        return -1
    if not os.path.exists(COVERAGE_JSON):
        print("[gate] 缺少 coverage.json")
        return -1
    with open(COVERAGE_JSON, encoding="utf-8") as f:
        data = json.load(f)
    return float(data["totals"]["percent_covered"])


def main() -> int:
    ap = argparse.ArgumentParser(description="ExpoHub 后端覆盖率门禁")
    ap.add_argument("--update-baseline", action="store_true", help="刷新基线")
    ap.add_argument("--threshold", type=float, default=None, help="覆盖率门限(%)")
    args = ap.parse_args()

    covered = run_tests()
    if covered < 0:
        return 1

    if args.update_baseline:
        with open(BASELINE_FILE, "w", encoding="utf-8") as f:
            f.write(f"{covered:.4f}\n")
        print(f"[gate] 基线已更新: {covered:.4f}% -> {BASELINE_FILE}")
        return 0

    threshold = args.threshold
    if threshold is None:
        if not os.path.exists(BASELINE_FILE):
            print("[gate] 无基线文件，请先运行 --update-baseline")
            return 1
        threshold = float(open(BASELINE_FILE, encoding="utf-8").read().strip())

    ok = covered >= threshold
    status = "PASS" if ok else "FAIL"
    print(f"[gate] coverage={covered:.1f}% threshold={threshold:.1f}% -> {status}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
