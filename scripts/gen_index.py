#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GitHub 项目索引生成器 · 单次运行，同时刷新三件产物：

    _repos.json   机器可读数据（唯一事实来源）
    README.md     人读的分类目录（GitHub 首页直接展示）
    index.html    深色看板（可搜索、可筛选）

三者由同一份实时数据生成，杜绝「README 说 41 个但实际已删」这类过期问题。

用法：
    python scripts/gen_index.py              # 生成到仓库根目录
    python scripts/gen_index.py --out DIR    # 生成到指定目录
    python scripts/gen_index.py --user X --org Y

依赖：已登录的 gh CLI（gh auth login）。
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from collections import Counter

TZ8 = timezone(timedelta(hours=8))

# ---------------------------------------------------------------- 分类

CATS = [
    ("内容生产与资讯", "把游戏资讯加工成可读内容、榜单与看板", "#f97316"),
    ("游戏与工具", "面向玩家与运营的实际可用工具", "#22c55e"),
    ("AI 能力与技能", "技能包、路由入口与迁移归档", "#818cf8"),
    ("数据与配置", "行情数据、运行配置与密钥备份", "#38bdf8"),
    ("创作与归档", "小说创作、项目索引与杂项存档", "#e879f9"),
    ("平台与工程", "自用工作台与基础工程", "#fbbf24"),
    ("组织仓库", "GHZS-Project 下的团队仓库", "#94a3b8"),
]

CAT_OF = {}
for _n in ["GameNews", "gamenews-snapshots", "endgame-weekly-report", "game-aggregator",
           "NewgameWiki", "newgamewiki-data", "Agnes-vampire-survivors-wiki-tool",
           "GH-GameNews", "GH-Gamehub", "GH-NewGameWIki", "GH-WeeklyReport", "GH-GameSearch"]:
    CAT_OF[_n] = "内容生产与资讯"
for _n in ["Komo-Convert", "komo-convert-dist", "okcs2-monitor-suite", "H5Game",
           "H5Game-SlotRoguelike", "gameops-bulk-import", "GH-CloudGame",
           "GH-Game-Puton", "GH-GameSearch-Prototype", "GH-GameGather-APP",
           "GH-GameGather-UPSTREAM"]:
    CAT_OF[_n] = "游戏与工具"
for _n in ["Komoyou-Skill-WorkBuddy", "Komoyou-Skill", "komo-agent-skill", "REA-Skill",
           "codex-migration-pack", "codex-session-archive", "openclaw-requirements",
           "GH-KomoSkill"]:
    CAT_OF[_n] = "AI 能力与技能"
for _n in ["Market-dashboard", "komo-market-dashboard-data", "gamenews-env-secrets"]:
    CAT_OF[_n] = "数据与配置"
for _n in ["novel-archive", "komo-project-index", "komo-misc-archive", "GH-Handover"]:
    CAT_OF[_n] = "创作与归档"
for _n in ["pm-workbench"]:
    CAT_OF[_n] = "平台与工程"

# 中文简述：仓库自带 description 是英文或过长时用这里的短句
SHORT = {
    "GameNews": "游戏资讯采集、简讯海报生成与飞书投递",
    "gamenews-snapshots": "GameNews 周榜快照归档",
    "endgame-weekly-report": "端游三源周报归档与在线看板",
    "game-aggregator": "单机游戏信息聚合站，整合机地与 XDGAME",
    "NewgameWiki": "本地优先的游戏资讯与排期工具",
    "newgamewiki-data": "NewgameWiki 数据快照",
    "Agnes-vampire-survivors-wiki-tool": "吸血鬼幸存者 Wiki 导出与翻译",
    "Komo-Convert": "Windows 通用工具箱：转换、加速、APK",
    "komo-convert-dist": "Komo-Convert 发行包（内含 exe 成品）",
    "okcs2-monitor-suite": "本地监控与数据归档：开箱、对战、指数",
    "H5Game": "H5 小游戏合集与打包产物",
    "H5Game-SlotRoguelike": "像素风 H5 肉鸽，含科技树",
    "gameops-bulk-import": "游戏后台批量导入工具",
    "Komoyou-Skill-WorkBuddy": "WorkBuddy 技能合集与 Komo 专家包",
    "Komoyou-Skill": "Codex 技能合集与总控入口",
    "komo-agent-skill": "Codex 技能路由入口，一句话分派",
    "REA-Skill": "获授权应用与游戏的逆向、反编译技能",
    "codex-migration-pack": "Codex 配置与技能迁移包",
    "codex-session-archive": "Codex、WorkBuddy 会话记录归档",
    "openclaw-requirements": "Openclaw 环境依赖安装包",
    "Market-dashboard": "A 股与 ETF 行情、研究、模拟交易",
    "komo-market-dashboard-data": "行情看板运行数据，含飞书/钉钉配置",
    "gamenews-env-secrets": "环境变量备份，含密钥",
    "novel-archive": "小说创作归档，两部原创与 InkAI",
    "komo-project-index": "全仓项目索引与看板（本仓库）",
    "komo-misc-archive": "杂项归档：企划书、解包工具、数据导出",
    "pm-workbench": "项目管理、任务看板、服务监控平台",
    "GH-GameGather-APP": "PC/手游情报站 + 资源索引 + Electron 桌面成品",
    "GH-GameGather-UPSTREAM": "GameGather APP 的配套数据服务",
    "GH-GameNews": "团队版游戏资讯采集与飞书投递",
    "GH-Gamehub": "机地与 XDGAME 聚合站（团队版）",
    "GH-CloudGame": "云游戏相关采集与分析",
    "GH-KomoSkill": "团队版技能包",
    "GH-Handover": "交接文档与在线看板",
    "GH-WeeklyReport": "团队版周报生成",
    "GH-NewGameWIki": "团队版 NewgameWiki",
    "GH-GameSearch": "游戏搜索（Android）",
    "GH-Game-Puton": "游戏后台批量导入（便携版）",
    "GH-GameSearch-Prototype": "GH-GameSearch 原型归档",
}

