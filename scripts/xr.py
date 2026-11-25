#!/usr/bin/env python3
"""xr.py — 短剧评估法条本 规则检索器

只依赖 Python 3.8+ 标准库。规则正本：data/rules.tsv

用法：
    python3 scripts/xr.py domains
    python3 scripts/xr.py domain IP
    python3 scripts/xr.py domain DIA --hard
    python3 scripts/xr.py show IP-04
    python3 scripts/xr.py search 量级
    python3 scripts/xr.py search 对白 --domain DIA
    python3 scripts/xr.py export --json  > rules.json
    python3 scripts/xr.py export --tsv
    python3 scripts/xr.py check                 # 体检：ID 唯一、域合法、字段齐全
    python3 scripts/xr.py selftest              # 自测（离线，不需要任何依赖）
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Dict, List

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RULES_PATH = os.path.join(ROOT, "data", "rules.tsv")

FIELDS = ["id", "domain", "title", "judge", "counter", "source", "strength"]

DOMAIN_NAMES: Dict[str, str] = {
    "IP": "选题与点子",
    "HOOK": "爽点与兑现",
    "STR": "结构与节奏",
    "CHR": "人物与关系",
    "DIA": "对白",
    "VIS": "视听与镜头",
    "BIZ": "商业与合规",
    "MET": "评估方法学",
}

STRENGTHS = ("硬", "中", "软")


# ---------------------------------------------------------------- 读取


def load_rules(path: str = RULES_PATH) -> List[dict]:
    """读 TSV，返回规则列表。字段数不符直接报错，不做猜测。"""
    if not os.path.exists(path):
        raise SystemExit(f"找不到规则文件：{path}")

    with open(path, "r", encoding="utf-8") as fh:
        lines = [ln.rstrip("\n") for ln in fh if ln.strip()]

    if not lines:
        raise SystemExit("规则文件为空")

    header = lines[0].split("\t")
    if header != FIELDS:
        raise SystemExit(
            "表头不符。期望：\n  " + "\t".join(FIELDS) + "\n实际：\n  " + "\t".join(header)
        )

    rules: List[dict] = []
    for lineno, line in enumerate(lines[1:], start=2):
        parts = line.split("\t")
        if len(parts) != len(FIELDS):
            raise SystemExit(
                f"第 {lineno} 行有 {len(parts)} 列，应为 {len(FIELDS)} 列：{line[:80]}"
            )
        rules.append(dict(zip(FIELDS, parts)))
    return rules


# ---------------------------------------------------------------- 渲染


def esc(text: str) -> str:
    """表格单元格转义：竖线会破坏 markdown 表格。"""
    return text.replace("|", "\\|")


def render_table(rules: List[dict], show_counter: bool = True) -> str:
    if not rules:
        return "_（无匹配规则）_"
    if show_counter:
        head = "| 编号 | 规则 | 判据 | 反例／边界 | 出处 | 强度 |"
        sep = "|---|---|---|---|---|---|"
        rows = [
            f"| `{r['id']}` | {esc(r['title'])} | {esc(r['judge'])} | "
            f"{esc(r['counter'])} | {esc(r['source'])} | {r['strength']} |"
            for r in rules
        ]
    else:
        head = "| 编号 | 规则 | 判据 | 出处 | 强度 |"
        sep = "|---|---|---|---|---|"
        rows = [
            f"| `{r['id']}` | {esc(r['title'])} | {esc(r['judge'])} | "
            f"{esc(r['source'])} | {r['strength']} |"
            for r in rules
        ]
    return "\n".join([head, sep] + rows)


def render_one(r: dict) -> str:
    return "\n".join(
        [
            f"## {r['id']} · {r['title']}",
            "",
            f"- **域**：{r['domain']}（{DOMAIN_NAMES.get(r['domain'], '?')}）",
            f"- **强度**：{r['strength']}",
            f"- **出处**：{r['source']}",
            "",
            "**判据**",
            "",
            r["judge"],
            "",
            "**反例／边界**",
            "",
            r["counter"] or "（无）",
        ]
    )


# ---------------------------------------------------------------- 过滤


def filter_rules(
    rules: List[dict],
    domain: str = None,
    hard_only: bool = False,
    keyword: str = None,
) -> List[dict]:
    out = rules
    if domain:
        key = domain.upper()
        out = [r for r in out if r["domain"] == key]
    if hard_only:
        out = [r for r in out if r["strength"] == "硬"]
    if keyword:
        kw = keyword.lower()
        out = [
            r
            for r in out
            if kw in " ".join(r.values()).lower()
        ]
    return out


# ---------------------------------------------------------------- 子命令


def cmd_domains(rules: List[dict], _args) -> int:
    counts: Dict[str, int] = {}
    hard: Dict[str, int] = {}
    for r in rules:
        counts[r["domain"]] = counts.get(r["domain"], 0) + 1
        if r["strength"] == "硬":
            hard[r["domain"]] = hard.get(r["domain"], 0) + 1

    print("| 前缀 | 域 | 条数 | 其中硬规则 |")
    print("|---|---|---|---|")
    for key in DOMAIN_NAMES:
        if key in counts:
            print(f"| `{key}` | {DOMAIN_NAMES[key]} | {counts[key]} | {hard.get(key, 0)} |")
    print(f"| — | **合计** | **{len(rules)}** | **{sum(hard.values())}** |")
    return 0


def cmd_domain(rules: List[dict], args) -> int:
    key = args.name.upper()
    if key not in DOMAIN_NAMES:
        raise SystemExit(f"未知域：{args.name}。可用：{', '.join(DOMAIN_NAMES)}")
    sel = filter_rules(rules, domain=key, hard_only=args.hard)
    name = DOMAIN_NAMES[key]
    scope = "（仅硬规则）" if args.hard else ""
    print(f"# {key} · {name}{scope}\n")
    print(f"共 {len(sel)} 条。\n")
    print(render_table(sel, show_counter=not args.brief))
    return 0


def cmd_show(rules: List[dict], args) -> int:
    target = args.id.upper()
    for r in rules:
        if r["id"] == target:
            print(render_one(r))
            return 0
    raise SystemExit(f"没有这条规则：{args.id}")


def cmd_search(rules: List[dict], args) -> int:
    sel = filter_rules(rules, domain=args.domain, hard_only=args.hard, keyword=args.keyword)
    if args.json:
        print(json.dumps(sel, ensure_ascii=False, indent=2))
        return 0
    print(f"# 搜索：{args.keyword}\n")
    print(f"命中 {len(sel)} 条。\n")
    print(render_table(sel, show_counter=not args.brief))
    return 0


def cmd_export(rules: List[dict], args) -> int:
    if args.json:
        payload = {
            "name": "短剧评估法条本",
            "version": "1.0.0",
            "license": "使用须署名；商用须取得作者书面授权",
            "domains": DOMAIN_NAMES,
            "rules": rules,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    print("\t".join(FIELDS))
    for r in rules:
        print("\t".join(r[f] for f in FIELDS))
    return 0


def cmd_check(rules: List[dict], _args) -> int:
    problems: List[str] = []
    seen = set()
    for r in rules:
        if r["id"] in seen:
            problems.append(f"编号重复：{r['id']}")
        seen.add(r["id"])
        prefix = r["id"].split("-")[0]
        if prefix != r["domain"]:
            problems.append(f"{r['id']} 的域前缀与 domain={r['domain']} 不一致")
        if r["domain"] not in DOMAIN_NAMES:
            problems.append(f"{r['id']} 的域非法：{r['domain']}")
        if r["strength"] not in STRENGTHS:
            problems.append(f"{r['id']} 的强度非法：{r['strength']}（应为 硬/中/软）")
        for f in ("title", "judge", "source"):
            if not r[f].strip():
                problems.append(f"{r['id']} 缺字段 {f}")

    if problems:
        print(f"发现 {len(problems)} 个问题：")
        for p in problems:
            print("  -", p)
        return 1
    print(f"OK：{len(rules)} 条规则，编号唯一、域与强度合法、必填字段齐全。")
    return 0


def cmd_selftest(_rules: List[dict], _args) -> int:
    import tempfile

    failures: List[str] = []

    def ok(cond: bool, label: str) -> None:
        if not cond:
            failures.append(label)

    # 1. 正本可读
    rules = load_rules()
    ok(len(rules) > 0, "正本应至少有一条规则")
    ok(all(r["strength"] in STRENGTHS for r in rules), "强度字段应合法")

    # 2. 过滤
    ip = filter_rules(rules, domain="IP")
    ok(len(ip) > 0 and all(r["domain"] == "IP" for r in ip), "domain 过滤应只返回该域")
    hard = filter_rules(rules, hard_only=True)
    ok(all(r["strength"] == "硬" for r in hard), "hard 过滤应只返回硬规则")
    both = filter_rules(rules, domain="IP", hard_only=True)
    ok(all(r["domain"] == "IP" and r["strength"] == "硬" for r in both), "组合过滤应同时生效")

    # 3. 搜索
    hit = filter_rules(rules, keyword="量级")
    ok(len(hit) > 0, "关键词「量级」应有命中")
    ok(filter_rules(rules, keyword="__不存在的词__") == [], "无命中应返回空")

    # 4. 渲染
    table = render_table(ip)
    ok(table.count("\n") == len(ip) + 1, "表格行数应为规则数 + 表头分隔两行中的换行数")
    ok("|" in table, "表格应含竖线")

    # 5. 损坏的表头应报错，而不是静默跳过
    with tempfile.NamedTemporaryFile("w", suffix=".tsv", delete=False, encoding="utf-8") as fh:
        fh.write("a\tb\tc\n1\t2\t3\n")
        bad_path = fh.name
    try:
        load_rules(bad_path)
        ok(False, "表头不符应抛 SystemExit")
    except SystemExit:
        pass
    finally:
        os.unlink(bad_path)

    # 6. 列数不符应报错
    with tempfile.NamedTemporaryFile("w", suffix=".tsv", delete=False, encoding="utf-8") as fh:
        fh.write("\t".join(FIELDS) + "\n" + "\t".join(["IP-99", "IP"]) + "\n")
        bad_path2 = fh.name
    try:
        load_rules(bad_path2)
        ok(False, "列数不符应抛 SystemExit")
    except SystemExit:
        pass
    finally:
        os.unlink(bad_path2)

    # 7. 正本体检
    if cmd_check(rules, None) != 0:
        failures.append("正本体检未通过")

    if failures:
        print(f"FAIL {len(failures)} 项：")
        for f in failures:
            print("  -", f)
        return 1
    print("PASS：检索器自测全部通过。")
    return 0


# ---------------------------------------------------------------- 入口


def _force_utf8_stdio() -> None:
    """Windows 控制台默认 GBK，会让 ⭐ 一类字符直接抛异常。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass


