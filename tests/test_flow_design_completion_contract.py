"""FLW-CON-008 設計完了判定の実証義務を機械検証する。

`FLW-REV-026` が PASS 4.96・P0〜P3 全 0 件で `FLW-GATE-005` を通過した翌日に
`FLW-REV-027` が FAIL 2.12 となった。原因は、設計レビューの高評価を production 経路の
実行可能性と同一視したことである。`FLW-DSN-017` v2.2 §8.1 は接続順を表として書いていたが、
その行が production 既定 dispatcher から到達するかは誰も検査していなかった。

本テストは `FLW-CON-008` を機械検証へ落とし、同じ見落としが次の Design Gate で
再現しないようにする。検査対象は **`implements` に `FLW-CON-008` を宣言した設計**と、
**その設計を `scope` に含む design GatePassage** である。対象が空になった場合は
黙って通さず FAIL させる（規範が骨抜きになったことを検出するため）。
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SPEC = REPO_ROOT / "plugins" / "bitz-flow" / ".spec"
TESTS = REPO_ROOT / "tests"
PLATFORM_REGISTRY = (
    REPO_ROOT / "plugins" / "bitz-flow" / "skills" / "flow-core"
    / "references" / "worktree-v2-platform-support.json"
)

REQUIREMENT_ID = "FLW-CON-008"

#: §13 の 6 表。見出し → 必須列。
REQUIRED_TABLES: dict[str, tuple[str, ...]] = {
    "垂直接続図": (
        "production入口", "経由component", "最終永続証跡", "利用者出力",
        "所有task", "production test ID",
    ),
    "状態遷移意味表": ("状態", "前提", "永続証跡", "許される後続処理", "禁止される完了判定"),
    "crash-point表": (
        "durable write", "直前で停止", "直後で停止", "authority", "再開処理",
        "重複実行時の結果",
    ),
    "liveness budget表": ("対象", "deadline", "kill手順", "出力回収", "terminal result"),
    "platform reality表": (
        "実装component", "identity", "probe方法", "未対応時の即時拒否",
    ),
    "legacy exclusion表": (
        "廃止対象", "所在", "production入口からの到達可否", "即時拒否の写像",
        "negative test ID",
    ),
}

#: FLW-CON-008 が GatePassage へ要求する 7 観点。
SEVEN_CRITERIA = (
    "接続完全性", "失敗原子性", "有限収束性", "platform実在性",
    "証跡妥当性", "legacy排除", "状態意味保存",
)

#: 未証明を表す語。いずれかであれば PASS 根拠にしていないとみなす。
UNPROVEN_MARKERS = ("未実装境界", "検証計画", "未実装")

#: 接続の成立根拠にしてはならない注入口（fixture 専用）。
FIXTURE_INJECTION_MARKERS = ("handlers=", "_GATED_HANDLERS")


# --- frontmatter / markdown --------------------------------------------------


def _frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}
    end = text.index("\n---", 4)
    fields: dict[str, str] = {}
    key = None
    for line in text[4:end].splitlines():
        if re.match(r"^\s+\S", line) and key:      # 継続行（origin の折返し等）
            fields[key] += " " + line.strip()
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        fields[key] = value.strip()
    return fields


def _id_list(value: str) -> list[str]:
    return [part.strip() for part in re.split(r"[,\s]+", value) if part.strip()]


def _table_rows(text: str, heading: str) -> tuple[list[str], list[list[str]]]:
    """`### <n> <heading>` 直下の最初の markdown 表を (ヘッダ, データ行) で返す。"""
    match = re.search(rf"^###\s+\S+\s+{re.escape(heading)}\s*$", text, re.M)
    if match is None:
        raise AssertionError(f"見出しが無い: {heading}")
    section = text[match.end():]
    nxt = re.search(r"^#{2,3}\s", section, re.M)
    if nxt:
        section = section[: nxt.start()]
    # セクション内の全パイプ行を拾うと、後続の別表まで同じ表として読んでしまう。
    # 最初の連続ブロックだけを表とみなす。
    lines: list[str] = []
    for raw in section.splitlines():
        stripped = raw.strip()
        if stripped.startswith("|"):
            lines.append(stripped)
        elif lines:
            break
    if not lines:
        raise AssertionError(f"表が無い: {heading}")
    def cells(line: str) -> list[str]:
        return [c.strip() for c in line.strip().strip("|").split("|")]
    header = cells(lines[0])
    rows = [cells(ln) for ln in lines[1:] if not re.fullmatch(r"[|\s:-]+", ln)]
    return header, rows


# --- 対象の収集 --------------------------------------------------------------


def _bound_designs() -> list[Path]:
    return sorted(
        p for p in (SPEC / "design").glob("*.md")
        if REQUIREMENT_ID in _id_list(_frontmatter(p).get("implements", ""))
    )


def _requirement_effective_date() -> str:
    """規範の発効日 = FLW-CON-008 の Revision History 1.0 の日付。

    ハードコードせず要件から読むことで、要件を差し替えても適用境界が追随する。
    """
    text = (SPEC / "requirements" / f"{REQUIREMENT_ID}.md").read_text(encoding="utf-8")
    match = re.search(r"^\s*-\s*1\.0\s*\((\d{4}-\d{2}-\d{2})\)", text, re.M)
    assert match, f"{REQUIREMENT_ID} の Revision History から 1.0 の日付を読めない"
    return match.group(1)


def _design_gates_for(designs: set[str]) -> list[Path]:
    """対象設計を scope に含む design GatePassage のうち、規範発効日以降のもの。

    FLW-CON-008 は 2026-08-24 に起票された規範であり、それ以前に人間が裁定した
    GatePassage（FLW-GATE-001〜005）へ遡及適用しない。遡及させると、当時の
    チェックリストで正しく裁定された記録を後から FAIL にしてしまう。
    """
    effective = _requirement_effective_date()
    gates = []
    for path in sorted((SPEC / "gates").glob("*.md")):
        fm = _frontmatter(path)
        if fm.get("gate") != "design":
            continue
        if fm.get("date", "") < effective:
            continue
        scope = set(_id_list(fm.get("scope", "").strip("[]")))
        if scope & designs:
            gates.append(path)
    return gates


BOUND_DESIGNS = _bound_designs()


def test_requirement_exists_and_is_bound_to_at_least_one_design():
    """規範が骨抜きになっていないこと（対象 0 件を黙って通さない）。"""
    assert (SPEC / "requirements" / f"{REQUIREMENT_ID}.md").exists(), (
        f"{REQUIREMENT_ID} が存在しない"
    )
    assert BOUND_DESIGNS, (
        f"{REQUIREMENT_ID} を implements に宣言した設計が 1 件も無い。"
        "規範が適用対象を失っている"
    )


@pytest.mark.parametrize("design", BOUND_DESIGNS, ids=lambda p: p.stem)
@pytest.mark.parametrize("heading,columns", list(REQUIRED_TABLES.items()))
def test_bound_design_declares_required_table_with_columns(design, heading, columns):
    """6 表が実在し、必須列をすべて持つこと。"""
    header, rows = _table_rows(design.read_text(encoding="utf-8"), heading)
    joined = " | ".join(header)
    missing = [c for c in columns if c not in joined]
    assert not missing, f"{design.name} §{heading}: 必須列が欠落 {missing}（実際: {header}）"
    assert rows, f"{design.name} §{heading}: データ行が無い"


# --- 13.1 垂直接続図: production test ID の実在と非 fixture 性 ----------------


def _cited_test_ids(design: Path) -> list[tuple[str, str]]:
    """(行ラベル, test ID) を返す。`未実装` の行は返さない。"""
    header, rows = _table_rows(design.read_text(encoding="utf-8"), "垂直接続図")
    column = next(i for i, c in enumerate(header) if "production test ID" in c)
    cited = []
    for row in rows:
        if len(row) <= column:
            continue
        cell = row[column]
        if any(marker in cell for marker in UNPROVEN_MARKERS):
            continue
        for span in re.findall(r"`([^`]+)`", cell):
            cited.append((row[1] if len(row) > 1 else row[0], span))
    return cited


def _resolve(test_id: str) -> tuple[Path, str | None]:
    file_part, _, func = test_id.partition("::")
    return REPO_ROOT / file_part, (func or None)


def _resolution_problem(test_id: str) -> str | None:
    """test ID が実体へ解決できない理由を返す（解決できれば None）。

    file の実在だけでは足りない。`file.py::関数名` 形式で関数が存在しない場合を
    見逃すと、実在する file 名に架空の関数名を添えた ID が通ってしまう。
    """
    path, func = _resolve(test_id)
    if not path.exists():
        return f"file 不在 {test_id}"
    if func is None:
        return None
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = {
        n.name for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    return None if func in names else f"関数不在 {test_id}"


@pytest.mark.parametrize("design", BOUND_DESIGNS, ids=lambda p: p.stem)
def test_vertical_table_cites_only_existing_tests(design):
    """名指しした production test が実在すること（架空 ID を許さない）。"""
    problems = []
    for label, test_id in _cited_test_ids(design):
        reason = _resolution_problem(test_id)
        if reason:
            problems.append(f"{label}: {reason}")
    assert not problems, f"{design.name} §13.1 の test 参照が実体と一致しない: {problems}"


@pytest.mark.parametrize("design", BOUND_DESIGNS, ids=lambda p: p.stem)
def test_vertical_table_does_not_cite_fixture_injection_tests(design):
    """fixture 注入 test を production 接続の根拠にしていないこと。

    `cli.main(handlers=...)` は fixture 専用の注入口である（`SI-FLW-059`）。
    これを起点にした test は「production 既定 dispatcher から到達する」ことを
    証明しないため、垂直接続図の根拠にできない。
    """
    problems = []
    for label, test_id in _cited_test_ids(design):
        path, func = _resolve(test_id)
        if not path.exists():
            continue                      # 実在検査は別テストの責務
        source = path.read_text(encoding="utf-8")
        if func is not None:
            tree = ast.parse(source)
            node = next(
                (n for n in ast.walk(tree)
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == func),
                None,
            )
            if node is None:
                continue
            source = ast.get_source_segment(source, node) or ""
        hits = [m for m in FIXTURE_INJECTION_MARKERS if m in source]
        if hits:
            problems.append(f"{label}: {test_id} が fixture 注入を使用 {hits}")
    assert not problems, (
        f"{design.name} §13.1 が fixture 注入 test を接続根拠にしている: {problems}"
    )


# --- 13.2 状態遷移意味表 -----------------------------------------------------


@pytest.mark.parametrize("design", BOUND_DESIGNS, ids=lambda p: p.stem)
def test_state_semantics_table_covers_all_terminal_states(design):
    """DONE / QUARANTINED / INDETERMINATE / BLOCKED の 4 状態を漏らさないこと。"""
    _, rows = _table_rows(design.read_text(encoding="utf-8"), "状態遷移意味表")
    declared = " ".join(row[0] for row in rows)
    missing = [s for s in ("DONE", "QUARANTINED", "INDETERMINATE", "BLOCKED")
               if s not in declared]
    assert not missing, f"{design.name} §13.2: 状態が欠落 {missing}"


# --- 13.4 liveness budget ----------------------------------------------------


@pytest.mark.parametrize("design", BOUND_DESIGNS, ids=lambda p: p.stem)
def test_liveness_budget_declares_numeric_deadlines(design):
    """deadline と最大応答が数値で書かれていること（定性的表現を許さない）。"""
    header, rows = _table_rows(design.read_text(encoding="utf-8"), "liveness budget表")
    deadline = next(i for i, c in enumerate(header) if "deadline" in c)
    problems = [
        row[0] for row in rows
        if len(row) > deadline and not re.search(r"\d", row[deadline])
    ]
    assert not problems, f"{design.name} §13.4: deadline が数値でない行 {problems}"


# --- 13.5 platform reality ---------------------------------------------------


@pytest.mark.parametrize("design", BOUND_DESIGNS, ids=lambda p: p.stem)
def test_platform_reality_table_covers_every_registered_platform(design):
    """support registry の全 platform が表に現れること（代替で省略しない）。"""
    registry = json.loads(PLATFORM_REGISTRY.read_text(encoding="utf-8"))
    platforms = {p["platform"] for p in registry["profiles"]}
    _, rows = _table_rows(design.read_text(encoding="utf-8"), "platform reality表")
    declared = " ".join(row[0] for row in rows).lower()
    missing = sorted(p for p in platforms if p not in declared)
    assert not missing, f"{design.name} §13.5: registry の platform が欠落 {missing}"


# --- 13.6 legacy exclusion ---------------------------------------------------


@pytest.mark.parametrize("design", BOUND_DESIGNS, ids=lambda p: p.stem)
def test_legacy_exclusion_negative_tests_exist_when_cited(design):
    """negative test を名指しした行は、その test が実在すること。"""
    header, rows = _table_rows(design.read_text(encoding="utf-8"), "legacy exclusion表")
    column = next(i for i, c in enumerate(header) if "negative test ID" in c)
    problems = []
    for row in rows:
        if len(row) <= column:
            continue
        cell = row[column]
        if any(marker in cell for marker in UNPROVEN_MARKERS):
            continue
        for span in re.findall(r"`([^`]+)`", cell):
            reason = _resolution_problem(span)
            if reason:
                problems.append(f"{row[0]}: {reason}")
    assert not problems, f"{design.name} §13.6: negative test が実在しない {problems}"


# --- design GatePassage: 7 観点の記録 ----------------------------------------


DESIGN_GATES = _design_gates_for({p.stem for p in BOUND_DESIGNS})


@pytest.mark.parametrize("gate", DESIGN_GATES, ids=lambda p: p.stem)
def test_design_gate_records_all_seven_criteria(gate):
    """FLW-CON-008 に拘束された設計を通す Gate は 7 観点を記録すること。"""
    text = gate.read_text(encoding="utf-8")
    missing = [c for c in SEVEN_CRITERIA if c not in text]
    assert not missing, f"{gate.name}: 7 観点の記録が欠落 {missing}"


@pytest.mark.parametrize("design", BOUND_DESIGNS, ids=lambda p: p.stem)
def test_unproven_criteria_are_not_claimed_as_gate_pass_grounds(design):
    """7 観点の現状表で、未証明の観点が実証済みと表記されていないこと。"""
    text = design.read_text(encoding="utf-8")
    match = re.search(r"^###\s+\S+\s+7観点の現状\s*$", text, re.M)
    if match is None:
        pytest.skip("7観点の現状表が無い（Gate 未提出の設計）")
    _, rows = _table_rows(text, "7観点の現状")
    declared = {row[1]: row[2] for row in rows if len(row) > 2}
    missing = [c for c in SEVEN_CRITERIA if c not in declared]
    assert not missing, f"{design.name}: 7 観点の行が欠落 {missing}"
    for name, state in declared.items():
        assert "実証済み" in state or any(m in state for m in UNPROVEN_MARKERS), (
            f"{design.name}: 観点 {name} の現状が判定不能な表記 {state!r}"
        )
