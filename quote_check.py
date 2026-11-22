# -*- coding: utf-8 -*-
"""法条引用校验（B 级归一化：去空白 + 全半角标点统一）

背景：`tools/yaml_audit.py` 的 norm() 只去空白，不容忍标点差异。
本模块用于规则集/引擎输出中的 quote 校验，标准为「表达一致即可」：
  - 去除所有空白（含全角空格 U+3000）
  - 全角字母数字 -> 半角（NFKC）
  - 全角标点 -> 对应半角标点
  - 统一引号、破折号、顿号

注意：归一化只是放宽「排版差异」，不放过「用字差异」（其他/其它 仍会不匹配）。
"""
from __future__ import annotations

import re
import unicodedata

# 全角/中文标点 -> 统一形态
_PUNCT_MAP = {
    "，": ",", "。": ".", "；": ";", "：": ":",
    "？": "?", "！": "!", "、": ",",
    "（": "(", "）": ")", "〔": "(", "〕": ")",
    "【": "[", "】": "]", "《": "<", "》": ">",
    "\u201c": '"', "\u201d": '"',      # “ ”
    "\u2018": "'", "\u2019": "'",      # ‘ ’
    "\u2014": "-", "\u2013": "-",      # — –
    "\uff0d": "-", "\uff5e": "~",      # － ～
    "\u00b7": ".", "\u2027": ".",      # · ‧
    "\u3001": ",",
}


def normalize(s: str) -> str:
    """B 级归一化：只抹平排版差异，不抹平用字差异"""
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s)      # 全角字母/数字/部分标点 -> 半角
    s = re.sub(r"[\s\u3000]+", "", s)         # 去全部空白
    for a, b in _PUNCT_MAP.items():
        s = s.replace(a, b)
    return s


def contains(quote: str, article_text: str) -> bool:
    """quote 是否逐字出现在 article_text 中（B 级归一化后）"""
    q = normalize(quote)
    if not q:
        return False
    return q in normalize(article_text)


def first_mismatch(quote: str, article_text: str, span: int = 12) -> str:
    """定位第一处不一致，便于排查"""
    q, a = normalize(quote), normalize(article_text)
    if q in a:
        return ""
    lo, hi = 0, min(len(q), len(a))
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if q[:mid] in a:
            lo = mid
        else:
            hi = mid - 1
    pos = lo
    left = max(0, pos - span)
    return "首个不一致位置 %d：引用「%s」/ 原文「%s」" % (
        pos, q[left:pos + span], a[left:pos + span])


def load_articles(md_path: str) -> dict:
    """从法条 md 解析 ## 第X条 -> 正文"""
    import os
    if not os.path.exists(md_path):
        return {}
    text = open(md_path, encoding="utf-8").read()
    arts, cur, buf = {}, None, []
    for line in text.split("\n"):
        m = re.match(r"^##\s+(第[一二三四五六七八九十百零]+条)\s*$", line.strip())
        if m:
            if cur:
                arts[cur] = "\n".join(buf).strip()
            cur, buf = m.group(1), []
        elif cur is not None:
            if line.strip().startswith(("（未在源文件", "> ")):
                continue
            buf.append(line)
    if cur:
        arts[cur] = "\n".join(buf).strip()
    return arts


if __name__ == "__main__":
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    arts = load_articles(os.path.join(here, "data", "laws", "个人信息保护法.md"))
    print("已加载法条: %d 条 -> %s" % (len(arts), "、".join(arts.keys())))
    # 演示：全角标点差异也能通过
    demo = "个人信息处理者不得公开其处理的个人信息,取得个人单独同意的除外."
    print("标点差异容忍测试:", contains(demo, arts.get("第二十五条", "")))
