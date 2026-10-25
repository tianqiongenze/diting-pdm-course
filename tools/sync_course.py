"""上游 Diting-PdM 变更 → 课程仓库同步。

设计：
- `--check`  只读：报告上游新提交、受影响讲次/文件、关键事实漂移
- `--apply`  写入：更新 sync/upstream-state.json、PROJECT_UPDATES.md、
             并在 11_项目案例库与代码导览.md 的 AUTO-SNAPSHOT 区块刷新事实快照
- `--init`   首次建立基线（不写更新记录）

为什么不做「全自动改写正文」：
课程正文是教学语言，不是数据搬运；自动改写会把「为什么这么教」改没。
因此脚本负责「发现 + 定位 + 记录 + 快照」，正文修订由人按 PROJECT_UPDATES.md 的清单完成。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "sync" / "upstream-state.json"
MAP = ROOT / "sync" / "upstream-map.yaml"
UPDATES = ROOT / "PROJECT_UPDATES.md"
CASE_DOC = ROOT / "11_项目案例库与代码导览.md"
SNAP_START = "<!-- AUTO-SNAPSHOT:START -->"
SNAP_END = "<!-- AUTO-SNAPSHOT:END -->"


def sh(args: list[str], cwd: Path) -> str:
    return subprocess.run(args, cwd=str(cwd), capture_output=True, text=True,
                          encoding="utf-8", errors="replace").stdout.strip()


def load_map() -> dict:
    if yaml is None:
        sys.exit("需要 PyYAML：pip install pyyaml")
    return yaml.safe_load(MAP.read_text(encoding="utf-8"))


def load_state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {"last_commit": "", "last_sync_at": "", "files": {}, "facts": {}}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def git_changed(upstream: Path, since: str) -> list[tuple[str, str]]:
    if not since:
        return []
    out = sh(["git", "diff", "--name-status", f"{since}..HEAD"], upstream)
    rows = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            rows.append((parts[0], parts[-1]))
    return rows


def extract_facts(cfg: dict, upstream: Path, prev: dict) -> tuple[dict, list[str]]:
    facts, drift = {}, []
    for name, spec in (cfg.get("facts") or {}).items():
        pattern = spec["pattern"]
        value = None
        if pattern == "COUNT_DOCS":
            docs = upstream / "docs"
            value = str(len(list(docs.glob("*.md")))) if docs.exists() else None
        else:
            for src in spec.get("sources", []):
                p = upstream / src
                if not p.is_file():
                    continue
                m = re.search(pattern, p.read_text(encoding="utf-8", errors="replace"))
                if m:
                    value = m.group(1)
                    break
        if value is None:
            continue
        facts[name] = value
        old = prev.get(name)
        if old and old != value:
            drift.append(f"{name}: {old} → {value}")
    return facts, drift


def render_snapshot(facts: dict, commit: str, when: str) -> str:
    labels = {
        "unit_tests": ("单元测试", "项"),
        "browser_tests": ("浏览器用例", "项"),
        "doc_count": ("工程文档", "份"),
        "image_version": ("镜像版本", ""),
    }
    lines = [SNAP_START, "", "### 项目事实快照（自动生成，勿手改）", "",
             "| 指标 | 当前值 | 来源 |", "|---|---|---|"]
    for k, v in facts.items():
        label, unit = labels.get(k, (k, ""))
        lines.append(f"| {label} | {v}{unit} | 上游 commit `{commit[:7]}` |")
    lines += ["", f"> 同步时间：{when} ｜ 执行 `python tools/sync_course.py --apply` 可刷新", "", SNAP_END]
    return "\n".join(lines)


def write_snapshot(facts: dict, commit: str, when: str) -> bool:
    text = CASE_DOC.read_text(encoding="utf-8")
    block = render_snapshot(facts, commit, when)
    if SNAP_START in text and SNAP_END in text:
        start = text.index(SNAP_START)
        end = text.index(SNAP_END) + len(SNAP_END)
        new = text[:start] + block + text[end:]
    else:
        anchor = "## 7. 数据与指标引用规范（防止课堂讲旧数据）"
        new = text.replace(anchor, anchor + "\n\n" + block + "\n") if anchor in text else text + "\n\n" + block + "\n"
    if new != text:
        CASE_DOC.write_text(new, encoding="utf-8")
        return True
    return False


def append_updates(changes: list[tuple[str, str]], mapping: dict, drift: list[str],
                   old_commit: str, new_commit: str, when: str) -> None:
    if not UPDATES.exists():
        UPDATES.write_text("# 项目更新同步记录\n\n> 只追加，不修改历史行。\n", encoding="utf-8")
    decks, files, unmapped = set(), set(), []
    for status, path in changes:
        item = mapping.get(path)
        if item:
            decks.update(item.get("decks") or [])
            files.update(item.get("files") or [])
        else:
            unmapped.append(f"{status} {path}")

    lines = [f"\n## {when} ｜ 上游 `{old_commit[:7] or 'init'}` → `{new_commit[:7]}`", ""]
    lines.append(f"- 变更文件：**{len(changes)}** 个")
    lines.append(f"- 受影响讲次：{', '.join(f'第 {d:02d} 讲' for d in sorted(decks)) or '无'}")
    lines.append(f"- 需同步的课程文件：{', '.join(sorted(files)) or '无'}")
    if drift:
        lines.append("- **关键事实漂移（必须人工核对）**：")
        for d in drift:
            lines.append(f"  - {d}")
    if unmapped:
        lines.append(f"- 未映射的上游变更（需人工判断）：{len(unmapped)} 个")
        for u in unmapped[:20]:
            lines.append(f"  - `{u}`")
    lines.append("")
    lines.append("### 同步清单（完成后勾选）")
    for f in sorted(files):
        lines.append(f"- [ ] 核对并更新 `{f}`")
    for d in sorted(decks):
        lines.append(f"- [ ] 重新生成第 {d:02d} 讲课件（`python tools/build_slides.py --only {d}`）")
    lines.append("")
    with UPDATES.open("a", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--init", action="store_true")
    ap.add_argument("--snapshot", action="store_true", help="仅刷新 11 号文档的事实快照")
    ap.add_argument("--upstream", default="")
    args = ap.parse_args()

    cfg = load_map()
    upstream = Path(args.upstream) if args.upstream else (ROOT / cfg["upstream"]["path"]).resolve()
    if not (upstream / ".git").exists():
        sys.exit(f"上游仓库不存在或不是 git 仓库：{upstream}")

    head = sh(["git", "rev-parse", "HEAD"], upstream)
    head_msg = sh(["git", "log", "-1", "--format=%h %ad %s", "--date=short"], upstream)
    state = load_state()
    since = state.get("last_commit", "")

    if args.snapshot:
        facts, _ = extract_facts(cfg, upstream, {})
        when = datetime.now().strftime("%Y-%m-%d %H:%M")
        ok = write_snapshot(facts, head, when)
        print(f"[snapshot] {'已刷新' if ok else '无变化'}：{facts}")
        return

    if args.init:
        state = {"last_commit": head, "last_sync_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                 "files": {}, "facts": {}}
        facts, _ = extract_facts(cfg, upstream, {})
        state["facts"] = facts
        skip = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache",
                "browser_test_shots", "export", "wheels"}
        for p in upstream.rglob("*"):
            if not p.is_file():
                continue
            if skip & set(p.parts):
                continue
            state["files"][str(p.relative_to(upstream))] = sha256(p)
        STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[init] baseline = {head[:7]} ({head_msg})")
        print(f"[init] tracked files = {len(state['files'])}, facts = {facts}")
        return

    changes = git_changed(upstream, since)
    facts, drift = extract_facts(cfg, upstream, state.get("facts", {}))

    print(f"upstream : {upstream}")
    print(f"head     : {head[:7]}  {head_msg}")
    print(f"baseline : {since[:7] or '(none)'}")
    print(f"changes  : {len(changes)}")
    if changes:
        mapping = cfg.get("map") or {}
        for status, path in changes[:40]:
            item = mapping.get(path)
            tag = f"→ decks {item['decks']}" if item else "→ (unmapped)"
            print(f"  {status:2} {path}  {tag}")
    if drift:
        print("fact drift:")
        for d in drift:
            print("  !", d)
    if not changes and not drift:
        print("课程与上游一致，无需同步。")

    if args.check or not args.apply:
        return
    if not changes and not drift:
        return

    when = datetime.now().strftime("%Y-%m-%d %H:%M")
    append_updates(changes, cfg.get("map") or {}, drift, since, head, when)
    changed_snap = write_snapshot(facts, head, when)
    state.update({"last_commit": head, "last_sync_at": when, "facts": facts})
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[apply] 已追加 {UPDATES.name}；快照{'已刷新' if changed_snap else '无变化'}；state 已更新。")


if __name__ == "__main__":
    main()
