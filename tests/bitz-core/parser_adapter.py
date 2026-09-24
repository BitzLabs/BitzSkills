#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""内部Parser受入のtest adapter（適合fixture仕様 §4.1、ADR-052 Decision 4）。

`fixtures/conformance/steps.json` の全Stepが参照するfixtureのうち`parserChecks`を持つものへ、
Core本体の実Scanner／Parser（`bitz.earsai.parser.parse_document`）を適用し、得られた全
Semantic IRを`expected/parser-ir.json`と完全比較する。fixture harnessの参照実装
（`parser_expectations.py`・`markdown_reference.py`等）は呼び出さない — 期待値の読込みと
setup・副作用観測だけ`fixtures/conformance`の既存部品（`harness.setup`／`harness.snapshot`）を
再利用する。`tests/`から`fixtures/`とCore導入先`plugins/bitz-core`を参照する向きはADR-049
Decision 6が許す。

`tests/bitz-core/certify_gate_b.py`の`run_parser_adapter`が、commit済みcloneのrepository rootで
本scriptを引数なしで`uv run`し、終了コード0と2 clone間のstdout byte一致を要求する（Step 2以降）。
標準出力は一時pathや所要時間を含まない決定的なJSON 1行とし、全fixtureがpassedの場合だけ
終了コード0とする。
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = ROOT / "fixtures"
CONFORMANCE_ROOT = FIXTURES_DIR / "conformance"
CORE_SRC = ROOT / "plugins" / "bitz-core" / "src"

sys.path.insert(0, str(CORE_SRC))
sys.path.insert(0, str(FIXTURES_DIR))

from conformance.harness import git, setup, snapshot  # noqa: E402  (fixtures側の既存setup部品を再利用)

from bitz.earsai.parser import parse_document  # noqa: E402  (検査対象の実Scanner／Parser)

# IRを伴う警告条件（構文破綻ではない）。これら以外の条件が出れば読取り対象fixtureとして未対応とする。
_SOFT_CONDITION_KINDS = {"should-reason-missing", "extension-unknown"}


def _observe(repository: Path) -> dict:
    """§5の読取り専用副作用条件の観測（`initial_fixtures.observe`と同じ形）。"""

    return {
        "repository": snapshot(repository),
        "git": {
            "status": git(repository, "status", "--porcelain=v1", "--untracked-files=all").decode(),
            "index": git(repository, "ls-files", "--stage").decode(),
        },
    }


def _diff_state(before: dict, after: dict) -> list[str]:
    return [name for name in sorted(before.keys() | after.keys()) if before.get(name) != after.get(name)]


def _fixture_ids() -> list[str]:
    """steps.jsonの全Stepが参照するfixture IDを、初出順の重複なしで集める。"""

    steps = json.loads((CONFORMANCE_ROOT / "steps.json").read_text(encoding="utf-8"))["steps"]
    ordered: list[str] = []
    for step in steps:
        for identifier in step["fixtures"]:
            if identifier not in ordered:
                ordered.append(identifier)
    return ordered


def _locate(identifier: str) -> Path | None:
    for kind in ("single", "multi"):
        candidate = CONFORMANCE_ROOT / kind / identifier
        if candidate.is_dir():
            return candidate
    return None


def _check_fixture(fixture_root: Path, manifest: dict, base_tmp: str) -> list[str]:
    """1 fixtureのparserChecksを検査し、差分の一覧を返す（空なら合格）。"""

    differences: list[str] = []
    with tempfile.TemporaryDirectory(prefix="bitz-parser-", dir=base_tmp) as sandbox_text:
        sandbox = Path(sandbox_text)
        repository = setup(fixture_root, manifest, sandbox / "repo")
        before = _observe(repository)

        for check in manifest["parserChecks"]:
            relative, expected_name = check["path"], check["resultFile"]
            source = repository / relative
            try:
                text = source.read_text(encoding="utf-8")
            except OSError as error:
                differences.append(f"{relative}: 読み取れません({error})")
                continue

            result = parse_document(text, relative)
            hard_conditions = [c for c in result.conditions if c["kind"] not in _SOFT_CONDITION_KINDS]
            if hard_conditions:
                differences.append(f"{relative}: 未対応の構文条件が発生しました: {hard_conditions}")

            expected = json.loads((fixture_root / expected_name).read_text(encoding="utf-8"))
            if result.statements != expected:
                differences.append(f"{relative}: 完全なSemantic IRがresultFileと一致しません")

        after = _observe(repository)
        state_diff = _diff_state(before, after)
        if state_diff:
            differences.append(f"読取り専用の副作用条件に違反しました: {state_diff}")
    return differences


def main() -> int:
    checks: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="bitz-parser-adapter-") as base_tmp:
        for identifier in _fixture_ids():
            fixture_root = _locate(identifier)
            if fixture_root is None:
                continue
            manifest_path = fixture_root / "manifest.json"
            if not manifest_path.is_file():
                continue
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if not manifest.get("parserChecks"):
                continue
            try:
                differences = _check_fixture(fixture_root, manifest, base_tmp)
            except (OSError, ValueError, KeyError) as error:
                differences = [f"adapter例外: {error}"]
            checks.append({"id": identifier, "result": "passed" if not differences else "failed",
                            "differences": differences})

    all_passed = bool(checks) and all(entry["result"] == "passed" for entry in checks)
    report = {"allPassed": all_passed, "checks": checks}
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
