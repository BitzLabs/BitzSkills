#!/usr/bin/env python3
"""リリース前の横断検証ゲート。全エージェント（Claude / Codex / agy）共用。

使い方: python3 scripts/release_check.py

チェック内容:
  1. 各プラグインの3マニフェスト（Claude Code / Antigravity / Codex）の存在・name・version 整合
  2. 共有 marketplace.json の plugins[] と plugins/ 実体の整合（双方向）
  3. 全 SKILL.md の frontmatter 必須項目（name / description / metadata の version・author・created・updated）
  4. claude plugin validate .（claude CLI があれば）
  5. agy plugin validate plugins/<name>（agy CLI があれば）
  6. CLAUDE.md「委譲レジストリ」節（SSOT）と .claude/agents/*.md の整合
     （agent 実在・ティア整合・ティアはしご健全性・モデル名直書き禁止）

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


def check_delegation_registry(repo: Path) -> list[str]:
    """CLAUDE.md の「委譲レジストリ」節（委譲判断の SSOT）と実体の整合を検証する。

    検証内容:
      1. 表の委譲先セル（プレーンな agent 名）が .claude/agents/<name>.md として実在するか
      2. そのティア列の値が agent frontmatter の model と大文字小文字無視で一致し、
         かつティアはしご上に存在するか
      3. ティアはしごのトークンに重複がないか
      4. delegation-routing.md にモデル名が直書きされていないか（存在する場合のみ）
    """
    violations: list[str] = []

    claude_md = repo / "CLAUDE.md"
    if not claude_md.exists():
        return []  # CLAUDE.md（委譲レジストリの置き場）が無い環境は検査対象外＝スキップ
    lines = claude_md.read_text(encoding="utf-8").splitlines()

    # 「委譲レジストリ」見出しから次の見出しまでを抽出
    start = None
    for i, line in enumerate(lines):
        if re.match(r"^#{2,6}\s", line) and "委譲レジストリ" in line:
            start = i
            break
    if start is None:
        return []  # 委譲レジストリ節を持たない環境は検査対象外＝スキップ
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if re.match(r"^#{2,6}\s", lines[i]):
            end = i
            break
    section = lines[start:end]

    # ティアはしご抽出
    ladder_tokens: list[str] = []
    for line in section:
        if "ティアはしご" in line:
            m = re.search(r"`([^`]+)`", line)
            if m:
                ladder_tokens = [t.strip() for t in m.group(1).split(">")]
            break
    if not ladder_tokens:
        violations.append("ティアはしごが見つからない")
    lower_ladder = [t.lower() for t in ladder_tokens]
    if len(lower_ladder) != len(set(lower_ladder)):
        violations.append(f"ティアはしごに重複がある: {ladder_tokens}")

    # 表行抽出（ヘッダ・区切り行を除く）
    rows: list[list[str]] = []
    for line in section:
        s = line.strip()
        if not s.startswith("|") or "---" in s:
            continue
        cols = [c.strip() for c in s.strip("|").split("|")]
        if len(cols) < 3 or cols[0] == "役割":
            continue
        rows.append(cols)

    for cols in rows:
        dest, tier = cols[1], cols[2]
        if tier == "—":
            continue
        for token in re.findall(r"`([^`]+)`", dest):
            if "/" in token or "antigravity" in token.lower():
                continue
            agent_path = repo / ".claude" / "agents" / f"{token}.md"
            if not agent_path.exists():
                violations.append(
                    f"委譲先 agent が実在しない: `{token}`"
                    f"（{agent_path.relative_to(repo)} が無い）")
                continue
            fm = frontmatter(agent_path.read_text(encoding="utf-8"))
            mm = re.search(r"^model:\s*(\S+)", fm, re.MULTILINE)
            model = mm.group(1) if mm else None
            if model is None:
                violations.append(f"agent frontmatter に model が無い: `{token}`")
                continue
            if tier.lower() != model.lower():
                violations.append(
                    f"ティア不一致: 表は「{tier}」だが `{token}` の frontmatter model は"
                    f"「{model}」")
            elif tier.lower() not in lower_ladder:
                violations.append(f"ティア「{tier}」がティアはしご上に存在しない（`{token}`）")

    # モデル名の外部直書き禁止
    routing_path = (repo / "plugins" / "bitz-sdd" / "skills" / "sdd-implement"
                     / "references" / "delegation-routing.md")
    if routing_path.exists():
        rtext = routing_path.read_text(encoding="utf-8")
        found = set(re.findall(r"\b(opus|sonnet|haiku|fable|gemini)\b", rtext, re.IGNORECASE))
        found |= set(re.findall(r"claude-[a-z0-9-]+", rtext, re.IGNORECASE))
        if found:
            violations.append(
                f"delegation-routing.md にモデル名の直書きがある: {sorted(found)}")

    return violations


def main() -> None:
    plugin_dirs = sorted(p for p in (REPO / "plugins").iterdir() if p.is_dir())

    # 1. 3マニフェストの存在・name・version 整合
    for d in plugin_dirs:
        manifests = {
            "claude": d / ".claude-plugin" / "plugin.json",
            "agy": d / "plugin.json",
            "codex": d / ".codex-plugin" / "plugin.json",
        }
        missing = [str(p.relative_to(REPO)) for p in manifests.values() if not p.exists()]
        if missing:
            check(f"{d.name}: マニフェスト3つの存在", False, f"missing: {missing}")
            continue
        data = {
            runtime: json.loads(path.read_text(encoding="utf-8"))
            for runtime, path in manifests.items()
        }
        names = {runtime: manifest.get("name") for runtime, manifest in data.items()}
        versions = {runtime: manifest.get("version") for runtime, manifest in data.items()}
        check(
            f"{d.name}: name 一致",
            all(name == d.name for name in names.values()),
            " / ".join(f"{runtime}={name}" for runtime, name in names.items()),
        )
        check(
            f"{d.name}: version 一致",
            len(set(versions.values())) == 1 and None not in versions.values(),
            " / ".join(f"{runtime}={version}" for runtime, version in versions.items()),
        )
        codex_skills = data["codex"].get("skills")
        check(
            f"{d.name}: Codex skills パス",
            codex_skills == "./skills/" and (d / "skills").is_dir(),
            f"skills={codex_skills}",
        )

    # 2. Claude Code と Codex CLI が共用する marketplace.json と実体の整合
    mp_path = REPO / ".claude-plugin" / "marketplace.json"
    mp = json.loads(mp_path.read_text(encoding="utf-8"))
    listed = {re.sub(r"^\./plugins/", "", e["source"]) for e in mp.get("plugins", [])}
    actual = {d.name for d in plugin_dirs}
    check("共有 marketplace.json: 全プラグインを列挙", listed >= actual, f"未列挙: {sorted(actual - listed)}")
    check("共有 marketplace.json: 実体のない参照なし", listed <= actual, f"実体なし: {sorted(listed - actual)}")

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

    # 6. 委譲レジストリ（CLAUDE.md の SSOT）と実体の整合
    registry_violations = check_delegation_registry(REPO)
    if registry_violations:
        for v in registry_violations:
            check("委譲レジストリ: " + v, False)
    else:
        check("委譲レジストリ整合", True)

    print()
    for w in warnings:
        print(f"注意: {w}")
    if failures:
        print(f"\n結果: FAIL（{len(failures)} 件）")
        sys.exit(1)
    print("\n結果: PASS（全チェック合格）")


if __name__ == "__main__":
    main()
