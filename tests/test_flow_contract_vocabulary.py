"""FLW-CON-007 三者照合を全 namespace へ拡張する（`FLW-TSK-097`）。

以前の三者照合（現 `test_flow_m2_worktree.py` の旧 `M2-FLT-023`。本ファイル追加に
伴い撤去した）は `work_unit_state` / `worktree_state` / `branch_audit_state` の
3 namespace だけをテスト側にハードコードしており、`FLW-DSN-016` §2 の閉集合表が
宣言する他の namespace（`cause` を含む）を走査していなかった。そのため
`cause` の `quarantined` が実装定数 `ALLOWED_CAUSES` にだけ追加され、
`schemas/result-v1.schema.json` へ入らないまま公開経路へ出る欠落が沈黙した
（`SI-FLW-072`）。

本テストは `FLW-DSN-016` §2 の閉集合表・所在表を**パースして得た namespace 集合**を
回し、実装定数の解決先が無い namespace は skip せず FAIL させる。閉集合表・所在表・
実際に照合した namespace の3集合が完全一致することも別アサーションで検査する。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / "plugins" / "bitz-flow" / "skills" / "flow-core"
SCHEMAS = SKILL / "schemas"
DESIGN = REPO_ROOT / "plugins/bitz-flow/.spec/design/FLW-DSN-016.md"
sys.path.insert(0, str(SKILL / "scripts"))

from flowlib import guard as G  # noqa: E402
from flowlib import intent as I  # noqa: E402
from flowlib import result as R  # noqa: E402
from flowlib import worktree as W  # noqa: E402
from flowlib import worktree_cleanup as WC  # noqa: E402

MODULES: dict[str, Any] = {
    "intent.py": I, "result.py": R, "worktree.py": W, "guard.py": G,
    "worktree_cleanup.py": WC,
}


# --- FLW-DSN-016 §2 の表のパース ---------------------------------------------


def _slice_section(text: str, start_heading: str, end_heading: str) -> str:
    start = text.index(start_heading)
    end = text.index(end_heading, start)
    return text[start:end]


def parse_closed_enum_table(text: str) -> dict[str, tuple[str, ...]]:
    """閉集合表（`### 閉集合（本書を唯一の正とする）`）から namespace → 値集合 を得る。

    行ごとに backtick span はちょうど2つ（field 名、comma 区切りの値列）である
    前提でパースする。namespace ラベル列・値の性質列は backtick を持たない。
    """
    section = _slice_section(text, "### 閉集合（本書を唯一の正とする）", "### 実装定数の所在")
    rows: dict[str, tuple[str, ...]] = {}
    for line in section.splitlines():
        if not line.strip().startswith("|"):
            continue
        spans = re.findall(r"`([^`]+)`", line)
        if len(spans) != 2:
            continue
        field, enum_list = spans
        if not re.fullmatch(r"[a-z_]+", field):
            continue
        rows[field] = tuple(part.strip() for part in enum_list.split(","))
    return rows


def parse_location_table(text: str) -> dict[str, dict[str, Any]]:
    """所在表（`### 実装定数の所在`）から namespace → schema/実装定数の所在 を得る。

    schema 側 span は「複数の `*.json` を挙げてから最後に `$defs/<key>`」の順で現れる
    （`guard_identity_kind` のように複数 schema へ現れる namespace がある）。
    実装側 span は「`*.py` の後に定数名」の順で現れる。列の並び順ではなく
    span の**形**（拡張子・`$defs/` 接頭辞）で分類するため、schema 側の個数が
    可変でも壊れない。
    """
    section = _slice_section(text, "### 実装定数の所在", "### 表記規則の判定基準")
    rows: dict[str, dict[str, Any]] = {}
    for line in section.splitlines():
        if not line.strip().startswith("|"):
            continue
        spans = re.findall(r"`([^`]+)`", line)
        if len(spans) < 5:
            continue
        namespace, rest = spans[0], spans[1:]
        if not re.fullmatch(r"[a-z_]+", namespace):
            continue
        schema_files: list[str] = []
        defs_key: str | None = None
        impl_file: str | None = None
        impl_const: str | None = None
        for span in rest:
            if span.startswith("$defs/"):
                defs_key = span[len("$defs/"):]
            elif span.endswith(".json"):
                schema_files.append(span)
            elif span.endswith(".py"):
                impl_file = span.rsplit("/", 1)[-1]
            else:
                impl_const = span
        if not (schema_files and defs_key and impl_file and impl_const):
            continue
        rows[namespace] = {
            "schema_files": tuple(schema_files),
            "defs_key": defs_key,
            "impl_file": impl_file,
            "impl_const": impl_const,
            "impl_is_key_set": "key 集合" in line,
        }
    return rows


def parse_generated_block(text: str) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """`<!-- BEGIN GENERATED: multi-namespace-values -->` 区間の実際の内容を読む。"""
    start = text.index("<!-- BEGIN GENERATED: multi-namespace-values -->")
    end = text.index("<!-- END GENERATED: multi-namespace-values -->", start)
    rows = []
    for line in text[start:end].splitlines():
        spans = re.findall(r"`([^`]+)`", line)
        if len(spans) < 2:
            continue
        rows.append((spans[0], tuple(spans[1:])))
    return tuple(rows)


def compute_multi_namespace_values(
    closed: Mapping[str, tuple[str, ...]],
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """閉集合表から「2つ以上の namespace に現れる値」を昇順・case-sensitive で導出する。"""
    owners: dict[str, set[str]] = {}
    for namespace, values in closed.items():
        for value in values:
            owners.setdefault(value, set()).add(namespace)
    return tuple(
        (value, tuple(sorted(namespaces)))
        for value, namespaces in sorted(owners.items())
        if len(namespaces) >= 2
    )


# --- schema / 実装定数の解決 ---------------------------------------------------


def load_schemas(schemas_dir: Path, filenames: Iterable[str]) -> dict[str, dict[str, Any]]:
    names = sorted(set(filenames))
    return {name: json.loads((schemas_dir / name).read_text(encoding="utf-8")) for name in names}


def resolve_schema_values(
    schemas: Mapping[str, dict[str, Any]], schema_files: Sequence[str], defs_key: str,
) -> dict[str, set[str]]:
    return {name: set(schemas[name]["$defs"][defs_key]["enum"]) for name in schema_files}


def resolve_impl_values(
    modules: Mapping[str, Any], impl_file: str, impl_const: str, *, is_key_set: bool,
) -> set[str]:
    value = getattr(modules[impl_file], impl_const)
    return set(value.keys()) if is_key_set else set(value)


def check_namespace(
    namespace: str,
    design_values: Iterable[str],
    schema_values_by_file: Mapping[str, set[str]],
    impl_values: set[str],
) -> list[str]:
    """設計 ⊆ schema / schema ⊆ 設計 / 設計 ⊆ 実装 / 実装 ⊆ 設計の4方向を検査する。

    同じ namespace が複数 schema に現れる場合は schema 間の不一致も検査する
    （`guard_identity_kind` が該当）。
    """
    design_set = set(design_values)
    errors: list[str] = []
    for schema_file, schema_set in schema_values_by_file.items():
        if schema_set != design_set:
            errors.append(
                f"{namespace}: design と {schema_file} が不一致 "
                f"(design-only={sorted(design_set - schema_set)}, "
                f"schema-only={sorted(schema_set - design_set)})"
            )
    files = list(schema_values_by_file)
    for left, right in zip(files, files[1:]):
        if schema_values_by_file[left] != schema_values_by_file[right]:
            errors.append(f"{namespace}: schema 間で不一致（{left} vs {right}）")
    if impl_values != design_set:
        errors.append(
            f"{namespace}: design と実装定数が不一致 "
            f"(design-only={sorted(design_set - impl_values)}, "
            f"impl-only={sorted(impl_values - design_set)})"
        )
    return errors


# --- 本体 ---------------------------------------------------------------------


def test_FLW_CON_007_closed_table_and_location_table_namespaces_match_exactly():
    """閉集合表・所在表・実際に照合した namespace の3集合が完全一致すること。

    片方の表に行を足して他方を忘れた場合はここで落ちる。
    """
    text = DESIGN.read_text(encoding="utf-8")
    closed = parse_closed_enum_table(text)
    location = parse_location_table(text)
    assert set(closed) == set(location), (
        f"閉集合表と所在表の namespace が一致しない: "
        f"closed-only={sorted(set(closed) - set(location))}, "
        f"location-only={sorted(set(location) - set(closed))}"
    )


def test_FLW_CON_007_all_declared_namespaces_match_design_schema_and_implementation():
    """閉集合表が宣言する**全 namespace**を実際に照合し、設計⇔schema⇔実装が一致すること。

    以前は `cause` を走査しておらず、`quarantined` の schema 欠落を検出できなかった
    （`SI-FLW-072`）。`FLW-TSK-096` の是正後にこのテストを実際に回すことで、
    `cause` と `result_code` の乖離が（存在すれば）検出されることを示す。
    """
    text = DESIGN.read_text(encoding="utf-8")
    closed = parse_closed_enum_table(text)
    location = parse_location_table(text)
    assert closed, "閉集合表を1行もパースできていない（パーサ自体の異常）"

    all_schema_files = {name for row in location.values() for name in row["schema_files"]}
    schemas = load_schemas(SCHEMAS, all_schema_files)

    tested: set[str] = set()
    errors: list[str] = []
    for namespace, design_values in closed.items():
        location_row = location.get(namespace)
        if location_row is None:
            # 所在表が未整備であること自体を FAIL させる（skip しない）。
            errors.append(f"{namespace}: 所在表に解決先が無い")
            continue
        tested.add(namespace)
        schema_values = resolve_schema_values(
            schemas, location_row["schema_files"], location_row["defs_key"]
        )
        impl_values = resolve_impl_values(
            MODULES, location_row["impl_file"], location_row["impl_const"],
            is_key_set=location_row["impl_is_key_set"],
        )
        errors.extend(check_namespace(namespace, design_values, schema_values, impl_values))

    assert not errors, "\n".join(errors)
    # 「宣言された namespace のうち自分が知っているものだけ」を回っていないことの確認。
    assert tested == set(closed) == set(location)


def test_FLW_CON_007_multi_namespace_value_list_matches_the_generated_block():
    """生成区間（`multi-namespace-values`）が閉集合表からの再生成と一致すること。

    比較は case-sensitive（`dirty` と `DIRTY` を同一視しない）。
    """
    text = DESIGN.read_text(encoding="utf-8")
    closed = parse_closed_enum_table(text)
    expected = compute_multi_namespace_values(closed)
    actual = parse_generated_block(text)
    assert actual == expected


# --- 陽性対照 — 意図的に壊した入力で必ず FAIL することを確認する ------------------


def test_FLW_TSK_097_fault_schema_missing_a_value_is_detected():
    """schema から1値削ると `check_namespace` が検出すること。"""
    errors = check_namespace(
        "cause", ("not-repository", "quarantined"),
        {"result-v1.schema.json": {"not-repository"}},  # quarantined を欠く
        {"not-repository", "quarantined"},
    )
    assert errors and "design-only=['quarantined']" in errors[0]


def test_FLW_TSK_097_fault_implementation_adds_an_extra_value_is_detected():
    """実装定数に schema/design に無い値を足すと `check_namespace` が検出すること。"""
    errors = check_namespace(
        "cause", ("not-repository", "quarantined"),
        {"result-v1.schema.json": {"not-repository", "quarantined"}},
        {"not-repository", "quarantined", "unregistered-extra-cause"},
    )
    assert any("impl-only=['unregistered-extra-cause']" in message for message in errors)


def test_FLW_TSK_097_fault_removing_a_location_row_breaks_completeness():
    """所在表の行を消すと3集合の完全一致が崩れ、skip ではなく検出できること。"""
    text = DESIGN.read_text(encoding="utf-8")
    closed = parse_closed_enum_table(text)
    location = parse_location_table(text)
    mutated_location = {key: value for key, value in location.items() if key != "cause"}
    assert set(closed) != set(mutated_location)
    assert "cause" in set(closed) - set(mutated_location)


def test_FLW_TSK_097_fault_generated_block_rewrite_is_detected():
    """生成区間を書き換えると再生成との不一致が検出できること。"""
    text = DESIGN.read_text(encoding="utf-8")
    closed = parse_closed_enum_table(text)
    expected = compute_multi_namespace_values(closed)
    tampered = text.replace(
        "| `ACTIVE` | `branch_audit_state` / `work_unit_state` |",
        "| `ACTIVE` | `branch_audit_state` |",
        1,
    )
    assert tampered != text, "置換対象の行が実体に存在しない（フォーマット変更を検知）"
    assert parse_generated_block(tampered) != expected
