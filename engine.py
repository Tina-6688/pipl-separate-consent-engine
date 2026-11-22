# -*- coding: utf-8 -*-
"""合规规则引擎 v0.1

职责：读取 YAML 规则集 -> 对输入字段求值 -> 输出三态结果
三态契约见 rules/*.yaml 的 output_states：
  not_applicable  明确不适用（存在个人信息处理行为 == false）
  evaluated       至少一条规则触发
  uncovered       无法判定或规则集未覆盖 -> 转人工，禁止默认合规

设计要点：
1. 三值逻辑：条件求值结果只有 True / False / None(未知)，字段缺失 = 未知，不是 False
2. 触发字段与履行字段分离：condition 决定是否适用，action.options 决定是否合规
3. 去重：单独同意优先于一般同意；告知按维度分层去重；接收方义务不合并
"""
from __future__ import annotations

import os
from typing import Any

import yaml

BASELINE_RULE = "PIPL-13-01"
BASELINE_CONSENT_GROUP = "legal_basis"


def _cmp(val: Any, op: str, exp: Any) -> bool:
    if op == "equals":
        return val == exp
    if op == "not_equals":
        return val != exp
    if op == "in":
        return val in (exp or [])
    if op == "gte":
        return val >= exp
    if op == "lte":
        return val <= exp
    if op == "exists":
        return True
    if op == "not_exists":
        return False
    raise ValueError("unsupported operator: %s" % op)


def eval_item(item: dict, fields: dict) -> bool | None:
    """单个条件项：字段缺失返回 None（未知），不当作 False"""
    f = item.get("field")
    if f not in fields:
        return None
    op = item.get("operator", "equals")
    if op == "exists":
        return True
    if op == "not_exists":
        return False
    return _cmp(fields[f], op, item.get("value"))


def eval_group(items: list, mode: str, fields: dict) -> bool | None:
    vals = [eval_item(i, fields) for i in items]
    if mode == "all":
        if any(v is False for v in vals):
            return False
        if any(v is None for v in vals):
            return None
        return True
    if mode == "any":
        if any(v is True for v in vals):
            return True
        if any(v is None for v in vals):
            return None
        return False
    if mode == "none":
        if any(v is True for v in vals):
            return False
        if any(v is None for v in vals):
            return None
        return True
    raise ValueError("unsupported mode: %s" % mode)


def eval_condition(cond: dict, fields: dict) -> bool | None:
    results = []
    for key in ("all", "any", "none"):
        if cond.get(key):
            results.append(eval_group(cond[key], key, fields))
    if not results:
        return True
    if any(r is False for r in results):
        return False
    if any(r is None for r in results):
        return None
    return True


def eval_action(action: dict, fields: dict) -> dict:
    """求值一个 action（履行要求组）"""
    out = {
        "action_id": action.get("id", ""),
        "label": action.get("label", ""),
        "type": action.get("type", "obligation"),
        "status": "met",
        "missing": [],
        "note": "",
    }
    mode = action.get("mode", "all")

    if mode == "conditional_all":
        cond = action.get("condition")
        if cond:
            st = eval_condition({"all": [cond]}, fields)
            if st is not True:
                out["status"] = "not_required"
                return out

    opts = action.get("options", []) or []
    evals = []
    for o in opts:
        f = o.get("field")
        evals.append({
            "field": f,
            "ok": fields.get(f) is True,
            "label": o.get("missing_label", f),
        })

    if mode == "any":
        if any(e["ok"] for e in evals):
            out["status"] = "met"
        else:
            out["status"] = "unmet"
            out["missing"] = [e["label"] for e in evals]
            out["note"] = "任一满足即可"
        return out

    missing = [e["label"] for e in evals if not e["ok"]]
    if missing:
        out["status"] = "unmet"
        out["missing"] = missing
    else:
        out["status"] = "met"
        # 禁止类：但书成立时给出提示
        if out["type"] == "prohibition" and action.get("exception_note"):
            out["note"] = action["exception_note"]
    return out


