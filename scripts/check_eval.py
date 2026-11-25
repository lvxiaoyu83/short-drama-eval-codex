#!/usr/bin/env python3
"""check_eval.py — 体检一份评估单

校验的不是"结论对不对"，而是**形式是否守纪律**：

1. 引用的每个规则编号在 data/rules.tsv 里存在
2. 必填章节齐全（事实层 / 命中清单 / 裁决）
3. 带了署名与授权说明（LICENSE 第三节）
4. 没有出现"总分"式表述（MET-14）
5. 没有出现"认证 / 审定"式背书表述（LICENSE 第五节）

不做的事：判定分档对不对、判据用对没对。那是人的活（MET-01）。

用法：
    python3 scripts/check_eval.py examples/示例评估单_小城老照相馆.md
    python3 scripts/check_eval.py --all examples/
    python3 scripts/check_eval.py --json 评估单.md
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Dict, List

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RULES_PATH = os.path.join(ROOT, "data", "rules.tsv")

# 形如 IP-04、HOOK-03、MET-16，允许反引号包裹
ID_PATTERN = re.compile(r"\b(IP|HOOK|STR|CHR|DIA|VIS|BIZ|MET)-(\d{2})\b")

REQUIRED_SECTIONS: List[str] = ["事实层", "命中清单", "裁决"]

BANNED_PATTERNS: List[tuple] = [
    (re.compile(r"总分\s*[:：]"), "出现了「总分」，MET-14 禁止给总分", "MET-14"),
    (re.compile(r"综合评分\s*[:：]"), "出现了「综合评分」，MET-14 禁止给总分", "MET-14"),
    (re.compile(r"评分\s*[:：]\s*\d"), "出现了数字评分，MET-14 禁止给总分", "MET-14"),
    (re.compile(r"经.{0,8}认证"), "出现了认证式表述，LICENSE 第五节禁止", "LICENSE"),
    (re.compile(r"作者审定|作者背书"), "出现了背书式表述，LICENSE 第五节禁止", "LICENSE"),
    (re.compile(r"予以驳回|判死|直接打回"), "出现了闸门式表述，MET-01 禁止", "MET-01"),
]

ATTRIBUTION_MARKERS = ["短剧评估法条本", "使用须署名"]


def load_ids(path: str = RULES_PATH) -> Dict[str, dict]:
    ids: Dict[str, dict] = {}
    with open(path, "r", encoding="utf-8") as fh:
        header = fh.readline().rstrip("\n").split("\t")
        for line in fh:
            line = line.rstrip("\n")
            if not line.strip():
                continue
            row = dict(zip(header, line.split("\t")))
            if "id" in row:
                ids[row["id"]] = row
    return ids


def check_file(path: str, known: Dict[str, dict]) -> List[dict]:
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()

    findings: List[dict] = []

    def add(level: str, msg: str, rule: str = "") -> None:
        findings.append({"level": level, "msg": msg, "rule": rule})

    # 1. 规则编号是否都存在
    cited = sorted({f"{a}-{b}" for a, b in ID_PATTERN.findall(text)})
    unknown = [c for c in cited if c not in known]
    for cid in unknown:
        add("error", f"引用了不存在的规则编号：{cid}", cid)
    if not cited:
        add("warn", "整份评估单没有引用任何规则编号——这通常意味着它不是按法条本做的", "IP-18")

    # 2. 必填章节
    for sec in REQUIRED_SECTIONS:
        if sec not in text:
            add("error", f"缺少必填章节：{sec}")

    # 3. 署名
    for marker in ATTRIBUTION_MARKERS:
        if marker not in text:
            add("error", f"缺少署名标记：{marker}（LICENSE 第三节）", "LICENSE")

    # 4. 禁用表述
    for pattern, msg, rule in BANNED_PATTERNS:
        for m in pattern.finditer(text):
            line = text[: m.start()].count("\n") + 1
            add("error", f"第 {line} 行：{msg}", rule)

    # 5. 分档是否给出
    if not re.search(r"分档\s*[:：]\s*(首选|可做|不建议)", text):
        add("warn", "没有找到「分档：首选／可做／不建议」——MET-14 要求三档结论")

    # 6. 覆盖面是否声明
    if "覆盖面" not in text:
        add("warn", "没有声明覆盖面（查了几个域、多少条规则）——SKILL.md 第 3 步要求")

    # 7. 事实层不能只有结论（粗检：事实层段落里应至少有一处引用号或具体集场）
    m = re.search(r"##\s*1\..{0,20}事实层(.{0,3000}?)(?=\n##\s|\Z)", text, re.S)
    if m:
        body = m.group(1)
        if not re.search(r"(第\s*\d+\s*集|场|「|“|\"|照片|台词)", body):
            add("warn", "事实层里找不到任何位置或引文，可能写成了结论", "MET-12")

    return findings


def main(argv: List[str]) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass

    ap = argparse.ArgumentParser(description="体检评估单是否守纪律")
    ap.add_argument("path", nargs="?", help="评估单路径")
    ap.add_argument("--all", metavar="DIR", help="体检目录下所有 .md")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--strict", action="store_true", help="把 warn 也算失败")
    args = ap.parse_args(argv)

    known = load_ids()

    targets: List[str] = []
    if args.all:
        for name in sorted(os.listdir(args.all)):
            if name.endswith(".md"):
                targets.append(os.path.join(args.all, name))
    elif args.path:
        targets = [args.path]
    else:
        ap.print_help()
        return 1

    report = {}
    failed = False
    for path in targets:
        if not os.path.exists(path):
            report[path] = [{"level": "error", "msg": "文件不存在", "rule": ""}]
            failed = True
            continue
        findings = check_file(path, known)
        report[path] = findings
        errors = [f for f in findings if f["level"] == "error"]
        warns = [f for f in findings if f["level"] == "warn"]
        if errors or (args.strict and warns):
            failed = True

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1 if failed else 0

    for path, findings in report.items():
        try:
            rel = os.path.relpath(path, ROOT)
        except ValueError:  # Windows 跨盘符
            rel = path
        if not findings:
            print(f"PASS  {rel}")
            continue
        errors = [f for f in findings if f["level"] == "error"]
        warns = [f for f in findings if f["level"] == "warn"]
        status = "FAIL" if errors else "WARN"
        print(f"{status}  {rel}  （error {len(errors)} / warn {len(warns)}）")
        for f in findings:
            tag = "  ✗" if f["level"] == "error" else "  !"
            rule = f" [{f['rule']}]" if f["rule"] else ""
            print(f"{tag} {f['msg']}{rule}")

    print()
    print("通过" if not failed else "未通过")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
