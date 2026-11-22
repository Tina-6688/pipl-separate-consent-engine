# -*- coding: utf-8 -*-
"""跑 golden cases（按 action_id 断言版本）

用法:
  python run_cases.py              # 跑全部，输出报告
  python run_cases.py S4           # 只跑某个 case，打印详细结果
"""
import json
import os
import sys

from engine import Engine, load_engine

HERE = os.path.dirname(os.path.abspath(__file__))
CASES = os.path.join(HERE, "cases", "golden_cases_v1.1.json")
OUT = os.path.join(HERE, "_cases_report.txt")


def load_cases():
    with open(CASES, encoding="utf-8") as fh:
        return json.load(fh)


def check(res: dict, exp: dict):
    """返回问题列表；空表示通过"""
    problems = []

    if res["state"] != exp["state"]:
        problems.append("state: 期望 %s / 实际 %s" % (exp["state"], res["state"]))

    if exp["state"] == "evaluated":
        act = set(res["triggered_rules"])
        want = set(exp["triggered"])
        if act != want:
            if want - act:
                problems.append("少触发: %s" % sorted(want - act))
            if act - want:
                problems.append("多触发: %s" % sorted(act - want))

        unmet_actual = {"%s:%s" % (pr["rule_id"], a["action_id"])
                        for pr in res.get("obligations", [])
                        for a in pr["actions"] if a["status"] == "unmet"}
        want_unmet = set(exp["unmet"])
        if unmet_actual != want_unmet:
            if want_unmet - unmet_actual:
                problems.append("应缺失但实际已满足: %s" % sorted(want_unmet - unmet_actual))
            if unmet_actual - want_unmet:
                problems.append("意外缺失: %s" % sorted(unmet_actual - want_unmet))

        if len(res["missing_materials"]) != exp["missing_count"]:
            problems.append("缺失项数量: 期望 %d / 实际 %d -> %s"
                            % (exp["missing_count"], len(res["missing_materials"]),
                               res["missing_materials"]))

    if res["verdict"] != exp["verdict"]:
        problems.append("verdict: 期望 %s / 实际 %s" % (exp["verdict"], res["verdict"]))

    return problems


def main():
    eng = load_engine()
    doc = load_cases()

    if len(sys.argv) > 1:
        wanted = set(sys.argv[1:])
        for c in doc["cases"]:
            if c["case_id"] in wanted:
                res = eng.evaluate(c["input"], case_id=c["case_id"])
                print(Engine.render(res))
                probs = check(res, c["expect"])
                print()
                print("期望: %s" % c["expect"]["note"])
                print("结果: %s" % ("通过" if not probs else "失败"))
                for p in probs:
                    print("  - " + p)
        return

    lines, details = [], []
    ok_cnt = fail_cnt = 0
    for c in doc["cases"]:
        res = eng.evaluate(c["input"], case_id=c["case_id"])
        probs = check(res, c["expect"])
        if probs:
            fail_cnt += 1
            lines.append("[%s] FAIL  %s / %s" % (c["case_id"], res["state"], res["verdict"]))
            for p in probs:
                lines.append("        - " + p)
        else:
            ok_cnt += 1
            lines.append("[%s] OK    %s / %s（规则 %d，缺失 %d）" % (
                c["case_id"], res["state"], res["verdict"],
                len(res["triggered_rules"]), len(res["missing_materials"])))
        details.append(Engine.render(res))

    total = ok_cnt + fail_cnt
    lines.append("")
    lines.append("=" * 72)
    lines.append("结果：通过 %d / 失败 %d / 共 %d" % (ok_cnt, fail_cnt, total))
    lines.append("规则集: rules/pipl-separate-consent_v2.5.yaml")
    lines.append("用例:   cases/golden_cases_v1.1.json")

    open(OUT, "w", encoding="utf-8").write(
        "\n".join(lines) + "\n\n\n" + "\n\n".join(details))
    print("pass=%d fail=%d total=%d" % (ok_cnt, fail_cnt, total))
    print("report ->", OUT)


if __name__ == "__main__":
    main()
