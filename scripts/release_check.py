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
  7. マニフェスト metadata.dependencies のプラグイン間依存グラフ検証
     （3マニフェスト同値・依存先の実在・semver 制約の充足・循環の不在。CORE-FR-013）
  8. 対訳辞書 spec_labels.py の SSOT（sdd-core）と複製（sdd-report）の一致（SDD-FR-137）
  9. フェーズ正規語彙 PHASE_CODES（spec_status.py）と文書側マーカーの一致（SDD-FR-140）
     （sdd-core SKILL.md / gates.md の phase-vocabulary マーカー・散文リストとの一致）

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


DEP_RE = re.compile(r"^(?P<name>[A-Za-z0-9_-]+)(?:(?P<op>>=|<=|==|>|<)(?P<ver>[0-9][0-9A-Za-z.-]*))?$")


def check_label_dictionary_copies(repo: Path) -> None:
    """対訳辞書 spec_labels.py の SSOT（sdd-core）と複製（sdd-report）の一致を検証する。

    AGENTS.md のスキル自己完結原則により sdd-report は sdd-core を相対参照せず複製を持つ
    （SI-CORE-018 の辞書配置裁定）。複製が乖離すると表示が種別ごとに食い違うため、
    ここで機械検証して乖離を CI で落とす（SDD-FR-137）。
    """
    ssot = repo / "plugins/bitz-sdd/skills/sdd-core/scripts/spec_labels.py"
    copies = [repo / "plugins/bitz-sdd/skills/sdd-report/scripts/spec_labels.py"]

    if not (repo / "plugins" / "bitz-sdd").exists():
        print("[SKIP] 対訳辞書の複製一致 — bitz-sdd プラグイン未配置")
        return

    if not ssot.exists():
        check("対訳辞書 SSOT の存在", False, f"{ssot.relative_to(repo)} が無い")
        return

    for copy in copies:
        rel = copy.relative_to(repo)
        if not copy.exists():
            check(f"対訳辞書の複製: {rel}", False, "複製が存在しない")
        elif copy.read_bytes() != ssot.read_bytes():
            check(f"対訳辞書の複製: {rel}", False,
                  "SSOT（sdd-core/scripts/spec_labels.py）と内容が一致しない — 両方を同時に更新すること")
        else:
            check(f"対訳辞書の複製: {rel}", True, "SSOT と一致")


PHASE_MARKER_RE = re.compile(r"<!--\s*phase-vocabulary:\s*(.*?)-->", re.DOTALL)


def _phase_codes_from_source(status_py: Path) -> list[str] | None:
    """spec_status.py のソースから PHASE_CODES の語を抽出する（import せず副作用を避ける）。"""
    m = re.search(r"PHASE_CODES\s*=\s*\(([^)]*)\)", status_py.read_text(encoding="utf-8"))
    if not m:
        return None
    return [w.strip().strip("\"'") for w in m.group(1).split(",") if w.strip().strip("\"'")]


def check_phase_vocabulary(repo: Path) -> None:
    """フェーズ正規語彙 PHASE_CODES（コード）と文書側マーカーの一致を検証する（SDD-FR-140）。

    sdd-core/SKILL.md と references/gates.md に置いた HTML コメントマーカー
    `<!-- phase-vocabulary: ... -->` から語集合を抽出し、`spec_status.py` の PHASE_CODES と
    過不足なく一致することを検査する。加えて、各文書に人間可読で併記された散文リスト
    （バッククォートのスラッシュ区切り）がマーカーと一致することを境界付き文字列比較で確認し、
    可視リストの静かなドリフトも検出する（自由文からの語推定はしない。SI-CORE-033 の裁定）。
    """
    if not (repo / "plugins" / "bitz-sdd").exists():
        print("[SKIP] フェーズ語彙の一致 — bitz-sdd プラグイン未配置")
        return

    status_py = repo / "plugins/bitz-sdd/skills/sdd-core/scripts/spec_status.py"
    if not status_py.exists():
        check("フェーズ語彙 SSOT の存在", False, f"{status_py.relative_to(repo)} が無い")
        return
    phase_codes = _phase_codes_from_source(status_py)
    if not phase_codes:
        check("PHASE_CODES 抽出", False, "spec_status.py から PHASE_CODES を抽出できない")
        return
    canonical = set(phase_codes)

    docs = [
        repo / "plugins/bitz-sdd/skills/sdd-core/SKILL.md",
        repo / "plugins/bitz-sdd/skills/sdd-core/references/gates.md",
    ]
    for doc in docs:
        rel = doc.relative_to(repo)
        if not doc.exists():
            check(f"フェーズ語彙マーカー: {rel}", False, "対象文書が無い")
            continue
        text = doc.read_text(encoding="utf-8")
        mk = PHASE_MARKER_RE.search(text)
        if not mk:
            check(f"フェーズ語彙マーカー: {rel}", False,
                  "<!-- phase-vocabulary: ... --> マーカーが無い")
            continue
        words = [w.strip() for w in mk.group(1).replace("\n", " ").split(",") if w.strip()]
        marker_set = set(words)
        if len(words) != len(marker_set):
            check(f"フェーズ語彙マーカー: {rel}", False, "マーカー内に重複語がある")
        elif marker_set != canonical:
            missing = sorted(canonical - marker_set)
            extra = sorted(marker_set - canonical)
            check(f"フェーズ語彙マーカー: {rel}", False,
                  f"PHASE_CODES と不一致 — 欠落{missing} 余剰{extra}（PHASE_CODES と同時に更新すること）")
        else:
            # 可視の散文リスト（`w / w / ...`）がマーカーと一致するか（境界付き・語推定なし）
            normalized = re.sub(r"\s+", " ", text)
            expected_span = "`" + " / ".join(words) + "`"
            if expected_span not in normalized:
                check(f"フェーズ語彙マーカー: {rel}", False,
                      f"可視の散文リストがマーカーと不一致（期待: {expected_span}）")
            else:
                check(f"フェーズ語彙マーカー: {rel}", True, "PHASE_CODES・散文リストと一致")


