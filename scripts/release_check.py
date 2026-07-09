#!/usr/bin/env python3
"""リリース前の横断検証ゲート。全エージェント（Claude / Codex / agy）共用。

使い方: python3 scripts/release_check.py

チェック内容:
  1. 各プラグインの2マニフェスト（.claude-plugin/plugin.json と plugin.json）の version 一致
  2. marketplace.json の plugins[] と plugins/ 実体の整合（双方向）
  3. 全 SKILL.md の frontmatter 必須項目（name / description / metadata の version・author・created・updated）
  4. claude plugin validate .（claude CLI があれば）
  5. agy plugin validate plugins/<name>（agy CLI があれば）

すべて合格なら exit 0、1つでも FAIL があれば exit 1。
"""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
failures: list[str] = []
warnings: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {label}" + (f" — {detail}" if detail else ""))
    if not ok:
        failures.append(label + (f": {detail}" if detail else ""))


def frontmatter(text: str) -> str:
    m = re.match(r"\A---\n(.*?)\n---\n", text, re.DOTALL)
    return m.group(1) if m else ""


def main() -> None:
    plugin_dirs = sorted(p for p in (REPO / "plugins").iterdir() if p.is_dir())

    # 1. 2マニフェストの version 一致
    for d in plugin_dirs:
        cc, agy = d / ".claude-plugin" / "plugin.json", d / "plugin.json"
        if not cc.exists() or not agy.exists():
            check(f"{d.name}: マニフェスト2つの存在", False,
                  f"missing: {[p.name for p in (cc, agy) if not p.exists()]}")
            continue
        v1 = json.loads(cc.read_text(encoding="utf-8")).get("version")
        v2 = json.loads(agy.read_text(encoding="utf-8")).get("version")
        check(f"{d.name}: version 一致", v1 == v2 and v1 is not None, f"claude={v1} / agy={v2}")

    # 2. marketplace.json と実体の整合
    mp_path = REPO / ".claude-plugin" / "marketplace.json"
    mp = json.loads(mp_path.read_text(encoding="utf-8"))
    listed = {re.sub(r"^\./plugins/", "", e["source"]) for e in mp.get("plugins", [])}
    actual = {d.name for d in plugin_dirs}
    check("marketplace.json: 全プラグインを列挙", listed >= actual, f"未列挙: {sorted(actual - listed)}")
    check("marketplace.json: 実体のない参照なし", listed <= actual, f"実体なし: {sorted(listed - actual)}")

    # 3. SKILL.md frontmatter 必須項目
    required_meta = ("version:", "author:", "created:", "updated:")
    for skill_md in sorted(REPO.glob("plugins/*/skills/*/SKILL.md")):
        fm = frontmatter(skill_md.read_text(encoding="utf-8"))
        rel = str(skill_md.relative_to(REPO))
        missing = [k for k in ("name:", "description:") if k not in fm]
        if "metadata:" not in fm:
            missing.append("metadata:")
        else:
            missing += [k for k in required_meta if k not in fm]
        check(f"frontmatter: {rel}", not missing, f"欠落: {missing}" if missing else "")

    # 4. / 5. CLI validate（インストールされている場合のみ）
    for cli, cmds in (
        ("claude", [["claude", "plugin", "validate", "."]]),
        ("agy", [["agy", "plugin", "validate", f"plugins/{d.name}"] for d in plugin_dirs]),
    ):
        if not shutil.which(cli):
            warnings.append(f"{cli} CLI が見つからないためスキップ")
            print(f"[SKIP] {cli} plugin validate — CLI 未検出")
            continue
        for cmd in cmds:
            r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, timeout=120)
            tail = (r.stdout + r.stderr).strip().splitlines()
            check(" ".join(cmd), r.returncode == 0, tail[-1] if tail and r.returncode != 0 else "")

    print()
    for w in warnings:
        print(f"注意: {w}")
    if failures:
        print(f"\n結果: FAIL（{len(failures)} 件）")
        sys.exit(1)
    print("\n結果: PASS（全チェック合格）")


if __name__ == "__main__":
    main()
