#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""CIの独立checkout・分割実行・厳密な集約（ADR-056）。Coreの合否は参照harnessが判定する。"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "fixtures"))
sys.path.insert(0, str(ROOT / "tests/bitz-core"))
from conformance.selection import partition, step_ids
from conformance.reports import merge_reports
import certify_gate_b as certification


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n")


def head():
    result = certification.git("rev-parse", "HEAD")
    if result.returncode:
        raise ValueError("HEADを取得できません")
    return result.stdout.strip()


def execute(args):
    """workerは同じcommitを新しいcloneへ展開し、自分の分割だけをbuild・実行する。"""
    errors = certification.worktree_errors()
    if errors:
        raise ValueError("; ".join(errors))
    groups = partition(step_ids(args.step), args.shards)
    if not 1 <= args.shard <= len(groups) or args.replica not in (1, 2):
        raise ValueError("分割番号または独立実行番号が不正です")
    uv = shutil.which("uv")
    if not uv:
        raise ValueError("uvが見つかりません")
    commit = head()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    stem = f"replica-{args.replica}-shard-{args.shard}"
    evidence = {"schemaVersion": 1, "commit": commit, "step": args.step,
                "replica": args.replica, "shard": args.shard, "shards": args.shards,
                "runId": args.run_id, "checkoutId": str(uuid.uuid4()),
                "cleanBefore": False, "cleanAfter": False,
                "conformance": None, "parserAdapter": None, "errors": []}
    try:
        with tempfile.TemporaryDirectory(prefix="bitz-ci-gate-b-") as temporary:
            clone = Path(temporary) / "checkout"
            certification.checkout(commit, clone)
            before = certification.git("status", "--porcelain", "--untracked-files=all", cwd=clone)
            evidence["cleanBefore"] = before.returncode == 0 and not before.stdout
            actual_head = certification.git("rev-parse", "HEAD", cwd=clone)
            if not evidence["cleanBefore"] or actual_head.returncode or actual_head.stdout.strip() != commit:
                raise ValueError("独立checkoutが指定commitのclean状態ではありません")
            report_path = output / f"{stem}-conformance.json"
            argv = [uv, "run", "fixtures/run_conformance.py", "--core", "plugins/bitz-core",
                    "--step", str(args.step), "--shard", str(args.shard), "--shards", str(args.shards),
                    "--output", str(report_path), "--timings", str(output / f"{stem}-timings.json"), "--progress"]
            # stderrは逐次表示する。終了まで進捗を隠さず、timeout時もCIログへ残す。
            result = subprocess.run(argv, cwd=clone, timeout=1800)
            evidence["conformance"] = {"exitCode": result.returncode,
                                       "report": json.loads(report_path.read_text())}
            if args.step >= 2 and args.shard == 1:
                parser = certification.run_parser_adapter(uv, clone, 180)
                evidence["parserAdapter"] = {
                    "exitCode": parser["exitCode"], "stdout": parser["stdout"].decode("utf-8"),
                    "stderr": parser["stderr"].decode("utf-8", errors="replace"), "error": parser.get("error")}
            after = certification.git("status", "--porcelain", "--untracked-files=all", cwd=clone)
            evidence["cleanAfter"] = after.returncode == 0 and not after.stdout
    except (OSError, ValueError, subprocess.SubprocessError, RuntimeError) as error:
        evidence["errors"].append(str(error))
    write_json(output / f"{stem}-evidence.json", evidence)
    c = evidence["conformance"]
    p = evidence["parserAdapter"]
    return 0 if (not evidence["errors"] and evidence["cleanBefore"] and evidence["cleanAfter"]
                 and c and c["exitCode"] == 0 and c["report"].get("allPassed") is True
                 and (args.step < 2 or args.shard != 1 or p and p["exitCode"] == 0 and not p["error"])) else 1


