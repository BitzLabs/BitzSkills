#!/usr/bin/env python3
"""プラグインの version を2つのマニフェストで同時に bump する。

使い方: python3 scripts/bump_version.py <plugin名> [major|minor|patch]

対象:
  plugins/<name>/.claude-plugin/plugin.json  (Claude Code 用)
  plugins/<name>/plugin.json                 (Antigravity 2.0 用)

両ファイルは常に同じ version でなければならない (AGENTS.md 規約)。
bump 後、配下スキルの metadata.updated が古いままの場合は警告する。
"""
import json
import re
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def bump(version: str, part: str) -> str:
    m = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", version)
    if not m:
        sys.exit(f"エラー: semver として解釈できません: {version}")
    major, minor, patch = map(int, m.groups())
    if part == "major":
        return f"{major + 1}.0.0"
    if part == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        sys.exit(__doc__)
    name = sys.argv[1]
    part = sys.argv[2] if len(sys.argv) > 2 else "patch"
    if part not in ("major", "minor", "patch"):
        sys.exit(f"エラー: bump 種別は major|minor|patch のいずれか: {part}")

    plugin_dir = REPO / "plugins" / name
    manifests = [plugin_dir / ".claude-plugin" / "plugin.json", plugin_dir / "plugin.json"]
    for p in manifests:
        if not p.exists():
            sys.exit(f"エラー: マニフェストがありません: {p.relative_to(REPO)}")

    data = {p: json.loads(p.read_text(encoding="utf-8")) for p in manifests}
    versions = {d.get("version") for d in data.values()}
    if len(versions) > 1:
        print(f"警告: 2マニフェストの version が不一致でした {sorted(versions)} — 大きい方を基準にします")
    base = max(versions, key=lambda v: [int(x) for x in v.split(".")])
    new = bump(base, part)

    for p, d in data.items():
        d["version"] = new
        p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"  {p.relative_to(REPO)}: {base} -> {new}")

    today = date.today().isoformat()
    stale = []
    for skill_md in sorted(plugin_dir.glob("skills/*/SKILL.md")):
        text = skill_md.read_text(encoding="utf-8")
        m = re.search(r"^\s*updated:\s*[\"']?(\d{4}-\d{2}-\d{2})", text, re.MULTILINE)
        if m and m.group(1) != today:
            stale.append(f"{skill_md.relative_to(REPO)} (updated: {m.group(1)})")
    if stale:
        print("\n注意: 今日変更したスキルがあれば、frontmatter の metadata (version/updated) も更新すること:")
        for s in stale:
            print(f"  - {s}")

    print(f"\n完了: {name} を {new} に bump しました（2マニフェスト同値）")


if __name__ == "__main__":
    main()
