#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["jsonschema==4.23.0", "attrs==26.1.0", "jsonschema-specifications==2025.9.1", "referencing==0.37.0", "rpds-py==2026.6.3", "typing-extensions==4.13.2"]
# ///
"""Core実行体なしで、性能基準と比較taskの入力（Step 0-Pで固定）を検証する。uv runで実行する。"""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parent

RUNNER_SPEC = importlib.util.spec_from_file_location(
    "performance_runner_for_audit", ROOT / "performance/run_benchmarks.py")
PERFORMANCE_RUNNER = importlib.util.module_from_spec(RUNNER_SPEC)
sys.modules[RUNNER_SPEC.name] = PERFORMANCE_RUNNER
RUNNER_SPEC.loader.exec_module(PERFORMANCE_RUNNER)


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    schemas = sorted(ROOT.glob("performance/schemas/*.json")) + sorted(ROOT.glob("comparison/*.schema.json"))
    for path in schemas:
        Draft202012Validator.check_schema(read(path))
    pairs = [
        ("performance/datasets/*.json", "performance/schemas/dataset.schema.json"),
        ("performance/environments/*.json", "performance/schemas/environment.schema.json"),
        ("performance/benchmark-plan.json", "performance/schemas/benchmark-plan.schema.json"),
        ("comparison/tasks/*.json", "comparison/task.schema.json"),
        ("comparison/protocol.json", "comparison/protocol.schema.json"),
        ("comparison/answer-key.json", "comparison/answer-key.schema.json"),
    ]
    validated = 0
    for pattern, schema in pairs:
        paths = sorted(ROOT.glob(pattern))
        assert paths, pattern
        validator = Draft202012Validator(read(ROOT / schema))
        for path in paths:
            validator.validate(read(path))
            validated += 1
    datasets = {read(p)["datasetId"]: p for p in ROOT.glob("performance/datasets/*.json")}
    plan = read(ROOT / "performance/benchmark-plan.json")
    assert (ROOT / "performance" / plan["environment"]).is_file()
    assert len({case["id"] for case in plan["cases"]}) == len(plan["cases"])
    assert all(case["dataset"] in datasets for case in plan["cases"])
    environment = read(ROOT / "performance" / plan["environment"])
    baseline_paths = sorted(ROOT.glob("performance/baselines/*/*.json"))
    assert baseline_paths, "performance/baselines/*/*.json"
    result_validator = Draft202012Validator(
        read(ROOT / "performance/schemas/run-result.schema.json"),
        format_checker=FormatChecker(),
    )
    baseline_summaries = []
    for path in baseline_paths:
        result = read(path)
        result_validator.validate(result)
        assert path.parent.name == result["environmentId"], path
        assert path.stem == result["coreCommit"], path
        commit = result["coreCommit"]
        exists = subprocess.run(
            ["git", "cat-file", "-e", f"{commit}^{{commit}}"],
            cwd=ROOT.parent, capture_output=True,
        )
        assert exists.returncode == 0, f"baselineのcommitが存在しません: {commit}"
        ancestor = subprocess.run(
            ["git", "merge-base", "--is-ancestor", commit, "HEAD"],
            cwd=ROOT.parent, capture_output=True,
        )
        assert ancestor.returncode == 0, f"baselineのcommitがHEADの祖先ではありません: {commit}"
        summary = PERFORMANCE_RUNNER.validate_accepted_baseline(
            result, plan, environment,
            {identifier: read(path) for identifier, path in datasets.items()})
        summary["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        baseline_summaries.append(summary)
        validated += 1
    protocol = read(ROOT / "comparison/protocol.json")
    assert sorted(protocol["taskIds"]) == sorted(p.stem for p in ROOT.glob("comparison/tasks/*.json"))
    results = []
    with tempfile.TemporaryDirectory(prefix="bitz-benchmarks-") as temporary:
        for identifier, manifest in sorted(datasets.items()):
            runs = []
            for index in range(2):
                command = [sys.executable, str(ROOT / "performance/scripts/generate_fixture.py"), str(manifest), str(Path(temporary) / f"{identifier}-{index}")]
                runs.append(subprocess.check_output(command, text=True))
            assert runs[0] == runs[1], identifier
            results.append(json.loads(runs[0]))
            # 元のdigestを残したままでも、壊した形状は拒否しなければならない。
            mutated = copy.deepcopy(read(manifest))
            mutated["shape"]["specBytes"] += 1
            bad_manifest = Path(temporary) / f"{identifier}-bad.json"
            bad_manifest.write_text(json.dumps(mutated), encoding="utf-8")
            command = [sys.executable, str(ROOT / "performance/scripts/generate_fixture.py"), str(bad_manifest), str(Path(temporary) / f"{identifier}-bad")]
            rejected = subprocess.run(command, capture_output=True, text=True)
            assert rejected.returncode != 0 and "形状が一致しません" in rejected.stderr
    print(json.dumps({
        "status": "Passed",
        "schemas": len(schemas),
        "inputs": validated,
        "generationRunsPerDataset": 2,
        "shapeRejectionChecks": len(datasets),
        "datasets": results,
        "baselines": baseline_summaries,
    }, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
