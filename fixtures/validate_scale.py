#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["jsonschema==4.23.0", "attrs==26.1.0", "jsonschema-specifications==2025.9.1", "referencing==0.37.0", "rpds-py==2026.6.3", "typing-extensions==4.13.2"]
# ///
"""上限境界fixtureを実寸で生成して照合する（Core操作は実行しない）。uv runで実行する。

既定の統合検証（validate_conformance.py）は縮小profileだけを生成する。本commandは
[ADR-048](../docs/02.設計書/10_決定記録/ADR-048_適合fixtureの生成入力とGit構造operationを確定する.md)の
段階的な検証の実寸側であり、dataset manifestから入力treeを作り、tree digest、期待結果のdigest、
副作用のstate digestを照合する。Gate Aの認定にはこの記録が必要である。
"""
import json
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / "fixtures"))

from conformance import multi_crosscheck, multi_generator, multi_limit_fixtures  # noqa: E402
from conformance.harness import setup, tree_digest_bytes, write_generated  # noqa: E402
from conformance.initial_fixtures import observe  # noqa: E402

FIXTURES = ROOT / "fixtures/conformance/multi"


def observed_state(fixture, manifest, entries, sandbox):
    repository = setup(fixture, manifest, sandbox / "repo", generated=entries)
    external = {name: sandbox / name for name in ("home", "cache", "temporary")}
    for path in external.values():
        path.mkdir()
    return observe(repository, external)


def binding_digests(entries, sandbox):
    """binding境界のtargetごとのContext Digestを、入力treeからの導出で求める。"""
    repository = sandbox / "context"
    repository.mkdir()
    write_generated(entries, repository)
    digests = {}
    for workspace, documents in multi_limit_fixtures.binding_documents(entries).items():
        workspace_id = "platform" if workspace == "." else workspace.rsplit("/", 1)[-1]
        for document in documents:
            target = f"{workspace_id}::{document['id']}"
            digests[target] = multi_crosscheck.digest(
                multi_crosscheck.canonical_bytes(multi_crosscheck.build(repository, target)))
    return digests


def expected_result(identifier, entries, sandbox):
    dimension, _, crosses = multi_limit_fixtures.CASES[identifier]
    if crosses:
        return multi_limit_fixtures.blocked_result(identifier)
    if dimension == multi_limit_fixtures.VERIFY_DIMENSION:
        return multi_limit_fixtures.passed_binding_result(entries, binding_digests(entries, sandbox))
    return multi_limit_fixtures.passed_check_result(multi_generator.workspace_counts(entries))


def validate_fixture(identifier):
    dimension, value, crosses = multi_limit_fixtures.CASES[identifier]
    fixture = FIXTURES / identifier
    manifest = json.loads((fixture / "manifest.json").read_text())
    dataset = json.loads((fixture / "dataset.json").read_text())
    effects = json.loads((fixture / "side-effects.json").read_text())
    errors = []
    entries = multi_generator.emit(multi_generator.plan(dimension, value))
    totals = multi_generator.count(entries)
    if totals != dataset["dimensions"]:
        errors.append("生成物のdimensionがdataset manifestと一致しません")
    if totals[dimension] != value:
        errors.append("狙ったdimensionの値が一致しません")
    digest = tree_digest_bytes(entries)
    if digest != manifest["setup"]["generate"]["treeDigest"]:
        errors.append("tree digestがmanifestと一致しません")
    if tree_digest_bytes(multi_generator.emit(multi_generator.plan(dimension, value))) != digest:
        errors.append("2回の生成が一致しません")
    with tempfile.TemporaryDirectory(prefix="bitz-scale-") as temporary:
        sandbox = Path(temporary)
        result = expected_result(identifier, entries, sandbox)
        if multi_limit_fixtures.canonical_digest(result) != manifest["expect"]["resultDigest"]:
            errors.append("期待結果のdigestがmanifestと一致しません")
        if crosses:
            if result["status"] != "blocked" or result["workspaces"]:
                errors.append("上限超過は部分結果を返しません")
        elif dimension == multi_limit_fixtures.VERIFY_DIMENSION:
            multi_limit_fixtures.check_binding_result(result, dataset)
        else:
            multi_limit_fixtures.check_passed_result(result, dataset)
        states = []
        for run in range(2):
            run_sandbox = sandbox / f"run{run}"
            run_sandbox.mkdir()
            states.append(observed_state(fixture, manifest, entries, run_sandbox))
        if states[0] != states[1]:
            errors.append("隔離setupが2回で一致しません")
        state_digest = multi_limit_fixtures.canonical_digest(states[0])
        if state_digest != effects["stateDigest"]:
            errors.append("副作用のstate digestが期待値と一致しません")
    return {"fixtureId": identifier, "dimension": dimension, "value": value,
            "files": len(entries), "inputBytes": totals["inputBytes"],
            "treeDigest": digest, "errors": errors}


def main():
    start = time.monotonic()
    results = [validate_fixture(identifier) for identifier in multi_limit_fixtures.CASES]
    errors = [f"{entry['fixtureId']}: {message}" for entry in results for message in entry["errors"]]
    report = {
        "status": "Passed" if not errors else "Failed",
        "fixtures": len(results),
        "setupsPerFixture": 2,
        "coreExecution": "Not run",
        "durationSeconds": round(time.monotonic() - start, 1),
        "results": [{key: value for key, value in entry.items() if key != "errors"} for entry in results],
        "errors": errors,
    }
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
