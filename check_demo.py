# -*- coding: utf-8 -*-
"""demo.html 校验：结构完整性 + 数据与引擎一致（防静态页过期）

可作为模块被 validate.py 调用：
    from check_demo import run as run_demo_check
    fails, lines = run_demo_check()

也可单独运行：
    python check_demo.py
"""
from __future__ import annotations

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

DEMO = os.path.join(HERE, "demo.html")
OUT = os.path.join(HERE, "_demo_check.txt")

VOID = {"meta", "link", "br", "hr", "img", "input", "source", "area",
        "base", "col", "embed", "param", "track", "wbr"}


def run() -> tuple[int, list[str]]:
    """返回 (失败数, 报告行)"""
    lines: list[str] = []
    fails = 0

    def ck(name, cond, detail=""):
        nonlocal fails
        if cond:
            lines.append("  OK    %s %s" % (name, detail))
        else:
            fails += 1
            lines.append("  FAIL  %s %s" % (name, detail))

    lines.append("=" * 66)
    lines.append("demo.html 校验")
    lines.append("=" * 66)

    if not os.path.exists(DEMO):
        ck("文件存在", False, "先跑 python build_demo.py")
        lines.append("")
        lines.append("总结：文件不存在")
        return fails, lines

    html = open(DEMO, encoding="utf-8").read()
    size_kb = os.path.getsize(DEMO) / 1024

    ck("文件存在", True)
    ck("体积合理", 30 < size_kb < 500, "%.1f KB" % size_kb)
    ck("无残留占位符", "__DATA__" not in html)
    ck("声明 UTF-8", 'charset="UTF-8"' in html or "charset=utf-8" in html.lower())
    ck("无外部资源引用", not re.search(r'(?:src|href)="(?:https?:)?//', html),
       "（不依赖 CDN，可离线打开）")

    m = re.search(r"const DATA = (\{.*?\});\s*\n", html, re.S)
    if not m:
        ck("找到 DATA 对象", False)
        lines.append("")
        lines.append("总结：数据结构缺失")
        return fails, lines
    ck("找到 DATA 对象", True)

    raw = m.group(1).replace("\\u003c", "<")
    try:
        doc = json.loads(raw)
        ck("JSON 可解析", True, "cases=%d" % len(doc.get("cases", [])))
    except Exception as e:
        ck("JSON 可解析", False, str(e))
        lines.append("")
        lines.append("总结：JSON 解析失败")
        return fails, lines

    ck("script 标签成对", html.count("<script") == html.count("</script>"))
    ck("style 标签成对", html.count("<style") == html.count("</style>"))

    # 标签闭合
    from html.parser import HTMLParser

    class _Bal(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.stack: list[str] = []
            self.errs: list[str] = []

        def handle_starttag(self, tag, attrs):
            if tag not in VOID:
                self.stack.append(tag)

        def handle_endtag(self, tag):
            if tag in VOID:
                return
            if self.stack and self.stack[-1] == tag:
                self.stack.pop()
            elif tag in self.stack:
                while self.stack and self.stack[-1] != tag:
                    self.errs.append("未闭合 <%s>" % self.stack.pop())
                if self.stack:
                    self.stack.pop()
            else:
                self.errs.append("多余闭合 </%s>" % tag)

    bal = _Bal()
    try:
        bal.feed(html)
        leftover = [t for t in bal.stack if t != "html"]
        ck("HTML 标签闭合", not bal.errs and not leftover,
           "%s %s" % (bal.errs[:3], leftover[:3]))
    except Exception as e:
        ck("HTML 标签闭合", False, str(e))

    # ---------- 与现跑引擎比对 ----------
    from engine import load_engine
    from run_cases import load_cases

    eng = load_engine()
    cases = {c["case_id"]: c for c in load_cases()["cases"]}
    demo_cases = {c["id"]: c for c in doc.get("cases", [])}

    ck("用例数量一致", set(demo_cases) == set(cases),
       "html=%d 期望=%d" % (len(demo_cases), len(cases)))
    ck("规则数量一致", len(doc.get("rules", {})) == len(eng.rules),
       "html=%d 期望=%d" % (len(doc.get("rules", {})), len(eng.rules)))

    drift = []
    for cid, c in cases.items():
        fresh = eng.evaluate(c["input"], cid)
        shown = (demo_cases.get(cid) or {}).get("result") or {}
        if json.dumps(shown, sort_keys=True, ensure_ascii=False) != \
           json.dumps(fresh, sort_keys=True, ensure_ascii=False):
            keys = sorted({k for k in set(shown) | set(fresh)
                           if shown.get(k) != fresh.get(k)})
            drift.append("%s 差异字段: %s" % (cid, keys))
    ck("与现跑引擎结果逐字段一致", not drift, "（不一致 %d 处）" % len(drift))
    for d in drift[:6]:
        lines.append("        " + d)

    # 依据条文是否含 supporting_quotes（PIPL-13-01 应同时带第13条与第17条）
    q_bad = []
    for rid, meta in (doc.get("rules") or {}).items():
        if not meta.get("quotes"):
            q_bad.append("%s 无 quotes" % rid)
    r13 = (doc.get("rules") or {}).get("PIPL-13-01") or {}
    if len(r13.get("quotes") or []) < 2:
        q_bad.append("PIPL-13-01 应含第13条+第17条")
    ck("依据条文含附加引用", not q_bad, "；".join(q_bad[:3]))

    # ---------- 必备字段 ----------
    bad = []
    for cid, c in demo_cases.items():
        for k in ("id", "type", "desc", "short", "input", "expect_note", "result"):
            if k not in c:
                bad.append("%s 缺 %s" % (cid, k))
        r = c.get("result") or {}
        for k in ("state", "verdict", "triggered_rules", "missing_materials",
                  "obligations", "inactive_detail", "notes"):
            if k not in r:
                bad.append("%s.result 缺 %s" % (cid, k))
    ck("case 必备字段齐全", not bad, "；".join(bad[:4]))

    # ---------- 原因追踪 ----------
    no_trace = []
    for cid, c in demo_cases.items():
        r = c.get("result") or {}
        inactive = r.get("inactive_detail") or []
        expect = len(r.get("undetermined_rules") or []) + len(r.get("not_triggered_rules") or [])
        if len(inactive) != expect:
            no_trace.append("%s: 追踪 %d / 应有 %d" % (cid, len(inactive), expect))
    ck("不触发规则带原因追踪", not no_trace, "；".join(no_trace[:3]))

    has_trace = any(
        d.get("condition")
        for c in demo_cases.values()
        for d in ((c.get("result") or {}).get("inactive_detail") or [])
    )
    ck("追踪含具体字段", bool(has_trace))

    # ---------- 关键行为在页面数据里可见 ----------
    s10 = (demo_cases.get("S10") or {}).get("result") or {}
    hits = [x for x in s10.get("missing_materials", []) if "单独同意" in x]
    ck("S10 页面上单独同意只 1 项", len(hits) == 1, str(hits))

    s6 = (demo_cases.get("S6") or {}).get("result") or {}
    ck("S6 显示合规且含但书说明",
       s6.get("verdict") == "合规" and any("但书" in n for n in s6.get("notes", [])))

    lines.append("")
    lines.append("总结：%s（失败 %d）" % ("通过" if fails == 0 else "有问题", fails))
    return fails, lines


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(errors="replace")
    except Exception:
        pass
    f, ls = run()
    open(OUT, "w", encoding="utf-8").write("\n".join(ls))
    print("fails:", f)
    print("report ->", OUT)