def collect(evidences, *, step, shards, replicas, commit, run_id):
    """worker不足、別commit、別run、失敗、重複を拒否して全件結果を照合する。"""
    if replicas not in (1, 2):
        raise ValueError("独立実行数は1または2です")
    identifiers = step_ids(step)
    groups = partition(identifiers, shards)
    expected = {(r, s) for r in range(1, replicas + 1) for s in range(1, shards + 1)}
    indexed, checkout_ids = {}, set()
    for evidence in evidences:
        key = (evidence["replica"], evidence["shard"])
        if key not in expected or key in indexed:
            raise ValueError("workerが余分または重複しています")
        if (evidence["schemaVersion"] != 1 or evidence["step"] != step or evidence["shards"] != shards
                or evidence["commit"] != commit or evidence["runId"] != run_id):
            raise ValueError("workerのcommit・run・実行条件が一致しません")
        checkout_id = evidence["checkoutId"]
        if not isinstance(checkout_id, str) or not checkout_id or checkout_id in checkout_ids:
            raise ValueError("独立checkoutの識別子が不正または重複しています")
        checkout_ids.add(checkout_id)
        if evidence["cleanBefore"] is not True or evidence["cleanAfter"] is not True or evidence["errors"]:
            raise ValueError("workerがclean状態で正常完了していません")
        conformance = evidence["conformance"]
        if not conformance or type(conformance["exitCode"]) is not int or conformance["exitCode"] != 0:
            raise ValueError("適合harnessが正常終了していません")
        indexed[key] = evidence
    if set(indexed) != expected:
        raise ValueError("workerの結果が不足しています")
    reports, parsers = [], []
    for replica in range(1, replicas + 1):
        workers = [indexed[(replica, shard)] for shard in range(1, shards + 1)]
        report = merge_reports([w["conformance"]["report"] for w in workers], groups, identifiers)
        if report["allPassed"] is not True:
            raise ValueError("全fixtureがpassedではありません")
        reports.append(report)
        for worker in workers:
            parser = worker["parserAdapter"]
            if step >= 2 and worker["shard"] == 1:
                if (not parser or type(parser["exitCode"]) is not int or parser["exitCode"] != 0
                        or parser["error"] or not isinstance(parser["stdout"], str) or not parser["stdout"]):
                    raise ValueError("Parser adapterが正常完了していません")
                parsers.append({"exitCode": 0, "stdout": parser["stdout"].encode(), "error": None})
            elif parser is not None:
                raise ValueError("Parser adapterの実行位置が不正です")
    result = {"commit": commit, "step": step, "replicas": replicas, "shards": shards,
              "fixtureCount": len(identifiers), "result": "Passed", "errors": [],
              "reports": [certification._conformance_digest(json.dumps(r).encode()) for r in reports]}
    if replicas == 2:
        conformance = [{"exitCode": 0, "stdout": json.dumps(report).encode()} for report in reports]
        errors = certification.judge(step, conformance, parsers)
        if errors:
            raise ValueError("; ".join(errors))
        result["gateB"] = {"step": step, "result": "Passed"}
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="mode", required=True)
    run = commands.add_parser("run")
    run.add_argument("--replica", type=int, choices=(1, 2), required=True)
    run.add_argument("--shard", type=int, required=True)
    merge = commands.add_parser("collect")
    merge.add_argument("--replicas", type=int, choices=(1, 2), required=True)
    merge.add_argument("--input", type=Path, required=True)
    for command in (run, merge):
        command.add_argument("--step", type=int, required=True)
        command.add_argument("--shards", type=int, default=4)
        command.add_argument("--run-id", required=True, help="CI run IDとattemptを合わせた識別子")
        command.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.mode == "run":
            return execute(args)
        errors = certification.worktree_errors()
        if errors:
            raise ValueError("; ".join(errors))
        evidence = [json.loads(path.read_text()) for path in sorted(args.input.glob("*-evidence.json"))]
        report = collect(evidence, step=args.step, shards=args.shards, replicas=args.replicas,
                         commit=head(), run_id=args.run_id)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        report = {"result": "Failed", "errors": [str(error)]}
        if args.mode == "run":
            print(json.dumps(report, ensure_ascii=False), file=sys.stderr)
            return 1
    write_json(args.output, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["result"] == "Passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
