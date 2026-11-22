# -*- coding: utf-8 -*-
"""一条命令跑完全部校验

用法:
  python validate.py                    # 跑全部
  python validate.py --only 引文,yaml_audit
  python validate.py --skip yaml_audit
  python validate.py -v                 # 打印细节

退出码：0 = 全过；1 = 有失败

九项检查：
  1 规则集结构      YAML 可解析 / 必填字段 / rule_id 唯一 / 枚举合法 / 三态契约
  2 引文校验        每条 quote 须为法条原文子串（B 级归一化）+ 归一化模块自测
  3 yaml_audit      外部工具（三法盲评发布包）
                    · 工具/docx 缺失       → SKIP（换机器仍能跑其余项）
                    · 返回码非 0 或 errors>0 → FAIL
  4 表 vs YAML      Excel 核对表与 YAML 的规则集合、触发/履行/quote/类型全部一致
  5 md vs yaml      .md（质检用）与 .yaml（引擎用）的规则内容逐条完全一致
  6 GoldenCases     全部用例的实际输出 vs 期望（按 action_id 断言）
  7 边界行为        三值逻辑 / 字段推导 / 去重 / 但书 / 分层告知
  8 演示页          demo.html 结构 + 内嵌数据与现跑引擎逐字段一致 + 原因追踪完整
  9 渲染            node + 最小 DOM 桩真跑一遍 buildNav/showCase（无浏览器）
                    · node 缺失 → SKIP
 10 覆盖度与分支    判「合规」者必须完整判定（陷阱1）；每个 action 至少被走到一次（陷阱5）

外部依赖路径可用环境变量覆盖：
  COMPLIANCE_AUDIT_TOOL   yaml_audit.py 路径
  COMPLIANCE_LAW_DOCX     官方个保法 docx 路径
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import yaml  # noqa: E402

import quote_check as qc  # noqa: E402
from engine import Engine, load_engine  # noqa: E402
from run_cases import check as check_case, load_cases  # noqa: E402

# ---------------------------------------------------------------- 路径配置 ---
# 规则核对表可能有三个位置，按顺序回落：
#   1) 环境变量 COMPLIANCE_XLSX 指定的路径
#   2) 仓库根（公开克隆后的常态）
#   3) 上一级目录（本地开发时的原布局）
_XLSX_NAME = "个保法规则核对_个人单独同意_v2.5.xlsx"
BASE = os.path.dirname(HERE)
XLSX_PATH = os.environ.get("COMPLIANCE_XLSX") or ""
if not XLSX_PATH:
    for _cand in (os.path.join(HERE, _XLSX_NAME), os.path.join(BASE, _XLSX_NAME)):
        if os.path.exists(_cand):
            XLSX_PATH = _cand
            break
    else:
        XLSX_PATH = os.path.join(HERE, _XLSX_NAME)

YAML_PATH = os.path.join(HERE, "rules", "pipl-separate-consent_v2.5.yaml")
MD_PATH = os.path.join(HERE, "rules", "pipl-separate-consent_v2.5.md")
LAW_PATH = os.path.join(HERE, "data", "laws", "个人信息保护法.md")
CASES_PATH = os.path.join(HERE, "cases", "golden_cases_v1.1.json")
REPORT_PATH = os.path.join(HERE, "_validate_all_report.txt")

# 外部依赖默认留空：未设置环境变量时，对应检查项 SKIP（不计 FAIL）。
#   COMPLIANCE_AUDIT_TOOL  外部 yaml_audit.py（第三方法条质量体检工具）
#   COMPLIANCE_LAW_DOCX    官方个保法 docx（用于引文逐字交叉核对）
# 因此全新克隆下默认输出为 OK 90 / SKIP 1；配齐两个环境变量后为 OK 92 / SKIP 0。
AUDIT_TOOL = os.environ.get("COMPLIANCE_AUDIT_TOOL", "")
LAW_DOCX = os.environ.get("COMPLIANCE_LAW_DOCX", "")

REQUIRED = ["rule_id", "title", "law", "article", "rule_type", "description",
            "condition", "action", "legal_basis", "verification"]
ALLOWED_RULE_TYPES = {"definition", "condition", "obligation", "exception",
                      "procedure", "penalty"}
ALLOWED_ACTION_TYPES = {"obligation", "permission", "prohibition"}
ALLOWED_OPS = {"equals", "not_equals", "in", "gte", "lte", "exists", "not_exists"}
COND_MODES = ("all", "any", "none")


class Ctx:
    def __init__(self):
        self.lines: list[str] = []
        self.fail = 0
        self.skip = 0
        self.verbose = False

    @property
    def mark(self) -> int:
        """用于「本段是否出过错」的基线"""
        return self.fail

    def ok(self, name, detail=""):
        self.lines.append("  OK    %s %s" % (name, detail))

    def bad(self, name, detail=""):
        self.fail += 1
        self.lines.append("  FAIL  %s %s" % (name, detail))

    def sk(self, name, detail=""):
        self.skip += 1
        self.lines.append("  SKIP  %s %s" % (name, detail))

    def info(self, text):
        if self.verbose:
            self.lines.append("        " + text)

    def head(self, idx, title):
        self.lines.append("")
        self.lines.append("=" * 72)
        self.lines.append("[%d] %s" % (idx, title))
        self.lines.append("=" * 72)


def load_data():
    with open(YAML_PATH, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


# ============================================================== 1 规则集结构 ===
def check_structure(ctx: Ctx, data: dict):
    ctx.head(1, "规则集结构")

    rules = data.get("rules") or []
    if len(rules) == 8:
        ctx.ok("规则数", "8 条")
    else:
        ctx.bad("规则数", "期望 8 / 实际 %d" % len(rules))

    ids = [r.get("rule_id") for r in rules]
    if len(ids) == len(set(ids)):
        ctx.ok("rule_id 唯一")
    else:
        dup = sorted({i for i in ids if ids.count(i) > 1})
        ctx.bad("rule_id 唯一", "重复: %s" % dup)

    # ---- 逐条字段/枚举/operator，全部过了才给一个总结 OK ----
    base = ctx.mark
    for r in rules:
        rid = r.get("rule_id", "?")
        miss = [k for k in REQUIRED if not r.get(k)]
        if miss:
            ctx.bad("%s 必填字段" % rid, "缺: %s" % miss)
        if r.get("rule_type") not in ALLOWED_RULE_TYPES:
            ctx.bad("%s rule_type 非法" % rid, str(r.get("rule_type")))
        bad_act = [a.get("type") for a in r.get("action", [])
                   if a.get("type") not in ALLOWED_ACTION_TYPES]
        if bad_act:
            ctx.bad("%s action.type 非法" % rid, str(bad_act))
        cond = r.get("condition") or {}
        for mode in COND_MODES:
            for c in cond.get(mode) or []:
                if c.get("operator") not in ALLOWED_OPS:
                    ctx.bad("%s condition.%s operator 非法" % (rid, mode), str(c))
        for a in r.get("action", []):
            sub = a.get("condition")
            if isinstance(sub, dict) and sub.get("operator") not in ALLOWED_OPS:
                ctx.bad("%s action.condition operator 非法" % rid, str(sub))
    if ctx.fail == base:
        ctx.ok("必填字段与枚举合法", "共 %d 条规则" % len(rules))

    # ---- 三态契约 ----
    base = ctx.mark
    states = data.get("output_states") or {}
    for k in ("not_applicable", "evaluated", "uncovered"):
        if k not in states:
            ctx.bad("三态契约", "缺 %s" % k)
    if ctx.fail == base:
        ctx.ok("三态契约齐全")


# ============================================================== 2 引文校验 ===
def check_quotes(ctx: Ctx, data: dict):
    ctx.head(2, "引文校验（B 级归一化：去空白 + 全半角标点统一）")
    arts = qc.load_articles(LAW_PATH)
    if not arts:
        ctx.bad("法条库加载", LAW_PATH)
        return
    ctx.ok("法条库加载", "%d 条" % len(arts))

    n_checked = 0
    base = ctx.mark
    for r in data["rules"]:
        rid = r["rule_id"]
        lb = r.get("legal_basis") or {}
        art = lb.get("article")
        if art not in arts:
            ctx.bad("%s legal_basis.article" % rid, "法条库无 %s" % art)
            continue
        n_checked += 1
        if qc.contains(lb.get("quote", ""), arts[art]):
            ctx.ok("%s -> %s" % (rid, art))
        else:
            ctx.bad("%s -> %s quote 不匹配" % (rid, art),
                    qc.first_mismatch(lb.get("quote", ""), arts[art]))

        for sq in lb.get("supporting_quotes") or []:
            sa = sq.get("article")
            if sa not in arts:
                ctx.bad("%s supporting_quotes" % rid, "法条库无 %s" % sa)
                continue
            n_checked += 1
            if qc.contains(sq.get("quote", ""), arts[sa]):
                ctx.ok("%s -> %s（附加）" % (rid, sa))
            else:
                ctx.bad("%s -> %s（附加）不匹配" % (rid, sa))

    # 归一化模块自测
    art25 = arts.get("第二十五条", "")
    art23 = arts.get("第二十三条", "")
    probes = [
        ("原文原样通过", art25, art25, True),
        ("半角标点容忍",
         "个人信息处理者不得公开其处理的个人信息,取得个人单独同意的除外.", art25, True),
        ("多余空格容忍",
         "个人信息处理者 不得公开 其处理的个人信息，取得个人单独同意的除外。", art25, True),
        ("用字差异（其它）不放过", "向其它个人信息处理者提供", art23, False),
        ("改字（过的）不放过",
         "个人信息处理者不得公开其处理过的个人信息，取得个人单独同意的除外。", art25, False),
    ]
    for name, probe, art, want in probes:
        got = qc.contains(probe, art)
        if got == want:
            ctx.ok("归一化自测：" + name)
        else:
            ctx.bad("归一化自测：" + name, "期望 %s / 实际 %s" % (want, got))

    if ctx.fail == base:
        ctx.ok("引文全部通过", "共校验 %d 处引用" % n_checked)


# ============================================================== 3 yaml_audit ===
def check_yaml_audit(ctx: Ctx):
    ctx.head(3, "yaml_audit.py（外部工具，三法盲评发布包）")
    if not os.path.exists(AUDIT_TOOL):
        ctx.sk("yaml_audit", "工具不存在（可用 COMPLIANCE_AUDIT_TOOL 覆盖）")
        return
    if not os.path.exists(LAW_DOCX):
        ctx.sk("yaml_audit", "法条 docx 不存在（可用 COMPLIANCE_LAW_DOCX 覆盖）")
        return

    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    cmd = [sys.executable, AUDIT_TOOL, MD_PATH, "--law-text", LAW_DOCX]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", env=env, timeout=120)
    except Exception as e:
        ctx.bad("yaml_audit 执行", str(e))
        return

    out = (p.stdout or "") + (p.stderr or "")
    if ctx.verbose:
        for ln in out.splitlines():
            ctx.info(ln)

    if p.returncode != 0:
        ctx.bad("yaml_audit 返回码", "rc=%s 输出: %s" % (p.returncode, out.strip()[:200]))
        return
    ctx.ok("yaml_audit 返回码 0")

    line = ""
    for ln in out.splitlines():
        if "errors:" in ln:
            line = ln.strip()
    if not line:
        ctx.bad("yaml_audit 输出解析", out.strip()[:200])
        return

    m = re.search(r"errors:\s*(\d+)\s+warnings:\s*(\d+)", line)
    if not m:
        ctx.bad("yaml_audit 结果解析", line)
        return
    err, warn = int(m.group(1)), int(m.group(2))
    if err == 0 and warn == 0:
        ctx.ok("yaml_audit 零问题", line)
    elif err == 0:
        ctx.ok("yaml_audit 无错误（%d 条警告）" % warn, line)
    else:
        ctx.bad("yaml_audit", "%d 个错误" % err)


# ============================================================== 4 表 vs YAML ===
def check_xlsx(ctx: Ctx, data: dict):
    ctx.head(4, "Excel 规则核对表 vs YAML 一致性")
    if not os.path.exists(XLSX_PATH):
        ctx.sk("表对照", "Excel 不存在: %s" % os.path.basename(XLSX_PATH))
        return
    try:
        import openpyxl
    except ImportError:
        ctx.sk("表对照", "openpyxl 未安装")
        return

    wb = openpyxl.load_workbook(XLSX_PATH, data_only=True)
    ws = wb["规则核对表"]
    idx = {h: i for i, h in enumerate([c.value for c in ws[1]])}

    need = ["规则ID", "rule_type", "action.type",
            "触发字段（← YAML condition）", "履行字段（← YAML action.options）",
            "官方quote（← YAML legal_basis.quote）"]
    lack = [k for k in need if k not in idx]
    if lack:
        ctx.sk("表对照", "表头缺列 %s（v2.4 之前的版本？）" % lack)
        return

    rules = {r["rule_id"]: r for r in data["rules"]}

    # ---- 先比 ID 集合，防止多行/漏行 ----
    xlsx_ids = set()
    rows = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        rid = row[idx["规则ID"]]
        if rid:
            xlsx_ids.add(str(rid).strip())
            rows.append(row)
    yaml_ids = set(rules)
    if xlsx_ids == yaml_ids:
        ctx.ok("规则 ID 集合一致", "%d 条" % len(yaml_ids))
    else:
        ctx.bad("规则 ID 集合不一致",
                "仅表有=%s 仅YAML有=%s" % (sorted(xlsx_ids - yaml_ids),
                                          sorted(yaml_ids - xlsx_ids)))

    # ---- 逐行比对 ----
    for row in rows:
        rid = str(row[idx["规则ID"]]).strip()
        if rid not in rules:
            continue                      # 上面 ID 集合检查已报过
        r = rules[rid]

        y_cond = {c["field"]: c.get("value")
                  for c in r["condition"].get("all", [])}
        y_ful = {o["field"] for a in r.get("action", [])
                 for o in a.get("options", [])}
        y_at = {a.get("type") for a in r.get("action", [])}

        try:
            x_cond = json.loads(row[idx["触发字段（← YAML condition）"]])
            x_ful = set(json.loads(row[idx["履行字段（← YAML action.options）"]]))
        except Exception as e:
            ctx.bad("%s 表内 JSON" % rid, str(e))
            continue
        x_rt = str(row[idx["rule_type"]] or "").strip()
        x_at = {s for s in str(row[idx["action.type"]] or "").replace(" ", "").split("、") if s}
        x_quote = str(row[idx["官方quote（← YAML legal_basis.quote）"]] or "").strip()

        problems = []
        if y_cond != x_cond:
            problems.append("触发字段 表=%s Y=%s" % (x_cond, y_cond))
        if y_ful != x_ful:
            problems.append("履行字段 差异=%s" % (x_ful ^ y_ful))
        if x_rt != r.get("rule_type"):
            problems.append("rule_type 表=%s Y=%s" % (x_rt, r.get("rule_type")))
        if x_at != y_at:
            problems.append("action.type 表=%s Y=%s" % (sorted(x_at), sorted(y_at)))
        if x_quote != r["legal_basis"]["quote"].strip():
            problems.append("quote 不一致")

        if problems:
            ctx.bad("%s" % rid, "；".join(problems))
        else:
            ctx.ok("%s 五列一致" % rid)


# ============================================================ 5 md vs yaml ===
def check_md_yaml_sync(ctx: Ctx, data: dict):
    ctx.head(5, ".md（质检用）vs .yaml（引擎用）规则内容一致性")
    if not os.path.exists(MD_PATH):
        ctx.sk("md 同步", "文件不存在: %s" % os.path.basename(MD_PATH))
        return
    text = open(MD_PATH, encoding="utf-8").read()
    blocks = re.findall(r"```ya?ml\s*\n(.*?)```", text, re.S | re.I)
    if not blocks:
        ctx.bad("md 同步", "未找到 yaml 代码块")
        return

    md_rules, base = {}, ctx.mark
    for i, b in enumerate(blocks, 1):
        try:
            d = yaml.safe_load(b)
        except Exception as e:
            ctx.bad("第 %d 个 yaml 块解析" % i, str(e))
            continue
        if isinstance(d, dict) and d.get("rule_id"):
            md_rules[d["rule_id"]] = d

    yaml_rules = {r["rule_id"]: r for r in data["rules"]}
    if set(md_rules) == set(yaml_rules):
        ctx.ok("规则 ID 集合一致", "%d 条" % len(md_rules))
    else:
        ctx.bad("规则 ID 集合不一致",
                "仅md=%s 仅yaml=%s" % (sorted(set(md_rules) - set(yaml_rules)),
                                      sorted(set(yaml_rules) - set(md_rules))))

    for rid in sorted(set(md_rules) & set(yaml_rules)):
        a, b = md_rules[rid], yaml_rules[rid]
        if a == b:
            ctx.ok("%s 内容一致" % rid)
        else:
            diff = sorted({k for k in set(a) | set(b) if a.get(k) != b.get(k)})
            ctx.bad("%s 内容不一致" % rid, "差异字段: %s" % diff)


# ============================================================ 6 GoldenCases ===
def check_cases(ctx: Ctx, eng):
    doc = load_cases()
    total = len(doc["cases"])
    ctx.head(6, "GoldenCases（%d 个用例）" % total)
    n_ok = 0
    for c in doc["cases"]:
        res = eng.evaluate(c["input"], case_id=c["case_id"])
        probs = check_case(res, c["expect"])
        if probs:
            ctx.bad(c["case_id"], "; ".join(probs))
        else:
            n_ok += 1
            ctx.ok(c["case_id"], "%s / %s（规则 %d，缺失 %d）" % (
                res["state"], res["verdict"], len(res["triggered_rules"]),
                len(res["missing_materials"])))
    if n_ok == total:
        ctx.ok("全部用例通过", "%d/%d" % (n_ok, total))


# ============================================================== 7 边界行为 ===
def check_behavior(ctx: Ctx, eng):
    ctx.head(7, "边界行为")
    doc = load_cases()
    cases = {c["case_id"]: c for c in doc["cases"]}

    r = eng.evaluate({}, "EMPTY")
    (ctx.ok if r["state"] == "uncovered" else ctx.bad)("空输入 -> uncovered", r["state"])

    r = eng.evaluate({"存在个人信息处理行为": False}, "NA")
    (ctx.ok if r["state"] == "not_applicable" else ctx.bad)(
        "处理行为=false -> not_applicable", r["state"])

    r = eng.evaluate({"存在个人信息处理行为": True}, "BARE")
    if r["state"] == "evaluated" and r["triggered_rules"] == ["PIPL-13-01"]:
        ctx.ok("仅处理行为=true -> 只触发基线")
    else:
        ctx.bad("仅处理行为=true", str(r["triggered_rules"]))

    if eng.evaluate({}, "X")["verdict"] == "合规":
        ctx.bad("空输入不得判合规")
    else:
        ctx.ok("空输入不判合规")

    # 字段推导
    r = eng.evaluate({"存在个人信息处理行为": True, "公开其处理的个人信息": True,
                      "已取得单独同意": True, "已取得个人同意": False}, "DERIVE")
    lb = [a for pr in r["obligations"] if pr["rule_id"] == "PIPL-13-01"
          for a in pr["actions"] if a["action_id"] == "legal_basis"]
    if lb and lb[0]["status"] == "met":
        ctx.ok("单独同意=true 推导出一般同意")
    else:
        ctx.bad("字段推导", lb[0]["status"] if lb else "无 legal_basis")
    if any("字段推导" in n for n in r["notes"]):
        ctx.ok("推导过程写入 notes")
    else:
        ctx.bad("推导过程未记录")

    r = eng.evaluate({"存在个人信息处理行为": True, "公开其处理的个人信息": True,
                      "已取得个人同意": True, "已取得单独同意": False}, "REV")
    (ctx.ok if r["verdict"] == "不合规" else ctx.bad)(
        "一般同意推不出单独同意", r["verdict"])

    # 去重：从用例里读期望值，不写死
    s10 = cases["S10"]
    r = eng.evaluate(s10["input"], "S10")
    hits = [m for m in r["missing_materials"] if "单独同意" in m]
    want = 1
    (ctx.ok if len(hits) == want else ctx.bad)(
        "单独同意去重为 %d 项" % want, str(hits))

    # 但书
    r = eng.evaluate(cases["S6"]["input"], "S6")
    if r["verdict"] == "合规" and any("但书" in n for n in r["notes"]):
        ctx.ok("但书成立时规则仍输出")
    else:
        ctx.bad("但书标注", r["verdict"])

    # 分层告知：从用例的 missing_count 读，不写死
    s4 = cases["S4"]
    r = eng.evaluate(s4["input"], "S4")
    want = s4["expect"]["missing_count"]
    (ctx.ok if len(r["missing_materials"]) == want else ctx.bad)(
        "告知按维度分层（S4 共 %d 项）" % want, "实际 %d" % len(r["missing_materials"]))


# ============================================================== 8 演示页 ===
def check_demo_page(ctx: Ctx):
    ctx.head(8, "演示页 demo.html（静态页与引擎是否一致）")
    try:
        from check_demo import run as run_demo_check
    except Exception as e:
        ctx.sk("演示页", "导入 check_demo 失败: %s" % e)
        return

    fails, lines = run_demo_check()
    for ln in lines:
        s = ln.strip()
        if not s or s.startswith("="):
            continue
        if s.startswith("demo.html") or s.startswith("总结"):
            continue
        if s.startswith("OK"):
            ctx.lines.append("  OK    " + s[2:].strip())
        elif s.startswith("FAIL"):
            ctx.bad(*([s[4:].strip()] + [""]))
        elif s.startswith("        "):
            ctx.info(s.strip())


# ========================================================== 9 演示页渲染 ===
def check_demo_render(ctx: Ctx):
    ctx.head(9, "演示页渲染（node + 最小 DOM 桩，无浏览器）")
    node = shutil.which("node")
    if not node:
        ctx.sk("渲染冒烟", "未找到 node，跳过（不影响其余检查）")
        return
    script = os.path.join(HERE, "test_demo_render.js")
    if not os.path.exists(script):
        ctx.sk("渲染冒烟", "缺少 test_demo_render.js")
        return

    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    try:
        p = subprocess.run([node, script], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", env=env,
                           cwd=HERE, timeout=120)
    except Exception as e:
        ctx.bad("渲染冒烟执行", str(e))
        return

    report = os.path.join(HERE, "_demo_render_report.txt")
    lines = []
    if os.path.exists(report):
        lines = open(report, encoding="utf-8").read().splitlines()

    if p.returncode != 0:
        ctx.bad("渲染冒烟", "返回码 %s" % p.returncode)
        for ln in lines:
            ctx.info(ln)
        return

    ctx.ok("node 渲染冒烟通过", "退出码 0")
    for ln in lines:
        s = ln.strip()
        if s.startswith("渲染成功") or s.startswith("全部场景"):
            ctx.ok(s)
        elif s.startswith("-"):
            ctx.bad("渲染问题", s)


# ====================================================== 10 覆盖度与分支 ===
def check_coverage(ctx: Ctx, eng):
    """对应《规则集自检_七类陷阱》的陷阱 1（覆盖度假象）与陷阱 5（分支盲区）

    陷阱 1：判定「合规」但大量规则因字段缺失未判定 → 假阴性
    陷阱 5：某个 rule×action 分支从未被任何案例触发过 → 死代码风险
    """
    ctx.head(10, "覆盖度与分支覆盖（陷阱 1 / 陷阱 5）")
    doc = load_cases()

    # ---- 陷阱 1：合规必须建立在完整判定之上 ----
    incomplete = []
    for c in doc["cases"]:
        r = eng.evaluate(c["input"], c["case_id"])
        cov = r.get("coverage") or {}
        if r["verdict"] == "合规" and not cov.get("complete"):
            incomplete.append("%s: 判合规但只判定 %s/%s"
                              % (c["case_id"], cov.get("decided"), cov.get("total")))
    (ctx.ok if not incomplete else ctx.bad)(
        "判合规者必须完整判定", "；".join(incomplete[:4]))

    # ---- 陷阱 5：每个 rule×action 都要至少被走到一次 ----
    met, unmet, skipped = set(), set(), set()
    for c in doc["cases"]:
        r = eng.evaluate(c["input"], c["case_id"])
        for pr in r.get("obligations") or []:
            for a in pr["actions"]:
                key = "%s:%s" % (pr["rule_id"], a["action_id"])
                if a["status"] == "met":
                    met.add(key)
                elif a["status"] == "unmet":
                    unmet.add(key)
                elif a["status"] in ("not_required", "subsumed"):
                    skipped.add(key)

    all_actions = set()
    for r in eng.rules:
        for a in r.get("action", []):
            all_actions.add("%s:%s" % (r["rule_id"], a.get("id")))

    never = sorted(all_actions - met - unmet)
    (ctx.ok if not never else ctx.bad)(
        "全部分支至少被走到一次", "；".join(never) if never else "%d 个 action" % len(all_actions))

    # 条件分支：从未被要求、也从未被判不满足 → 可能未真正生效
    dead = sorted(k for k in all_actions
                  if k in skipped and k not in met and k not in unmet)
    (ctx.ok if not dead else ctx.bad)("条件分支均有效", "；".join(dead))

    ctx.ok("状态统计", "满足 %d / 未满足 %d / 条件未成立 %d"
           % (len(met), len(unmet), len(skipped)))


# ==================================================================== 主入口 ===
ALL_CHECKS = ["结构", "引文", "yaml_audit", "表对照", "md同步", "用例", "边界",
              "演示页", "渲染", "覆盖度"]


def main():
    try:
        sys.stdout.reconfigure(errors="replace")
    except Exception:
        pass

    ap = argparse.ArgumentParser(description="合规规则引擎 v0.1 全量校验")
    ap.add_argument("--only", default="", help="只跑指定项，逗号分隔")
    ap.add_argument("--skip", default="", help="跳过指定项，逗号分隔")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    only = {x.strip() for x in args.only.split(",") if x.strip()}
    skip = {x.strip() for x in args.skip.split(",") if x.strip()}
    bad_names = (only | skip) - set(ALL_CHECKS)
    if bad_names:
        print("未知检查项: %s（可选: %s）" % (sorted(bad_names), "、".join(ALL_CHECKS)))
        return 2
    names = [n for n in ALL_CHECKS if (not only or n in only) and n not in skip]

    ctx = Ctx()
    ctx.verbose = args.verbose

    doc = load_cases()
    ctx.lines.append("合规规则引擎 v0.1 · 全量校验")
    ctx.lines.append("规则集: rules/pipl-separate-consent_v2.5.yaml")
    ctx.lines.append("用例:   cases/golden_cases_v1.1.json（%d 个）" % len(doc["cases"]))

    data = load_data()
    eng = load_engine()

    for name in names:
        if name == "用例":
            check_cases(ctx, eng)
        elif name == "边界":
            check_behavior(ctx, eng)
        elif name == "结构":
            check_structure(ctx, data)
        elif name == "引文":
            check_quotes(ctx, data)
        elif name == "yaml_audit":
            check_yaml_audit(ctx)
        elif name == "表对照":
            check_xlsx(ctx, data)
        elif name == "md同步":
            check_md_yaml_sync(ctx, data)
        elif name == "演示页":
            check_demo_page(ctx)
        elif name == "渲染":
            check_demo_render(ctx)
        elif name == "覆盖度":
            check_coverage(ctx, eng)

    ok_cnt = len([l for l in ctx.lines if l.strip().startswith("OK")])
    ctx.lines.append("")
    ctx.lines.append("=" * 72)
    ctx.lines.append("总结：OK %d / FAIL %d / SKIP %d" % (ok_cnt, ctx.fail, ctx.skip))
    ctx.lines.append("结论：%s" % ("全部通过" if ctx.fail == 0 else "存在问题"))
    ctx.lines.append("")
    ctx.lines.append("说明：本校验只证明「内部一致性」，不证明「法律正确性」。")
    ctx.lines.append("      GoldenCases 与规则集共享同一套假设，可能同错；")
    ctx.lines.append("      yaml_audit 只查结构和 quote，不查法律语义。")

    text = "\n".join(ctx.lines)
    open(REPORT_PATH, "w", encoding="utf-8").write(text)
    print(text)
    print()
    print("报告 -> %s" % REPORT_PATH)
    return 0 if ctx.fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