# 实测确认过的 release 附件（脚本会自动覆盖，这里只作离线兜底）
FALLBACK_ASSETS = {
    "komo-convert-dist": "KomoConvert.exe 204.4MB + avfilter-12.dll 101.9MB",
    "GH-GameGather-APP": "GH-GameGather-APP-v28-win-x64.zip 262.4MB",
}

RUN_ENTRY = {"package.json": "Node", "requirements.txt": "Python", "pyproject.toml": "Python",
             "build.gradle": "Android", "build.gradle.kts": "Android", "pom.xml": "Java",
             "go.mod": "Go", "Cargo.toml": "Rust"}
ENV_HINT = {".env.example", ".env.sample", ".env.template", "config.example.json"}
BIN_EXT = (".exe", ".msi", ".dmg", ".appimage")
PACK_EXT = (".zip", ".7z", ".tar.gz", ".tgz")
DATA_WORDS = ("data", "snapshot", "backup", "dump", "dataset", "快照", "备份")

LEVELS = [
    ("A", "下载即装", "release 里有现成程序，下载解压就能用", "#22c55e"),
    ("B", "源码可跑", "有标准依赖文件，clone 后装依赖即可运行", "#38bdf8"),
    ("C", "技能包", "供 AI 调用，不是给人直接运行的", "#818cf8"),
    ("D", "脚本直跑", "独立脚本，装了解释器就能跑", "#a78bfa"),
    ("E", "静态页", "双击 index.html 即可查看", "#fbbf24"),
    ("F", "存档数据", "纯数据/文档，不需要运行", "#94a3b8"),
]
LEVEL_MAP = {k: (n, c) for k, n, _, c in LEVELS}


# ---------------------------------------------------------------- 显示开关

CONFIG_NAME = "index.config.json"

DEFAULT_CONFIG = {
    "_readme": "控制哪些仓库不出现在 README.md 与 index.html 中。改完重跑 python scripts/gen_index.py 即生效。",
    "hide_prefixes": ["GH-"],
    "hide_repos": [],
    "hide_private": False,
    "note_hidden": False,
}


def load_config(path=None):
    """读取显示配置；文件不存在时写出默认配置并返回。"""
    path = path or os.path.join(os.path.dirname(os.path.abspath(__file__)), CONFIG_NAME)
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, ensure_ascii=False, indent=2)
        print("已生成默认配置：%s" % path)
        return dict(DEFAULT_CONFIG), path
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    for k, v in DEFAULT_CONFIG.items():
        cfg.setdefault(k, v)
    return cfg, path


def mark_hidden(recs, cfg):
    """按配置给每条记录打 hidden 标记，返回 (可见列表, 隐藏列表)。"""
    pre = tuple(cfg.get("hide_prefixes") or ())
    names = set(cfg.get("hide_repos") or ())
    hide_priv = bool(cfg.get("hide_private"))

    visible, hidden = [], []
    for r in recs:
        why = ""
        if names and r["name"] in names:
            why = "名单"
        elif pre and r["name"].startswith(pre):
            why = "前缀"
        elif hide_priv and r["private"]:
            why = "私有"
        r["hidden"] = bool(why)
        r["hide_by"] = why
        (hidden if why else visible).append(r)
    return visible, hidden


# ---------------------------------------------------------------- gh 调用

def gh(args, retries=3):
    for i in range(retries):
        p = subprocess.run(["gh"] + args, capture_output=True)
        if p.returncode == 0:
            return p.stdout
        msg = p.stderr.decode("utf-8", "replace")
        if i == retries - 1:
            raise SystemExit("gh 调用失败：gh %s\n%s" % (" ".join(args), msg[:400]))
    return b""


def gh_json(args, retries=3):
    return json.loads(gh(args, retries).decode("utf-8"))