def parse_version(text: str) -> tuple[int, ...]:
    """semver 文字列を比較用タプルへ変換する（"1.4" のような部分指定も受理）"""
    return tuple(int(p) for p in re.findall(r"\d+", text)) or (0,)


def constraint_satisfied(op: str, actual: str, required: str) -> bool:
    a, r = parse_version(actual), parse_version(required)
    # 部分指定（例 >=1.4）は指定された桁までで比較する
    a_cmp = a[: len(r)] if len(a) > len(r) else a
    ops = {
        ">=": a_cmp >= r, "<=": a_cmp <= r, "==": a_cmp == r,
        ">": a_cmp > r, "<": a_cmp < r,
    }
    return ops[op]


def check_dependencies(plugin_manifests: dict[str, dict[str, dict]]) -> None:
    """metadata.dependencies のプラグイン間依存グラフを検証する（CORE-FR-013）。

    plugin_manifests: {plugin名: {runtime: マニフェスト dict}}
    依存宣言を持たないプラグインについては何も報告しない（後方互換）。
    """
    graph: dict[str, list[str]] = {}
    for name, manifests in sorted(plugin_manifests.items()):
        declared = {
            runtime: (manifest.get("metadata") or {}).get("dependencies")
            for runtime, manifest in manifests.items()
        }
        if all(deps is None for deps in declared.values()):
            continue  # 宣言なし＝検証対象外（後方互換）
        values = list(declared.values())
        check(
            f"{name}: metadata.dependencies 一致",
            all(v == values[0] for v in values),
            " / ".join(f"{rt}={deps}" for rt, deps in declared.items()),
        )
        deps = next((v for v in values if v is not None), [])
        graph[name] = []
        for entry in deps:
            m = DEP_RE.match(entry)
            if not m:
                check(f"{name}: 依存宣言の書式", False, f"解釈不能: {entry!r}")
                continue
            dep_name = m.group("name")
            graph[name].append(dep_name)
            target = plugin_manifests.get(dep_name)
            check(
                f"{name}: 依存先 {dep_name} の実在",
                target is not None,
                "" if target else f"plugins/{dep_name} が無い",
            )
            if target and m.group("op"):
                actual = target["claude"].get("version") or ""
                check(
                    f"{name}: 依存 {entry} の semver 制約",
                    constraint_satisfied(m.group("op"), actual, m.group("ver")),
                    f"{dep_name} の現行 version は {actual}",
                )

    # 循環検出（DFS。宣言を持つプラグインから辿る）
    def find_cycle(node: str, path: list[str]) -> list[str] | None:
        if node in path:
            return path[path.index(node):] + [node]
        for nxt in graph.get(node, []):
            found = find_cycle(nxt, path + [node])
            if found:
                return found
        return None

    for start in graph:
        cycle = find_cycle(start, [])
        if cycle:
            check("依存グラフ: 循環なし", False, " → ".join(cycle))
            break
    else:
        if graph:
            check("依存グラフ: 循環なし", True)


def main() -> None:
    plugin_dirs = sorted(p for p in (REPO / "plugins").iterdir() if p.is_dir())
    plugin_manifests: dict[str, dict[str, dict]] = {}

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
        plugin_manifests[d.name] = data
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

    # 7. プラグイン間依存グラフ（metadata.dependencies）
    check_dependencies(plugin_manifests)

    # 8. 対訳辞書 SSOT と複製の一致（SDD-FR-137）
    check_label_dictionary_copies(REPO)

    # 9. フェーズ正規語彙 PHASE_CODES と文書側マーカーの一致（SDD-FR-140）
    check_phase_vocabulary(REPO)

    print()
    for w in warnings:
        print(f"注意: {w}")
    if failures:
        print(f"\n結果: FAIL（{len(failures)} 件）")
        sys.exit(1)
    print("\n結果: PASS（全チェック合格）")


if __name__ == "__main__":
    main()