class Engine:
    def __init__(self, yaml_path: str):
        with open(yaml_path, encoding="utf-8") as fh:
            self.data = yaml.safe_load(fh)
        self.rules = self.data.get("rules", [])
        self.by_id = {r["rule_id"]: r for r in self.rules}
        self.states = self.data.get("output_states", {})

    # ------------------------------------------------------------ 字段隐含推导 ---
    @staticmethod
    def derive(fields: dict) -> tuple[dict, list]:
        """补全可由已给字段推导出的取值，返回 (新字段, 说明列表)

        依据：单独同意的构成要件强于一般同意，
              已取得单独同意 => 视为已满足第 13 条的一般同意（单向蕴含）。
        反向不成立：有一般同意不代表有单独同意（见 S2）。
        """
        f = dict(fields)
        notes = []
        if f.get("已取得单独同意") is True and f.get("已取得个人同意") is not True:
            f["已取得个人同意"] = True
            notes.append(
                "字段推导：已取得单独同意=true → 视为已满足第13条的一般同意"
                "（单独同意在要求上强于一般同意；反向不成立）")
        return f, notes

    # ------------------------------------------------------- 覆盖度计算 ---
    @staticmethod
    def coverage(total: int, decided: int, undetermined: int, note: str = "") -> dict:
        """报告「有多少规则真的给出了结论」

        三值逻辑下，字段缺失会让规则被判为「未知」，若不显式统计，
        用户会以为全部查过了——这是最危险的假阴性。
        """
        cov = {
            "total": total,
            "decided": decided,
            "undetermined": undetermined,
            "complete": undetermined == 0,
        }
        if note:
            cov["note"] = note
        return cov

    @staticmethod
    def qualify(verdict: str, cov: dict) -> str:
        """给出不夸大的判定措辞"""
        if verdict in ("不适用", "未覆盖"):
            return verdict
        if verdict == "不合规":
            return verdict
        if cov.get("complete"):
            return verdict
        return "合规（部分未判定）"

    # ---------------------------------------------------------------- 主流程 ---
    def evaluate(self, fields: dict, case_id: str = "") -> dict:
        fields, derive_notes = self.derive(fields)
        total_rules = len(self.rules)

        result = {
            "case_id": case_id,
            "state": "",
            "verdict": "",
            "verdict_qualified": "",
            "coverage": {},
            "triggered_rules": [],
            "not_triggered_rules": [],
            "undetermined_rules": [],
            "obligations": [],
            "missing_materials": [],
            "notes": list(derive_notes),
        }

        # ---- 三态入口 1：明确不适用 ----
        if fields.get("存在个人信息处理行为") is False:
            result["state"] = "not_applicable"
            result["verdict"] = "不适用"
            result["verdict_qualified"] = "不适用"
            result["coverage"] = self.coverage(total_rules, 0, 0,
                                               note="本法不适用，无需逐条判定")
            result["notes"].append(
                self.states.get("not_applicable", {}).get(
                    "message", "不存在个人信息处理行为，本法不适用（第四条）"))
            # 不适用时不逐条列原因（场景根本没进入规则判断），但字段要存在
            result["inactive_detail"] = []
            return result

        # ---- 规则求值 ----
        triggered, undetermined = [], []
        for r in self.rules:
            st = eval_condition(r.get("condition", {}), fields)
            if st is True:
                triggered.append(r)
            elif st is None:
                undetermined.append(r)
            else:
                result["not_triggered_rules"].append(r["rule_id"])

        result["undetermined_rules"] = [r["rule_id"] for r in undetermined]

        # ---- 三态入口 2/3 ----
        if not triggered:
            result["state"] = "uncovered"
            result["verdict"] = "未覆盖"
            result["verdict_qualified"] = "未覆盖（转人工）"
            result["coverage"] = self.coverage(
                total_rules, len(result["not_triggered_rules"]),
                len(undetermined), note="没有任何规则被触发")
            if undetermined:
                missing_fields = []
                for r in undetermined:
                    for c in r.get("condition", {}).get("all", []):
                        if c["field"] not in fields:
                            missing_fields.append(c["field"])
                result["notes"].append(
                    "无法判定：下列触发字段缺失 -> %s；转人工确认，禁止默认合规"
                    % "、".join(dict.fromkeys(missing_fields)))
            else:
                result["notes"].append(
                    self.states.get("uncovered", {}).get(
                        "message", "当前场景未纳入规则集覆盖范围，转人工确认"))
            # 未覆盖时最重要：把「为什么判不了」逐条摊开
            result["inactive_detail"] = self._build_inactive(
                result["not_triggered_rules"], result["undetermined_rules"], fields)
            return result

        result["state"] = "evaluated"
        result["triggered_rules"] = [r["rule_id"] for r in triggered]

        # ---- 逐规则求值 action ----
        per_rule = []
        for r in triggered:
            acts = []
            for a in r.get("action", []) or []:
                res = eval_action(a, fields)
                res["rule_id"] = r["rule_id"]
                acts.append(res)
            per_rule.append({"rule_id": r["rule_id"], "article": r["article"], "actions": acts})

        # ---- 去重 1：单独同意优先于一般同意 ----
        special_consent_unmet = []
        for pr in per_rule:
            if pr["rule_id"] == BASELINE_RULE:
                continue
            for a in pr["actions"]:
                if "consent" in a["action_id"] and a["status"] == "unmet":
                    special_consent_unmet.append(pr["rule_id"])

        if special_consent_unmet:
            for pr in per_rule:
                if pr["rule_id"] != BASELINE_RULE:
                    continue
                for a in pr["actions"]:
                    if a["action_id"] == BASELINE_CONSENT_GROUP and a["status"] == "unmet":
                        a["status"] = "subsumed"
                        a["missing"] = []
                        a["note"] = "由 %s 的单独同意要求覆盖，不重复输出" % "、".join(
                            dict.fromkeys(special_consent_unmet))

        # ---- 汇总缺失项（按标签去重，保序） ----
        missing_all = []
        for pr in per_rule:
            for a in pr["actions"]:
                if a["status"] == "unmet":
                    for m in a["missing"]:
                        if m not in missing_all:
                            missing_all.append(m)

        # ---- 判定 ----
        unmet = [a for pr in per_rule for a in pr["actions"] if a["status"] == "unmet"]
        result["obligations"] = per_rule
        result["missing_materials"] = missing_all
        result["verdict"] = "不合规" if unmet else "合规"
        result["coverage"] = self.coverage(
            total_rules,
            len(result["triggered_rules"]) + len(result["not_triggered_rules"]),
            len(result["undetermined_rules"]))
        result["verdict_qualified"] = self.qualify(result["verdict"], result["coverage"])

        # ---- 附加说明 ----
        for pr in per_rule:
            for a in pr["actions"]:
                if a["status"] == "met" and a["note"]:
                    result["notes"].append("%s：%s" % (pr["rule_id"], a["note"]))
                if a["status"] == "not_required":
                    result["notes"].append("%s / %s：条件未成立，本组不适用"
                                           % (pr["rule_id"], a["action_id"]))
        if result["undetermined_rules"]:
            result["notes"].append(
                "另有 %d 条规则因字段不足未能判定：%s"
                % (len(result["undetermined_rules"]), "、".join(result["undetermined_rules"])))

        # ---- 未触发/未判定规则的原因追踪（供界面展示「为什么没触发」）----
        # 三值逻辑下，"不适用"有两种：条件为假（字段给了但对不上）、
        # 或字段缺失无法判定。两者都要能解释给用户看。
        result["inactive_detail"] = self._build_inactive(
            result["not_triggered_rules"], result["undetermined_rules"], fields)
        return result

    # ------------------------------------------------------- 条件求值追踪 ---
    @staticmethod
    def trace(rule: dict, fields: dict) -> list:
        """逐条记录条件项的求值情况，用于解释「为什么没触发」"""
        out = []
        for mode in ("all", "any", "none"):
            for c in (rule.get("condition") or {}).get(mode) or []:
                f = c.get("field")
                present = f in fields
                out.append({
                    "mode": mode,
                    "field": f,
                    "expected": c.get("value"),
                    "actual": fields.get(f) if present else None,
                    "present": present,
                    "ok": (fields.get(f) == c.get("value")) if present else None,
                })
        return out

    def _build_inactive(self, not_trig: list, undet: list, fields: dict) -> list:
        """构造「未触发 / 未判定」规则的追踪列表（三态所有分支都要有）"""
        inactive = []
        for rid, reason, text in (
            *[(r, "condition_false", "触发条件不成立（字段已提供但对不上）") for r in not_trig],
            *[(r, "field_missing", "触发字段未提供，无法判定") for r in undet],
        ):
            inactive.append({
                "rule_id": rid,
                "reason": reason,
                "reason_text": text,
                "condition": self.trace(self.by_id[rid], fields) if rid in self.by_id else [],
            })
        return inactive

    # ------------------------------------------------------------ 格式化输出 ---
    @staticmethod
    def render(res: dict) -> str:
        lines = []
        lines.append("=" * 72)
        lines.append("case: %s   state: %s   verdict: %s" % (
            res["case_id"] or "-", res["state"], res["verdict"]))
        lines.append("-" * 72)
        if res["triggered_rules"]:
            lines.append("触发规则: " + "、".join(res["triggered_rules"]))
        if res["not_triggered_rules"]:
            lines.append("不触发:   " + "、".join(res["not_triggered_rules"]))
        if res["undetermined_rules"]:
            lines.append("未判定:   " + "、".join(res["undetermined_rules"]))
        for pr in res.get("obligations", []):
            for a in pr["actions"]:
                flag = {"met": "OK", "unmet": "MISS", "subsumed": "DEDUP",
                        "not_required": "SKIP"}.get(a["status"], a["status"])
                lines.append("  [%s] %-12s %-22s %s" % (flag, pr["rule_id"], a["action_id"], a["label"]))
                if a["missing"]:
                    lines.append("         缺: " + "；".join(a["missing"]))
                if a["note"]:
                    lines.append("         注: " + a["note"])
        if res["missing_materials"]:
            lines.append("-" * 72)
            lines.append("缺失材料清单（去重后 %d 项）:" % len(res["missing_materials"]))
            for i, m in enumerate(res["missing_materials"], 1):
                lines.append("  %d. %s" % (i, m))
        if res["notes"]:
            lines.append("-" * 72)
            for n in res["notes"]:
                lines.append("  · " + n)
        return "\n".join(lines)


def load_engine(default_path: str | None = None) -> Engine:
    path = default_path or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "rules", "pipl-separate-consent_v2.5.yaml")
    return Engine(path)


if __name__ == "__main__":
    import json
    import sys

    eng = load_engine()
    if len(sys.argv) > 1:
        with open(sys.argv[1], encoding="utf-8") as fh:
            fields = json.load(fh)
    else:
        fields = json.loads(sys.stdin.read() or "{}")
    print(Engine.render(eng.evaluate(fields)))