FIELDS = """
        name isPrivate isFork isArchived pushedAt diskUsage description url
        primaryLanguage { name }
        defaultBranchRef { target { ... on Commit { committedDate message history(first:1){ totalCount } } } }
        releases(first: 3, orderBy: {field: CREATED_AT, direction: DESC}) { totalCount nodes { tagName publishedAt } }
        object(expression: "HEAD:") { ... on Tree { entries { name type } } }
"""

Q_PERSONAL = """query {
  viewer {
    repositories(first: 100, ownerAffiliations: OWNER,
                  orderBy: {field: PUSHED_AT, direction: DESC}) {
      nodes { %s }
    }
  }
}""" % FIELDS

Q_ORG = """query($login: String!) {
  organization(login: $login) {
    repositories(first: 100, isFork: false) {
      nodes { %s }
    }
  }
}""" % FIELDS


def fetch(login=None, is_org=False):
    if is_org:
        raw = gh(["api", "graphql", "-f", "query=" + Q_ORG, "-F", "login=" + login])
        d = json.loads(raw.decode("utf-8"))
        if "errors" in d:
            raise SystemExit("GraphQL 报错：%s" % json.dumps(d["errors"], ensure_ascii=False)[:300])
        ns = d["data"]["organization"]["repositories"]["nodes"]
    else:
        raw = gh(["api", "graphql", "-f", "query=" + Q_PERSONAL])
        d = json.loads(raw.decode("utf-8"))
        if "errors" in d:
            raise SystemExit("GraphQL 报错：%s" % json.dumps(d["errors"], ensure_ascii=False)[:300])
        ns = d["data"]["viewer"]["repositories"]["nodes"]
    for n in ns:
        n["owner"] = login or "me"
    return ns


def fetch_assets(repo, owner):
    """查 release 附件，区分「程序成品」与「数据快照」。

    返回 (apps, data)：apps 是可直接运行的成品，data 是数据/备份包。
    """
    try:
        rels = gh_json(["api", "repos/%s/%s/releases?per_page=3" % (owner, repo)])
    except SystemExit:
        return [], []
    apps, data = [], []
    for r in rels:
        tag_l = (r.get("tag_name") or "").lower()
        for a in r.get("assets") or []:
            name_l = a["name"].lower()
            item = {
                "tag": r["tag_name"],
                "name": a["name"],
                "mb": round(a["size"] / 1048576, 1),
                "url": a["browser_download_url"],
            }
            # 1) 可执行文件一定是程序，不看 tag 名（v1.0-archive 这种 tag 容易误伤）
            if name_l.endswith(BIN_EXT):
                apps.append(item)
                continue
            if not name_l.endswith(PACK_EXT):
                continue
            # 2) 压缩包才按关键词区分「程序打包」还是「数据快照」
            if any(w in name_l or w in tag_l for w in DATA_WORDS):
                data.append(item)
            else:
                apps.append(item)
    return apps, data


# ---------------------------------------------------------------- 判定

def classify(n):
    t = (n.get("defaultBranchRef") or {}).get("target") or {}
    entries = (n.get("object") or {}).get("entries") or []
    files = {e["name"] for e in entries if e.get("type") == "blob"}
    dirs = {e["name"] for e in entries if e.get("type") == "tree"}
    rel = n.get("releases") or {}
    rel_tags = [x["tagName"] for x in (rel.get("nodes") or [])]

    has_app_asset = bool(n.get("_apps"))
    if has_app_asset:
        return "A"
    entry_hit = sorted(set(RUN_ENTRY) & files)
    if entry_hit:
        return "B"
    if ({"skills", "experts", "legacy"} & dirs) or "SKILL.md" in files:
        return "C"
    if len([f for f in files if f.lower().endswith((".py", ".ps1", ".sh"))]) >= 1 \
            and not dirs.issuperset({"src"}):
        return "D"
    if "index.html" in files and len(entries) <= 15:
        return "E"
    return "F"


def how_to_use(n, level):
    """给一句「怎么用」的具体话，不是套话。"""
    if level == "A":
        a = (n.get("_apps") or [{}])[0]
        return "去 Releases 下载 %s（%.1f MB）" % (a.get("name", ""), a.get("mb", 0))
    if level == "B":
        lang = RUN_ENTRY.get(sorted(set(RUN_ENTRY) & set(n["_entries"]))[0], "")
        if lang == "Node":
            return "clone 后 npm install && npm start"
        if lang == "Python":
            return "clone 后 pip install -r requirements.txt 再运行入口脚本"
        if lang == "Android":
            return "clone 后用 Android Studio 打开构建"
        return "clone 后按 README 装依赖运行"
    if level == "C":
        return "把 skills/ 下的目录复制进 AI 的技能目录"
    if level == "D":
        py = [f for f in n["_entries"] if f.lower().endswith(".py")]
        return "python %s" % (py[0] if py else "入口脚本")
    if level == "E":
        return "直接打开 index.html，或用静态服务器托管"
    return "无需运行，按需查阅或复原"


# ---------------------------------------------------------------- 组装