def main(argv: List[str]) -> int:
    _force_utf8_stdio()
    parser = argparse.ArgumentParser(
        description="短剧评估法条本 · 规则检索器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="cmd")

    p = sub.add_parser("domains", help="列出所有域与条数")
    p.set_defaults(func=cmd_domains)

    p = sub.add_parser("domain", help="按域列出规则")
    p.add_argument("name", help="域前缀，如 IP / HOOK / DIA / MET")
    p.add_argument("--hard", action="store_true", help="只要硬规则")
    p.add_argument("--brief", action="store_true", help="省略反例列")
    p.set_defaults(func=cmd_domain)

    p = sub.add_parser("show", help="显示一条规则全文")
    p.add_argument("id", help="规则编号，如 IP-04")
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("search", help="按关键词搜索")
    p.add_argument("keyword")
    p.add_argument("--domain", help="限定域")
    p.add_argument("--hard", action="store_true", help="只要硬规则")
    p.add_argument("--json", action="store_true", help="输出 JSON")
    p.add_argument("--brief", action="store_true", help="省略反例列")
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("export", help="导出全部规则")
    p.add_argument("--json", action="store_true", help="导出 JSON（默认 TSV）")
    p.set_defaults(func=cmd_export)

    p = sub.add_parser("check", help="体检规则文件")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("selftest", help="离线自测检索器")
    p.set_defaults(func=cmd_selftest)

    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 1

    rules = load_rules()
    return args.func(rules, args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
