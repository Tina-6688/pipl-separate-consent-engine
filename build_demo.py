# -*- coding: utf-8 -*-
"""生成静态演示页 demo.html

设计原则：
  判定逻辑只在 Python（engine.py）里有一份。
  本脚本跑完引擎，把结果序列化嵌进 HTML；页面里的 JS 只做渲染，不含任何判定。
  → 不会有第二套实现漂移。

用法：
  python build_demo.py
  → 生成 demo.html（单文件，零依赖，双击即开）
"""
from __future__ import annotations

import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import yaml  # noqa: E402

from engine import load_engine  # noqa: E402
from run_cases import load_cases  # noqa: E402

YAML_PATH = os.path.join(HERE, "rules", "pipl-separate-consent_v2.5.yaml")
TEMPLATE = os.path.join(HERE, "_demo_template.html")
OUT = os.path.join(HERE, "demo.html")


def short_title(case: dict) -> str:
    """左侧列表用的短标签：优先用「类型」，它本身就是为短标签写的

    例：正例·跨境叠加 / 反例·明确不适用 / 例外·25条但书
    """
    t = (case.get("type") or "").strip()
    t = t.replace("（新增）", "").replace("★", "").strip(" ·")
    if t:
        return t
    d = (case.get("desc") or "").strip()
    return (d[:14] + "…") if len(d) > 14 else d


def main():
    data = yaml.safe_load(open(YAML_PATH, encoding="utf-8"))
    cases = load_cases()["cases"]
    eng = load_engine()

    # 规则元数据（展示用）
    rules_meta = {}
    for r in data["rules"]:
        lb = r.get("legal_basis") or {}
        quotes = []
        if lb.get("quote"):
            quotes.append({"article": lb.get("article", ""),
                           "quote": lb["quote"],
                           "kind": "主要依据"})
        for sq in lb.get("supporting_quotes") or []:
            if sq.get("quote"):
                quotes.append({"article": sq.get("article", ""),
                               "quote": sq["quote"],
                               "kind": "附加依据"})
        rules_meta[r["rule_id"]] = {
            "title": r.get("title", ""),
            "article": r.get("article", ""),
            "strength": r.get("strength", ""),
            "layer": r.get("layer", ""),
            "quote": lb.get("quote", ""),      # 兼容旧字段
            "quotes": quotes,                  # ★ 含 supporting_quotes
            "not_applicable": r.get("not_applicable") or [],
        }

    # 逐个跑引擎
    out_cases = []
    for c in cases:
        res = eng.evaluate(c["input"], c["case_id"])
        # 未触发/未判定规则的标题也从元数据补上（页面用）
        out_cases.append({
            "id": c["case_id"],
            "type": c["type"],
            "desc": c["desc"],
            "short": short_title(c),
            "input": c["input"],
            "expect_note": c["expect"]["note"],
            "result": res,
        })

    doc = {
        "meta": {
            "rules_version": str(data["meta"].get("version", "")),
            "engine_version": "0.1",
            "generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "case_count": len(out_cases),
            "law": data["meta"].get("law", ""),
        },
        "rules": rules_meta,
        "cases": out_cases,
    }

    payload = json.dumps(doc, ensure_ascii=False, indent=None, separators=(",", ":"))
    # 防止数据里出现 </script> 提前闭合
    payload = payload.replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")

    tpl = open(TEMPLATE, encoding="utf-8").read()
    if "__DATA__" not in tpl:
        raise SystemExit("模板缺少 __DATA__ 占位符")
    html = tpl.replace("__DATA__", payload)

    open(OUT, "w", encoding="utf-8").write(html)

    print("generated:", OUT)
    print("  cases : %d" % len(out_cases))
    print("  rules : %d" % len(rules_meta))
    print("  size  : %.1f KB" % (os.path.getsize(OUT) / 1024))
    print("  打开方式: 双击 demo.html")


if __name__ == "__main__":
    main()