def build_records(user, org):
    nodes = fetch(user, False)
    if org:
        nodes += fetch(org, True)

    recs = []
    for n in nodes:
        t = (n.get("defaultBranchRef") or {}).get("target") or {}
        entries = (n.get("object") or {}).get("entries") or []
        n["_entries"] = sorted(e["name"] for e in entries)
        n["_apps"], n["_data"] = [], []
        if (n.get("releases") or {}).get("totalCount"):
            n["_apps"], n["_data"] = fetch_assets(n["name"], n["owner"])

        lvl = classify(n)
        if lvl == "A" and not n["_apps"]:
            n["_apps"] = [{"tag": "?", "name": FALLBACK_ASSETS.get(n["name"], "未知附件"), "mb": 0, "url": ""}]
        lvl_name, lvl_color = LEVEL_MAP[lvl]

        pushed = datetime.strptime(n["pushedAt"][:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
        pushed8 = pushed.astimezone(TZ8)
        commits = (t.get("history") or {}).get("totalCount") or 0
        rels = (n.get("releases") or {}).get("nodes") or []

        rec = {
            "name": n["name"],
            "owner": n["owner"],
            "url": n["url"],
            "private": n["isPrivate"],
            "fork": n.get("isFork", False),
            "archived": n.get("isArchived", False),
            "desc": SHORT.get(n["name"]) or (n.get("description") or "").strip() or "（无描述）",
            "group": CAT_OF.get(n["name"], "组织仓库" if n["owner"] != user else "创作与归档"),
            "level": lvl,
            "level_name": lvl_name,
            "how": how_to_use(n, lvl),
            "commits": commits,
            "lang": (n.get("primaryLanguage") or {}).get("name") or "—",
            "kb": n["diskUsage"],
            "pushed": pushed8.strftime("%Y-%m-%d"),
            "days": (datetime.now(TZ8) - pushed8).days,
            "release": rels[0]["tagName"] if rels else "",
            "release_at": (rels[0]["publishedAt"] or "")[:10] if rels else "",
            "assets": n["_apps"],
            "data_assets": n["_data"],
            "env_required": bool(set(ENV_HINT) & set(n["_entries"])),
            "entries": n["_entries"][:20],
            "last_msg": ((t.get("message") or "").split("\n")[0])[:70],
        }
        # 建议动作
        acts = []
        if rec["archived"]:
            acts.append("已归档")
        if lvl == "F" and rec["days"] > 30:
            acts.append("可设为 archived")
        if not rec["release"] and lvl in ("A", "B"):
            acts.append("建议打 release")
        if rec["private"] and rec["name"] in ("gamenews-env-secrets", "komo-market-dashboard-data"):
            acts.append("含密钥，勿转公开")
        if not rec["private"] and rec["name"] == "komo-misc-archive":
            acts.append("公开仓含数据结构导出，复查")
        if rec["days"] > 60:
            acts.append("60 天未推送")
        rec["actions"] = acts
        recs.append(rec)

    recs.sort(key=lambda r: (r["level"], -r["commits"]))
    return recs


# ---------------------------------------------------------------- 输出 JSON

def write_json(recs, path, user, org, hidden_total=0, cfg=None):
    latest = max((r["pushed"] for r in recs), default="")
    forks = len([r for r in recs if r["fork"]])
    payload = {
        "generated_at": datetime.now(TZ8).strftime("%Y-%m-%d %H:%M:%S"),
        "owner": user,
        "org": org,
        "total": len(recs),
        "hidden_total": hidden_total,
        "forks": forks,
        "independent": len(recs) - forks,
        "by_level": dict(sorted(Counter(r["level"] for r in recs).items())),
        "by_group": dict(sorted(Counter(r["group"] for r in recs).items())),
        "latest_push": latest,
        "display_config": {
            k: (cfg or {}).get(k) for k in ("hide_prefixes", "hide_repos", "hide_private")
        },
        "repos": recs,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    return payload


# ---------------------------------------------------------------- 输出 README

def size_txt(kb):
    return ("%.1f MB" % (kb / 1024.0)) if kb >= 1024 else ("%d KB" % kb)


def write_readme(recs, path, user, org, hidden_total=0, note_hidden=False):
    now = datetime.now(TZ8).strftime("%Y-%m-%d %H:%M")
    priv = len([r for r in recs if r["private"]])
    forks = len([r for r in recs if r["fork"]])
    used = sum(r["kb"] for r in recs) / 1024.0
    lv = Counter(r["level"] for r in recs)
    lines = []
    lines.append("# 项目目录 · Komo\n")
    lines.append("本仓库是本机所有项目的**总索引**。共 **%d** 个仓库（公开 %d / 私有 %d），"
                 "其中 %d 个是 fork 副本，独立项目 **%d** 个；GitHub 侧合计约 **%.0f MB**。\n"
                 % (len(recs), len(recs) - priv, priv, forks, len(recs) - forks, used))
    lines.append("> 本文件由 `scripts/gen_index.py` 自动生成，**请勿手工修改**。最后刷新：%s（GMT+8）\n" % now)
    if note_hidden and hidden_total:
        lines.append("> 另有 %d 个仓库按 `scripts/index.config.json` 的配置不在本页展示。\n" % hidden_total)
    lines.append("\n## 按「能不能直接用」分级\n")
    lines.append("| 级别 | 含义 | 数量 |\n|---|---|---|")
    for k, name, desc, _ in LEVELS:
        n = lv.get(k, 0)
        if n:
            lines.append("| **%s %s** | %s | %d |" % (k, name, desc, n))
    lines.append("\n**结论：共 %d 个是「下载即装」的成品，%d 个是源码，%d 个是技能包，%d 个无需运行。**\n"
                 % (lv.get("A", 0), lv.get("B", 0), lv.get("C", 0), lv.get("F", 0)))

    for cat, cat_desc, _ in CATS:
        items = [r for r in recs if r["group"] == cat]
        if not items:
            continue
        lines.append("\n## %s　（%d 个）\n" % (cat, len(items)))
        lines.append("| 仓库 | 说明 | 能不能用 | 可见性 | 占用 | 最近推送 |")
        lines.append("|---|---|---|---|---|---|")
        for r in sorted(items, key=lambda x: (x["level"], -x["commits"])):
            vis = "🔒 私有" if r["private"] else "🌐 公开"
            use = "**%s %s**" % (r["level"], r["level_name"])
            if r["release"]:
                use += " · `%s`" % r["release"]
            label = r["name"] + (" 🔀" if r["fork"] else "")
            lines.append("| [%s](%s) | %s | %s | %s | %s | %s |"
                         % (label, r["url"], r["desc"], use, vis, size_txt(r["kb"]), r["pushed"]))

    lines.append("\n---\n")
    lines.append("## 怎么用这份索引\n")
    lines.append("| 你想做的是 | 看哪一节 | 数量 |\n|---|---|---|")
    lines.append("| 装个工具直接用 | A 下载即装 | %d |" % lv.get("A", 0))
    lines.append("| 继续开发改造 | B 源码可跑 | %d |" % lv.get("B", 0))
    lines.append("| 给 AI 用 | C 技能包 | %d |" % lv.get("C", 0))
    lines.append("| 查资料 / 恢复环境 | F 存档数据 | %d |" % lv.get("F", 0))
    lines.append("\n**刷新方式**：`python scripts/gen_index.py`（需已登录 `gh`）。"
                 "脚本会实时拉取 GitHub 数据，同时重写 `_repos.json`、本文件与 `index.html`。\n")
    lines.append("**可选隐藏**：`scripts/index.config.json` 控制哪些仓库不进本页与看板 —— "
                 "`hide_prefixes` 按名字前缀、`hide_repos` 按精确仓库名、`hide_private` 隐藏全部私有仓。"
                 "改完重跑脚本即生效；临时查看全量加 `--show-all`。\n")
    lines.append("**标记说明**：🔀 表示该仓库是 fork 副本，与组织仓库同名，不计入独立项目。\n")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return len("\n".join(lines))


# ---------------------------------------------------------------- 输出 HTML

def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


CSS = """
:root{
  --bg:#0b0d12; --panel:#141821; --panel2:#1a1f2b; --line:#252b38;
  --text:#e8ecf4; --muted:#98a2b3; --dim:#6b7688;
  --priv:#f472b6; --pub:#34d399;
}
*{box-sizing:border-box}
body{margin:0;background:radial-gradient(1200px 600px at 15% -10%,#16202e 0%,var(--bg) 55%);
color:var(--text);font-family:"Segoe UI","PingFang SC","Microsoft YaHei",system-ui,sans-serif;
padding:32px 28px 56px;-webkit-font-smoothing:antialiased}
.wrap{max-width:1400px;margin:0 auto}
h1{font-size:22px;margin:0 0 6px;letter-spacing:.4px}
.sub{color:var(--muted);font-size:13px;margin:0 0 22px;line-height:1.7}
.sub b{color:#cbd5e1;font-weight:600}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(148px,1fr));gap:12px;margin-bottom:18px}
.stat{background:linear-gradient(180deg,var(--panel2),var(--panel));border:1px solid var(--line);
border-radius:12px;padding:14px 16px}
.stat .k{color:var(--muted);font-size:12px;letter-spacing:.4px}
.stat .v{font-size:24px;font-weight:650;margin-top:6px;font-variant-numeric:tabular-nums}
.stat .v small{font-size:12px;color:var(--dim);font-weight:400;margin-left:4px}
.levels{background:linear-gradient(180deg,var(--panel2),var(--panel));border:1px solid var(--line);
border-radius:12px;padding:15px 16px;margin-bottom:20px}
.levels .lt{font-size:12.5px;color:var(--muted);margin-bottom:11px}
.lbar{display:flex;height:12px;border-radius:99px;overflow:hidden;background:#1b2130}
.lbar i{display:block;height:100%;transition:.2s}
.llegend{display:flex;gap:6px;flex-wrap:wrap;margin-top:12px}
.lkey{display:inline-flex;align-items:center;gap:6px;font-size:11.8px;color:#93a1b5;
background:#1b2130;border:1px solid #2a3245;border-radius:7px;padding:5px 10px;cursor:pointer}
.lkey.on{border-color:#3b82f6;background:#16233a;color:#dbeafe}
.lkey b{color:#dbe3ee;font-variant-numeric:tabular-nums}
.toolbar{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:6px 0 22px}
input#q{background:var(--panel);border:1px solid var(--line);border-radius:9px;color:var(--text);
padding:9px 12px;font-size:13px;width:270px;outline:none}
input#q:focus{border-color:#3b82f6}
.chip{background:var(--panel);border:1px solid var(--line);border-radius:999px;color:#c7d0dd;
font-size:12.5px;padding:7px 13px;cursor:pointer;display:inline-flex;gap:7px;align-items:center}
.chip em{font-style:normal;color:var(--dim);font-variant-numeric:tabular-nums}
.chip.on{border-color:#3b82f6;background:#16233a;color:#dbeafe}
.dot{width:8px;height:8px;border-radius:50%;display:inline-block}
.cat{margin:26px 0 8px}
.cat-head{display:flex;align-items:center;gap:10px;margin-bottom:12px;flex-wrap:wrap}
.cat-head h2{font-size:15.5px;margin:0;font-weight:600}
.cat-head .count{font-size:11.5px;color:var(--dim);border:1px solid var(--line);border-radius:999px;padding:2px 8px}
.cat-head .cat-desc{font-size:12.5px;color:var(--dim)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:12px}
.card{background:linear-gradient(180deg,var(--panel2),var(--panel));border:1px solid var(--line);
border-radius:12px;padding:14px 15px;transition:.16s;position:relative}
.card:hover{border-color:#37415a;transform:translateY(-2px)}
.card-top{display:flex;justify-content:space-between;align-items:center;gap:10px}
.repo{font-family:ui-monospace,Consolas,monospace;font-size:13.5px;color:#dbeafe;word-break:break-all}
.badge{font-size:11px;padding:2px 8px;border-radius:999px;white-space:nowrap;border:1px solid}
.badge.private{color:var(--priv);border-color:#5b2a45;background:#2a1420}
.badge.public{color:var(--pub);border-color:#1d4b3d;background:#0f2a24}
.desc{font-size:12.8px;color:#b9c3d3;margin:9px 0 10px;line-height:1.55;min-height:38px}
.lv{display:inline-flex;align-items:center;gap:7px;font-size:12px;font-weight:600;
border-radius:7px;padding:4px 10px;margin-bottom:9px;border:1px solid}
.how{font-size:11.8px;color:#8b97a8;margin:0 0 10px;line-height:1.5;
background:#111620;border-left:2px solid #2a3245;padding:7px 10px;border-radius:0 6px 6px 0}
.bar{height:3px;background:#1f2532;border-radius:99px;overflow:hidden;margin-bottom:9px}
.bar i{display:block;height:100%;background:linear-gradient(90deg,#3b82f6,#22d3ee);border-radius:99px}
.meta{display:flex;flex-wrap:wrap;gap:10px;font-size:11.5px;color:var(--dim);font-variant-numeric:tabular-nums}
.tags{display:flex;gap:6px;flex-wrap:wrap;margin:9px 0 4px}
.tag{font-size:11px;padding:2px 8px;border-radius:6px;background:#1b2130;border:1px solid #2a3245;color:#93a1b5}
.tag.rel{color:#a7f3d0;border-color:#1d4b3d;background:#0f2a24}
.tag.warn{color:#fbbf24;border-color:#5a4213;background:#2a1f06}
.tag.done{color:#94a3b8}
footer{margin-top:34px;border-top:1px solid var(--line);padding-top:14px;color:var(--dim);
font-size:11.5px;line-height:1.8}
.hide{display:none!important}
@media(max-width:640px){body{padding:20px 14px 40px}.grid{grid-template-columns:1fr}input#q{width:100%}}
"""

JS = """
const q=document.getElementById('q');
const chips=[...document.querySelectorAll('.chip')];
const lkeys=[...document.querySelectorAll('.lkey')];
let flt='all';
function apply(){
  const kw=q.value.trim().toLowerCase();
  document.querySelectorAll('.card').forEach(c=>{
    const t=(c.dataset.name+' '+c.querySelector('.desc').textContent).toLowerCase();
    const okKw=!kw||t.includes(kw);
    let okF=true;
    if(flt==='private')okF=c.dataset.private==='true';
    else if(flt==='public')okF=c.dataset.private==='false';
    else if(flt!=='all')okF=c.dataset.level===flt;
    c.classList.toggle('hide',!(okKw&&okF));
  });
  document.querySelectorAll('.cat').forEach(s=>{
    s.classList.toggle('hide',![...s.querySelectorAll('.card')].some(c=>!c.classList.contains('hide')));
  });
}
q.addEventListener('input',apply);
chips.forEach(b=>b.addEventListener('click',()=>{
  const f=b.dataset.filter;
  chips.forEach(x=>x.classList.remove('on'));b.classList.add('on');
  flt=f;apply();
}));
lkeys.forEach(b=>b.addEventListener('click',()=>{
  const f=b.dataset.level;
  flt=(flt===f)?'all':f;
  lkeys.forEach(x=>x.classList.toggle('on',x.dataset.level===flt));
  chips.forEach(x=>x.classList.toggle('on',x.dataset.filter==='all'&&flt==='all'));
  apply();
}));
"""


def write_html(recs, path, user, org, payload, hidden_total=0, note_hidden=False):
    lv = Counter(r["level"] for r in recs)
    total = len(recs)
    priv = len([r for r in recs if r["private"]])

    stats = """
  <div class="stats">
    <div class="stat"><div class="k">仓库总数</div><div class="v">{total}<small>个</small></div></div>
    <div class="stat"><div class="k">下载即装</div><div class="v" style="color:#22c55e">{a}<small>个</small></div></div>
    <div class="stat"><div class="k">源码可跑</div><div class="v" style="color:#38bdf8">{b}<small>个</small></div></div>
    <div class="stat"><div class="k">技能包</div><div class="v" style="color:#818cf8">{c}<small>个</small></div></div>
    <div class="stat"><div class="k">存档数据</div><div class="v" style="color:#94a3b8">{f}<small>个</small></div></div>
    <div class="stat"><div class="k">公开 / 私有</div><div class="v">{pub}<small>/ {priv}</small></div></div>
  </div>""".format(total=total, a=lv.get("A", 0), b=lv.get("B", 0), c=lv.get("C", 0),
                  f=lv.get("F", 0), pub=total - priv, priv=priv)

    seg = "".join('<i style="width:%.1f%%;background:%s"></i>' % (lv.get(k, 0) / total * 100, col)
                  for k, _, _, col in LEVELS if lv.get(k, 0))
    keys = "".join(
        '<span class="lkey" data-level="%s"><span class="dot" style="background:%s"></span>%s %s<b>%d</b></span>'
        % (k, col, k, name, lv.get(k, 0)) for k, name, _, col in LEVELS if lv.get(k, 0))
    levels = """
  <div class="levels">
    <div class="lt">按「能不能直接用」分布 —— 点下面任意级别可只看该级</div>
    <div class="lbar">%s</div>
    <div class="llegend">%s</div>
  </div>""" % (seg, keys)

    chips = '<button class="chip on" data-filter="all">全部 <em>%d</em></button>' % total
    chips += '<button class="chip" data-filter="private">仅私有</button>'
    chips += '<button class="chip" data-filter="public">仅公开</button>'

    def card(r):
        lcol = LEVEL_MAP[r["level"]][1]
        size_txt = ("%.1f MB" % (r["kb"] / 1024.0)) if r["kb"] >= 1024 else ("%d KB" % r["kb"])
        tags = []
        if r["fork"]:
            tags.append('<span class="tag done">fork 副本</span>')
        if r["release"]:
            tags.append('<span class="tag rel">%s</span>' % esc(r["release"]))
        if r["env_required"]:
            tags.append('<span class="tag">需配置 .env</span>')
        if r["data_assets"]:
            tags.append('<span class="tag">release 是数据快照，非程序</span>')
        for a in r["actions"][:2]:
            cls = "warn" if ("密钥" in a or "复查" in a or "未推送" in a) else ""
            tags.append('<span class="tag %s">%s</span>' % (cls, esc(a)))
        tag_html = '<div class="tags">%s</div>' % "".join(tags) if tags else ""
        bar = min(100, max(3, int(r["commits"] / 2)))
        return """
    <article class="card" data-name="{name}" data-private="{pv}" data-level="{lvl}">
      <div class="card-top">
        <span class="repo">{name}</span>
        <span class="badge {vcls}">{vis}</span>
      </div>
      <p class="desc">{desc}</p>
      <div class="lv" style="color:{lcol};border-color:{lcol}44;background:{lcol}14">{lvl} · {lname}</div>
      <p class="how">{how}</p>
      <div class="bar"><i style="width:{bar}%"></i></div>
      <div class="meta">
        <span>{commits} 次提交</span><span>{lang}</span><span>{kb}</span><span>推送 {pushed}</span>
      </div>
      {tags}
    </article>""".format(
            name=esc(r["name"]), pv="true" if r["private"] else "false", lvl=r["level"],
            vis="私有" if r["private"] else "公开",
            vcls="private" if r["private"] else "public",
            desc=esc(r["desc"]), lcol=lcol, lname=esc(r["level_name"]),
            how=esc(r["how"]), bar=bar, commits=r["commits"], lang=esc(r["lang"]),
            kb=esc(size_txt), pushed=r["pushed"], tags=tag_html)

    sections = []
    for cat, cat_desc, color in CATS:
        items = [r for r in recs if r["group"] == cat]
        if not items:
            continue
        items.sort(key=lambda x: (x["level"], -x["commits"]))
        sections.append("""
  <section class="cat" data-cat="{cat}">
    <div class="cat-head">
      <span class="dot" style="background:{col}"></span>
      <h2>{cat}</h2><span class="count">{n}</span>
      <span class="cat-desc">{cd}</span>
    </div>
    <div class="grid">{cards}</div>
  </section>""".format(cat=esc(cat), col=color, n=len(items), cd=esc(cat_desc),
                       cards="".join(card(r) for r in items)))

    now = datetime.now(TZ8).strftime("%Y-%m-%d %H:%M")
    hidden_note = ("，另 %d 个未列入展示" % hidden_total) if (note_hidden and hidden_total) else ""
    html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>项目索引 · Komo</title>
<style>%s</style>
</head>
<body>
<div class="wrap">
  <h1>项目索引</h1>
  <p class="sub">账号 <b>%s</b>%s · 共 <b>%d</b> 个仓库（独立项目 <b>%d</b> 个，其余为 fork 副本%s）
  · 数据实时抓取于 <b>%s</b> · 本页由 <code>scripts/gen_index.py</code> 生成</p>
%s
%s
  <div class="toolbar">
    <input id="q" placeholder="搜索项目名或功能…">
    %s
  </div>
%s
  <footer>
    分级口径：<b>A</b> release 里有 exe/zip 成品 · <b>B</b> 有 package.json / requirements.txt 等标准入口 ·
    <b>C</b> 含 skills/ 或 SKILL.md · <b>D</b> 独立脚本 · <b>E</b> 静态页 · <b>F</b> 无可执行内容。<br>
    分级只反映「怎么打开它」，不评价代码质量。数据源：GitHub GraphQL + Releases API 实时查询，写入 <code>_repos.json</code>。
  </footer>
</div>
<script>%s</script>
</body>
</html>""" % (CSS, esc(user), (" + 组织 <b>%s</b>" % esc(org)) if org else "",
              total, total - len([r for r in recs if r["fork"]]), hidden_note, now,
              stats, levels, chips, "".join(sections), JS)

    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return len(html)


# ---------------------------------------------------------------- 入口

def main():
    ap = argparse.ArgumentParser(description="生成 GitHub 项目索引（JSON + README + HTML）")
    ap.add_argument("--out", default=None, help="输出目录，默认脚本上级目录")
    ap.add_argument("--user", default=None, help="账号名，默认取 gh 当前登录")
    ap.add_argument("--org", default="GHZS-Project", help="组织名，留空字符串则不查组织")
    ap.add_argument("--config", default=None, help="显示配置文件，默认 scripts/index.config.json")
    ap.add_argument("--show-all", action="store_true", help="忽略隐藏配置，输出全部仓库")
    args = ap.parse_args()

    user = args.user
    if not user:
        user = gh(["api", "user", "--jq", ".login"]).decode().strip()

    out = args.out or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    org = args.org or None

    print("拉取数据：user=%s org=%s" % (user, org or "—"))
    all_recs = build_records(user, org)
    print("得到 %d 个仓库" % len(all_recs))

    cfg, cfg_path = load_config(args.config)
    if args.show_all:
        cfg = dict(cfg, hide_prefixes=[], hide_repos=[], hide_private=False)
        print("--show-all 已生效：本次忽略隐藏配置")
    recs, hidden = mark_hidden(all_recs, cfg)
    if hidden:
        by = Counter(r["hide_by"] for r in hidden)
        print("按配置隐藏 %d 个（%s）" % (
            len(hidden), "，".join("%s %d" % (k, v) for k, v in sorted(by.items()))))
        print("  隐藏名单：%s" % "、".join("%s/%s" % (r["owner"], r["name"]) for r in hidden))
    print("实际展示 %d 个 · 配置 %s" % (len(recs), cfg_path))

    pj = os.path.join(out, "_repos.json")
    pm = os.path.join(out, "README.md")
    ph = os.path.join(out, "index.html")
    note = bool(cfg.get("note_hidden"))
    payload = write_json(recs, pj, user, org, hidden_total=len(hidden), cfg=cfg)
    n1 = write_readme(recs, pm, user, org, hidden_total=len(hidden), note_hidden=note)
    n2 = write_html(recs, ph, user, org, payload, hidden_total=len(hidden), note_hidden=note)

    lv = Counter(r["level"] for r in recs)
    print("\n写出：")
    for p, sz in [(pj, os.path.getsize(pj)), (pm, n1), (ph, n2)]:
        print("  %-14s %8d B" % (os.path.basename(p), sz))
    print("\n分级：")
    for k, name, _, _ in LEVELS:
        print("  %s %-6s %2d" % (k, name, lv.get(k, 0)))
    print("\n刷新完成。")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
