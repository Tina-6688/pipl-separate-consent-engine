#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
公开前自检 —— 确认这个仓库可以对外公开。

设计原则
--------
本脚本只包含**通用**检查模式，**不含任何具体公司名、客户名、项目代号**。
如果你有自己的黑名单（前雇主、客户、内部代号），写进同目录的

    .check_public.local.json

例如：

    {
      "banned_words":      ["某公司A", "某客户B", "内部代号C"],
      "banned_name_parts": ["草稿", "内部评审"]
    }

**这个文件不要提交**（已在 .gitignore 里）。它只存在于你本地。

检查项
------
1. 文件名        不该被跟踪的文件（缓存 / 报告 / 凭据）
2. 文本内容      真实姓名 / 手机号 / 邮箱 / 本地绝对路径 / 凭据 / 计算机名 + 本地自定义词
3. Office 元数据 xlsx / docx 的 docProps 会记录作者与本机 Windows 用户名
4. Office 正文   xlsx 单元格文本也会扫（元数据干净不等于内容干净）
5. 提交信息      git log 里的姓名与"自述式隐瞒"措辞（文件扫描抓不到这一类）

用法
----
    python check_public.py          # 检查，有问题返回 1
    python check_public.py -v       # 列出所有被跟踪文件

注意：本脚本依赖 `git ls-files`，**必须在 git init 之后**才能运行。
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LOCAL_CFG = os.path.join(HERE, ".check_public.local.json")

# ---------------------------------------------------------------- 通用规则 ---

# 文件名里出现这些片段就不该被跟踪
BANNED_NAME_PARTS = [
    "__pycache__",
    ".pyc",
    "_report.txt",
    ".env",
    "credentials",
]

# 内容里出现这些就不该公开（全部是通用模式，不含具体名称）
BANNED_CONTENT = {
    "真实姓名（X女士/X先生）": r"[\u4e00-\u9fa5]{1,3}(女士|先生)",
    "手机号": r"(?<!\d)1[3-9]\d{9}(?!\d)",
    "邮箱地址": r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
    "Windows 用户目录": r"[A-Za-z]:[\\/]+Users[\\/]+[^<>\"\\/\s]+",
    "盘符绝对路径": r"(?<![A-Za-z])[A-Za-z]:[\\/](?![\\/])[^<>\"\s]{3,}",
    "疑似凭据": r"(?i)(api[_-]?key|secret|passwd|password|token)\s*[:=]\s*\S{12,}",
    "计算机名样式": r"(?i)DESKTOP-[A-Z0-9]{5,}|LAPTOP-[A-Z0-9]{5,}",
}

# 提交信息里另加（"我把 X 改成了 Y" 这类自述式泄露）
BANNED_COMMIT_EXTRA = {
    "自述式隐瞒": r"真实姓氏|真实姓名|不便公开|刻意隐藏|不适合随公开",
}

# 扩展名
OFFICE_EXT = (".xlsx", ".docx", ".pptx", ".xlsm", ".docm")
BINARY_EXT = (".png", ".jpg", ".jpeg", ".gif", ".ico", ".zip", ".pyc", ".pdf") + OFFICE_EXT


# ---------------------------------------------------------------- 本地配置 ---

