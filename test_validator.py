# -*- coding: utf-8 -*-
"""validate.py 自身的负向测试：故意破坏数据，验证每个检查项真的能抓到问题

用法: python test_validator.py
输出: test_validator_report.txt，每行 PASS 表示该检查项确实抓到了问题

为什么需要它：
  一个「全部通过」的校验器，可能是真的没问题，也可能是**检查根本不生效**。
  本脚本对每个检查项构造一个确定性破坏，要求它必须 FAIL。
"""
import copy
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import yaml

import validate as V
from engine import load_engine

results = []


def run(label, fn):
    ctx = V.Ctx()
    fn(ctx)
    msgs = [l.strip() for l in ctx.lines if l.strip().startswith(("OK", "FAIL", "SKIP"))]
    caught = ctx.fail > 0
    results.append((label, caught, ctx.fail, msgs))


HAS_XLSX = os.path.exists(V.XLSX_PATH)
if not HAS_XLSX:
    print("提示: 未找到 Excel 核对表，跳过「表对照」相关负向测试")
data0 = V.load_data()

# ---------- 场景1：P1-1 必填字段缺失时不应仍报 OK ----------
d = copy.deepcopy(data0)
del d["rules"][0]["description"]
run("P1-1 删掉 description", lambda c: V.check_structure(c, d))

# ---------- 场景2：P1-1 三态契约缺失 ----------
d = copy.deepcopy(data0)
del d["output_states"]["uncovered"]
run("P1-1 删掉 uncovered 态", lambda c: V.check_structure(c, d))

# ---------- 场景3：rule_type 非法 ----------
d = copy.deepcopy(data0)
d["rules"][0]["rule_type"] = "prohibition"      # 不在允许枚举里
run("P1-1 rule_type=prohibition", lambda c: V.check_structure(c, d))

# ---------- 场景4：P1-2 多一条 YAML 没在表里的规则 ----------
d = copy.deepcopy(data0)
extra = copy.deepcopy(d["rules"][1])
extra["rule_id"] = "PIPL-99-99"
d["rules"].append(extra)
if HAS_XLSX:
    run("P1-2 YAML 多一条表里没有的规则", lambda c: V.check_xlsx(c, d))

# ---------- 场景5：P1-3 改 rule_type 但不改字段 ----------
d = copy.deepcopy(data0)
d["rules"][4]["rule_type"] = "exception"        # 25-01 从 obligation 改掉
if HAS_XLSX:
    run("P1-3 rule_type 与表不一致", lambda c: V.check_xlsx(c, d))

# ---------- 场景6：P1-3 改 action.type ----------
d = copy.deepcopy(data0)
d["rules"][4]["action"][0]["type"] = "permission"   # 25-01 的 prohibition 改掉
if HAS_XLSX:
    run("P1-3 action.type 与表不一致", lambda c: V.check_xlsx(c, d))

# ---------- 场景7：P2-1 .yaml 改了但 .md 没改 ----------
tmpdir = os.path.join(HERE, "_neg_tmp")
os.makedirs(tmpdir, exist_ok=True)
tmp_md = os.path.join(tmpdir, "rules.md")
shutil.copy(V.MD_PATH, tmp_md)
old_md_path = V.MD_PATH
V.MD_PATH = tmp_md
# 把 md 里某条规则改坏
txt = open(tmp_md, encoding="utf-8").read()
txt = txt.replace("title: 处理个人信息的合法性基础与基本告知",
                  "title: 处理个人信息的合法性基础（被篡改）", 1)
open(tmp_md, "w", encoding="utf-8").write(txt)
run("P2-1 md 内容与 yaml 不一致", lambda c: V.check_md_yaml_sync(c, data0))
V.MD_PATH = old_md_path

# ---------- 场景8：md 少一条规则 ----------
shutil.copy(V.MD_PATH, tmp_md)
txt = open(tmp_md, encoding="utf-8").read()
blocks = txt.split("```yaml")
if len(blocks) > 2:
    txt = "```yaml".join(blocks[:-1])     # 砍掉最后一个 yaml 块
open(tmp_md, "w", encoding="utf-8").write(txt)
V.MD_PATH = tmp_md
run("P2-1 md 少一条规则", lambda c: V.check_md_yaml_sync(c, data0))
V.MD_PATH = old_md_path

# ---------- 场景9：引文改字 ----------
d = copy.deepcopy(data0)
d["rules"][4]["legal_basis"]["quote"] = d["rules"][4]["legal_basis"]["quote"].replace("公开", "公布")
run("引文改字（公开->公布）", lambda c: V.check_quotes(c, d))

# ---------- 场景10：正常数据应当全过 ----------
def _ctrl(c):
    V.check_structure(c, data0)
    if HAS_XLSX:
        V.check_xlsx(c, data0)
    V.check_md_yaml_sync(c, data0)


run("对照组：原始数据", _ctrl)

# ---------- 输出 ----------
lines = []
for label, caught, nfail, msgs in results:
    expect_catch = not label.startswith("对照组")
    good = (caught == expect_catch)
    lines.append("%s %-38s FAIL=%d" % ("PASS" if good else "BUG!", label, nfail))
    for m in msgs:
        if m.startswith("FAIL"):
            lines.append("        " + m)
lines.append("")
lines.append("说明：对照组应 FAIL=0；其余场景必须 FAIL>0（否则校验器抓不到问题）")

shutil.rmtree(tmpdir, ignore_errors=True)
text = "\n".join(lines)
open(os.path.join(HERE, "test_validator_report.txt"), "w", encoding="utf-8").write(text)

# 同时打到控制台（Windows 控制台可能是 GBK，不能编码的字符降级为 ?）
try:
    sys.stdout.reconfigure(errors="replace")
except Exception:
    pass
print(text)
print()
print("report -> test_validator_report.txt")

sys.exit(0 if all(caught == (not lab.startswith("对照组")) for lab, caught, _, _ in results) else 1)
