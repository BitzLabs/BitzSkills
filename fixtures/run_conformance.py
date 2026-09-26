#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["jsonschema==4.23.0", "attrs==26.1.0", "jsonschema-specifications==2025.9.1", "referencing==0.37.0", "rpds-py==2026.6.3", "typing-extensions==4.13.2"]
# ///
"""参照適合harnessの入口(ADR-052 Decision 1)。

`--core`が指す検査対象Core(source directoryまたはwheel)へ、`--step`または`--fixture`で選んだ
manifestを実行し、合否と差分をJSONで報告する。選んだfixtureがすべて`passed`の場合だけ終了コード0とする。
このscriptと`conformance/`はCoreに依存せず、`bitz`をimportしない(ADR-049 Decision 6)。
"""
import argparse
import json
from pathlib import Path
import sys
import tempfile
import time

from jsonschema import Draft202012Validator

sys.dont_write_bytecode = True
from conformance.runner import CoreEnvironment, CoreEnvironmentError, host_tool_versions, run_fixture
from conformance.schemas import schema_path
from conformance.selection import step_ids, selected_ids

HERE = Path(__file__).resolve().parent
CONFORMANCE_ROOT = HERE / "conformance"


def load_validators():
    names = ("manifest", "result", "side-effects")
    return {name: Draft202012Validator(json.loads(schema_path(CONFORMANCE_ROOT, name).read_text(encoding="utf-8")))
            for name in names}


def resolve_fixture_ids(args):
    if args.fixtures:
        ordered = []
        for identifier in args.fixtures:
            if identifier not in ordered:
                ordered.append(identifier)
        return ordered
    return step_ids(args.step)


def locate_fixture_root(identifier):
    for kind in ("single", "multi"):
        candidate = CONFORMANCE_ROOT / kind / identifier
        if candidate.is_dir():
            return candidate
    return None


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="Bitz Core 1.0の参照適合harness。--coreに対して選んだfixtureを実行し、合否をJSONで報告する。")
    parser.add_argument("--core", required=True, help="検査対象Coreのsource directoryまたは.whl file")
    selector = parser.add_mutually_exclusive_group(required=True)
    selector.add_argument("--step", type=int, help="steps.jsonのstep 1..Nのfixturesを累積で選ぶ")
    selector.add_argument("--fixture", action="append", dest="fixtures", metavar="ID",
                           help="single/またはmulti/のfixture IDを選ぶ。反復可能")
    parser.add_argument("--output", help="結果JSONの書き出し先。省略時は標準出力")
    parser.add_argument("--suite", choices=("full", "standard", "scale"), default="full",
                        help="開発時の部分検査。Gate認定はfullだけを使用する")
    parser.add_argument("--shard", type=int, default=1, help="1から始まる分割番号")
    parser.add_argument("--shards", type=int, default=1, help="分割数")
    parser.add_argument("--timings", help="工程別の所要時間を保存する別JSON")
    parser.add_argument("--progress", action="store_true", help="完了したfixtureを標準エラーへ表示する")
    args = parser.parse_args(argv)
    if args.output and args.timings and Path(args.output).resolve() == Path(args.timings).resolve():
        parser.error("--outputと--timingsには異なるpathを指定してください")
    return args


def main(argv=None):
    args = parse_args(argv)
    try:
        fixture_ids = selected_ids(resolve_fixture_ids(args), args.suite, args.shard, args.shards)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2
    timing_rows = []
    started = time.perf_counter()
    if not fixture_ids:
        print("選択されたfixtureがありません", file=sys.stderr)
        return 2
    validators = load_validators()

    report = {"core": str(Path(args.core).resolve()), "environment": host_tool_versions(), "fixtures": []}
    with tempfile.TemporaryDirectory(prefix="bitz-conformance-core-") as core_work_root:
        try:
            core_environment = CoreEnvironment(args.core, core_work_root)
        except CoreEnvironmentError as error:
            report["fixtures"] = [{"id": identifier, "result": "error", "differences": [str(error)]}
                                   for identifier in fixture_ids]
            _emit(report, args.output)
            return 1
        with tempfile.TemporaryDirectory(prefix="bitz-conformance-run-") as run_work_root:
            for identifier in fixture_ids:
                fixture_root = locate_fixture_root(identifier)
                if fixture_root is None:
                    report["fixtures"].append({"id": identifier, "result": "error",
                                                "differences": [f"fixture directoryが見つかりません: {identifier}"]})
                    continue
                phases = {} if args.timings else None
                start = time.perf_counter()
                result = run_fixture(fixture_root, identifier, core_environment, validators, run_work_root,
                                     timings=phases)
                elapsed = round((time.perf_counter() - start) * 1000, 3)
                report["fixtures"].append(result)
                if args.timings:
                    timing_rows.append({"id": identifier, "durationMs": elapsed,
                                        "phasesMs": {key: round(value, 3) for key, value in phases.items()}})
                    _emit({"durationMs": round((time.perf_counter() - started) * 1000, 3),
                           "fixtures": timing_rows}, args.timings)
                if args.progress:
                    print(f"[{len(report['fixtures'])}/{len(fixture_ids)}] {identifier}: "
                          f"{result['result']} ({elapsed / 1000:.2f}s)", file=sys.stderr, flush=True)

    counts = {"passed": 0, "failed": 0, "error": 0}
    for entry in report["fixtures"]:
        counts[entry["result"]] = counts.get(entry["result"], 0) + 1
    report["counts"] = counts
    all_passed = counts.get("passed", 0) == len(report["fixtures"]) and not counts.get("failed") and not counts.get("error")
    report["allPassed"] = all_passed
    _emit(report, args.output)
    return 0 if all_passed else 1


def _emit(report, output_path):
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if output_path:
        Path(output_path).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)


if __name__ == "__main__":
    raise SystemExit(main())