def load_local():
    if not os.path.isfile(LOCAL_CFG):
        return {"banned_words": [], "banned_name_parts": []}, False
    try:
        with open(LOCAL_CFG, encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception as e:
        print("[WARN] 本地配置读取失败（忽略）：%s" % e)
        return {"banned_words": [], "banned_name_parts": []}, True
    return {
        "banned_words": [w for w in cfg.get("banned_words", []) if w],
        "banned_name_parts": [w for w in cfg.get("banned_name_parts", []) if w],
    }, True


# ---------------------------------------------------------------- 工具函数 ---

def git(*args):
    r = subprocess.run(["git"] + list(args), cwd=HERE, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or ""), (r.stderr or "")


def tracked_files():
    rc, out, _ = git("-c", "core.quotepath=false", "ls-files")
    if rc != 0:
        print("[FAIL] 这不是一个 git 仓库（或 git 不可用）。")
        print("       本脚本依赖 git ls-files，请先：git init && git add -A && git commit")
        sys.exit(2)
    return [x for x in out.split("\n") if x.strip()]


def scan_patterns(text, patterns):
    hits = []
    for label, pat in patterns.items():
        for m in re.finditer(pat, text):
            a = max(0, m.start() - 40)
            b = min(len(text), m.end() + 40)
            hits.append((label, text[a:b].replace("\n", " ")))
    return hits


def scan_words(text, words):
    hits = []
    for w in words:
        for m in re.finditer(re.escape(w), text):
            a = max(0, m.start() - 40)
            b = min(len(text), m.end() + 40)
            hits.append(("自定义词：" + w, text[a:b].replace("\n", " ")))
    return hits


def read_text(fp):
    try:
        return open(fp, encoding="utf-8", errors="ignore").read()
    except OSError:
        return ""


# ---------------------------------------------------------------- 主流程 ---

def main() -> int:
    verbose = "-v" in sys.argv
    cfg, cfg_exists = load_local()
    words = cfg["banned_words"]
    name_parts = BANNED_NAME_PARTS + cfg["banned_name_parts"]
    files = tracked_files()
    problems = []

    print("被跟踪文件：%d 个" % len(files))
    if cfg_exists:
        print("本地配置：已加载（自定义词 %d 个）" % len(words))
    else:
        print("本地配置：无（%s）" % os.path.basename(LOCAL_CFG))
        print("          如需拦截内部名称，请创建该文件；格式见脚本头部说明。")
    if verbose:
        for f in files:
            print("  " + f)

    text_files = [f for f in files if not f.lower().endswith(BINARY_EXT)]

    # ---- 1 ----
    print("\n[1] 文件名检查")
    bad = [f for f in files if any(p in f for p in name_parts)]
    if bad:
        problems.extend("不该公开的文件被跟踪：" + f for f in bad)
        print("  FAIL  %d 个：%s" % (len(bad), bad[:5]))
    else:
        print("  OK    0 个")

    # ---- 2 ----
    print("\n[2] 文本内容检查")
    for label, pat in BANNED_CONTENT.items():
        hits = []
        for f in text_files:
            hits.extend(scan_patterns(read_text(os.path.join(HERE, f.replace("/", os.sep))),
                                      {label: pat}))
        if hits:
            problems.extend("%s :: %s" % h for h in hits)
            print("  FAIL  %-22s %d 处" % (label, len(hits)))
            for l, c in hits[:3]:
                print("          ...%s..." % c)
        else:
            print("  OK    %-22s 0" % label)

    if words:
        hits = []
        for f in text_files:
            hits.extend(scan_words(read_text(os.path.join(HERE, f.replace("/", os.sep))), words))
        if hits:
            problems.extend("%s :: %s" % h for h in hits)
            print("  FAIL  %-22s %d 处" % ("自定义词（本地配置）", len(hits)))
            for l, c in hits[:3]:
                print("          %s: ...%s..." % (l, c))
        else:
            print("  OK    %-22s 0" % "自定义词（本地配置）")

    # ---- 3/4 ----
    print("\n[3] Office 元数据与正文")
    office = [f for f in files if f.lower().endswith(OFFICE_EXT)]
    if not office:
        print("  OK    仓库内无 Office 文件")
    for f in office:
        fp = os.path.join(HERE, f.replace("/", os.sep))
        if not os.path.isfile(fp):
            continue
        try:
            import zipfile
            z = zipfile.ZipFile(fp)
        except Exception:
            print("  FAIL  %s 无法作为 zip 打开" % f)
            problems.append("Office 文件损坏：" + f)
            continue

        meta = []
        for part in ("docProps/core.xml", "docProps/app.xml", "docProps/custom.xml"):
            if part in z.namelist():
                meta.append(z.read(part).decode("utf-8", "ignore"))
        blob = "\n".join(meta)
        m_hits = scan_patterns(blob, BANNED_CONTENT) + scan_words(blob, words)
        creator = re.search(r"<dc:creator[^>]*>([^<]*)</dc:creator>", blob)
        creator = creator.group(1) if creator else "（未记录）"

        cell_hits = []
        if f.lower().endswith((".xlsx", ".xlsm")):
            try:
                from openpyxl import load_workbook
                wb = load_workbook(fp, data_only=True, read_only=True)
                for ws in wb.worksheets:
                    for i, row in enumerate(ws.iter_rows(values_only=True)):
                        if i > 5000:
                            break
                        for v in row:
                            if isinstance(v, str) and v:
                                cell_hits.extend(scan_patterns(v, BANNED_CONTENT))
                                cell_hits.extend(scan_words(v, words))
                wb.close()
            except ImportError:
                cell_hits.append(("提示", "openpyxl 未安装，单元格未扫"))
            except Exception as e:
                cell_hits.append(("提示", "单元格扫描失败：%s" % e))

        if m_hits or cell_hits:
            for l, c in (m_hits + cell_hits):
                problems.append("%s :: %s :: %s" % (f, l, c))
            print("  FAIL  %s  元数据 %d / 正文 %d" % (f, len(m_hits), len(cell_hits)))
            for l, c in (m_hits + cell_hits)[:3]:
                print("          %s: ...%s..." % (l, c))
        else:
            print("  OK    %s  作者=%s，元数据与正文均干净" % (f, creator))

    # ---- 5 ----
    print("\n[5] git 提交信息（含历史）")
    rc, msgs, _ = git("-c", "core.quotepath=false", "log", "--branches", "--remotes", "--format=%B")
    SELF_DESC = ("自述式隐瞒", "自述式泄露", "额外拦", "check_public",
                 "BANNED_COMMIT", ".check_public.local")
    scan_msgs = "\n".join(ln for ln in msgs.split("\n") if not any(k in ln for k in SELF_DESC))
    m_hits = scan_patterns(scan_msgs, dict(BANNED_CONTENT, **BANNED_COMMIT_EXTRA)) \
        + scan_words(scan_msgs, words)
    if m_hits:
        for l, c in m_hits:
            problems.append("提交信息泄漏（%s）：%s" % (l, c))
            print("  FAIL  %s :: ...%s..." % (l, c))
    else:
        rc2, n, _ = git("rev-list", "--branches", "--remotes", "--count")
        print("  OK    历史 %s 个提交，提交信息干净" % (n.strip() or "?"))

    # ---- 6 ----
    print("\n[6] 文档引用的提交 SHA（能否在本仓库解析）")
    HEX = re.compile(r"(?<![0-9A-Za-z])([0-9a-f]{7,40})(?![0-9A-Za-z])")
    CTX = ("提交", "commit", "基线", "HEAD")
    SKIP_CTX = ("SHA256", "sha256", "哈希", "校验值", "blob", "SHA-1", "sha1", "SHA-1")
    checked = 0
    sha_bad = []
    for f in text_files:
        txt = read_text(os.path.join(HERE, f.replace("/", os.sep)))
        for m in HEX.finditer(txt):
            sha = m.group(1)
            if not re.search(r"[a-f]", sha):      # 纯数字多为日期/编号，跳过
                continue
            a, b = max(0, m.start() - 70), min(len(txt), m.end() + 70)
            ctx = txt[a:b]
            if any(k in ctx for k in SKIP_CTX):
                continue
            if not any(k in ctx for k in CTX):
                continue
            checked += 1
            rc, _, _ = git("cat-file", "-e", sha)
            if rc != 0:
                sha_bad.append((f, sha, ctx.replace("\n", " ")))
    if sha_bad:
        for f, sha, ctx in sha_bad:
            problems.append("文档引用了本仓库不存在的提交 %s（%s）" % (sha, f))
            print("  FAIL  %s  %s" % (sha, f))
            print("        ...%s..." % ctx[:120])
    else:
        print("  OK    检查 %d 处引用，全部可解析" % checked)

    print("\n" + "=" * 62)
    if problems:
        print("结论：[FAIL] 有 %d 处需要处理，先不要公开" % len(problems))
        return 1
    print("结论：[PASS] 可以公开")
    return 0


if __name__ == "__main__":
    sys.exit(main())
