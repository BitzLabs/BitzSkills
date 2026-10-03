#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Gate Cの実行・集約コマンド。

`run`はコミット済みHEADから新しいチェックアウトを作り、指定した環境のロールで全適合fixtureとCore単体試験を実行する。
`collect`は`minimum`と`reference`の2つの証跡を、失敗時に通さない扱いで照合し、対象コミットの新しいチェックアウトで
受入済みの性能ベースラインと固定SLO、および提案25のP0/P1 11件の個別の証跡を再監査する。
すべてが通過した場合だけGate Cを`Passed`とする。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests/bitz-core"))
sys.path.insert(0, str(ROOT / "fixtures"))

import gate_c
from conformance.selection import step_ids

CORE = "plugins/bitz-core"
UNIT_RUNNER = "tests/bitz-core/run_test_files.py"
REFERENCE_MANIFEST = Path("fixtures/performance/environments/core-1-reference.json")
BENCHMARK_AUDIT = "fixtures/validate_benchmarks.py"
PRIORITY_CLOSURE_AUDIT = "tests/bitz-core/priority_closure.py"


def git(*args: str, cwd: Path = ROOT) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=120)


def clean(cwd: Path) -> bool:
    result = git("status", "--porcelain", "--untracked-files=all", cwd=cwd)
    return result.returncode == 0 and result.stdout == ""


def checkout(commit: str, directory: Path) -> None:
    for args, cwd in ((("clone", "--quiet", "--no-checkout", str(ROOT), str(directory)), ROOT),
                      (("checkout", "--quiet", "--detach", commit), directory)):
        result = git(*args, cwd=cwd)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or f"`git {args[0]}`が失敗しました")


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def load_reference_manifest(cwd: Path) -> dict:
    return json.loads((cwd / REFERENCE_MANIFEST).read_text(encoding="utf-8"))


def load_reference_manifest_at(commit: str) -> dict:
    result = git("show", f"{commit}:{REFERENCE_MANIFEST.as_posix()}")
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "対象コミットの基準環境のマニフェストを読めません")
    return json.loads(result.stdout)


def command_output(argv: list[str]) -> str:
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=30)
    except OSError:
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def cpu_model() -> str:
    try:
        for line in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines():
            if line.startswith("model name"):
                return line.partition(":")[2].strip()
    except OSError:
        pass
    return platform.processor() or "unknown"


def platform_class(kernel: str) -> str:
    lowered = kernel.lower()
    if "microsoft" in lowered and "wsl2" in lowered:
        return "WSL2"
    return "native-linux"


def storage_class(source: str, host_platform_class: str) -> str:
    if host_platform_class == "WSL2":
        return "wsl2-virtual-disk"
    if not source.startswith("/dev/"):
        return "unknown"
    values = command_output(["lsblk", "-no", "ROTA", source]).split()
    if values and set(values) == {"0"}:
        return "local-ssd"
    if "1" in values:
        return "local-hdd"
    return "unknown"


def observed_host_environment(cwd: Path) -> dict:
    source = command_output(["findmnt", "-n", "-o", "SOURCE", "-T", str(cwd)])
    filesystem = command_output(["findmnt", "-n", "-o", "FSTYPE", "-T", str(cwd)])
    kernel = platform.release()
    host_platform_class = platform_class(kernel)
    try:
        ram_bytes = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    except (OSError, ValueError):
        ram_bytes = 0
    cgroup_v2 = (Path("/sys/fs/cgroup/cgroup.controllers").is_file()
                 and Path("/sys/fs/cgroup/cgroup.procs").is_file())
    return {
        "kernel": kernel,
        "cpuModel": cpu_model(),
        "logicalCores": os.cpu_count() or 0,
        "ramBytes": ram_bytes,
        "platformClass": host_platform_class,
        "storageClass": storage_class(source, host_platform_class),
        "filesystem": filesystem or "unknown",
        "memoryAccounting": "cgroup-v2-process-tree" if cgroup_v2 else "unsupported",
    }


def python_environment(uv: str, python_spec: str, cwd: Path) -> dict:
    program = (
        "import json,platform,sys;"
        "print(json.dumps({'python':platform.python_version(),"
        "'implementation':platform.python_implementation(),"
        "'system':platform.system(),'machine':platform.machine(),"
        "'executable':sys.executable},sort_keys=True))"
    )
    result = subprocess.run(
        [uv, "run", "--python", python_spec, "--no-project", "python", "-c", program],
        cwd=cwd, capture_output=True, text=True, timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Python環境の観測に失敗しました")
    return json.loads(result.stdout)


def run_command(argv: list[str], cwd: Path, timeout: int) -> dict:
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(argv, cwd=cwd, env=environment, capture_output=True, timeout=timeout)
    return {"exitCode": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr}


def unit_test_count(stdout: bytes, stderr: bytes) -> int | None:
    text = (stdout + b"\n" + stderr).decode("utf-8", errors="replace")
    matched = re.search(r"Ran (\d+) tests? in ", text)
    return int(matched.group(1)) if matched else None


def run_evidence(role: str, environment_id: str, python_spec: str) -> tuple[dict, list[str]]:
    errors: list[str] = []
    uv = shutil.which("uv")
    head = git("rev-parse", "--verify", "HEAD")
    commit = head.stdout.strip() if head.returncode == 0 else None
    if not clean(ROOT):
        errors.append("作業ツリーにコミットされていない変更があります")
    if uv is None:
        errors.append("`uv`が見つかりません")
    if commit is None:
        errors.append("`HEAD`のコミットがありません")

    evidence = {
        "schemaVersion": 1,
        "commit": commit,
        "role": role,
        "environmentId": environment_id,
        "referenceManifestSha256": None,
        "requestedPython": python_spec,
        "checkoutId": uuid.uuid4().hex,
        "cleanBefore": False,
        "cleanAfter": False,
        "environment": {},
        "conformance": {},
        "unit": {},
        "errors": errors,
    }
    if errors:
        return evidence, errors

    try:
        with tempfile.TemporaryDirectory(prefix=f"bitz-gate-c-{role}-") as temporary:
            directory = Path(temporary) / "checkout"
            checkout(commit, directory)
            evidence["cleanBefore"] = clean(directory)
            evidence["environment"] = python_environment(uv, python_spec, directory)
            evidence["environment"]["git"] = subprocess.check_output(
                ["git", "--version"], text=True, timeout=30).strip()
            evidence["environment"].update(observed_host_environment(directory))

            if role == "reference":
                manifest = load_reference_manifest(directory)
                evidence["referenceManifestSha256"] = gate_c.manifest_digest(manifest)
                if environment_id != manifest.get("environmentId"):
                    errors.append("`environmentId`が基準環境のマニフェストと一致しません")
                try:
                    gate_c.validate_reference_environment(evidence["environment"], manifest)
                except ValueError as error:
                    errors.append(str(error))
                if errors:
                    evidence["cleanAfter"] = clean(directory)
                    if not evidence["cleanBefore"] or not evidence["cleanAfter"]:
                        errors.append("新しいチェックアウトが実行前後でクリーンではありません")
                    evidence["errors"] = errors
                    return evidence, errors

            conformance = run_command(
                [uv, "run", "--python", python_spec, "fixtures/run_conformance.py",
                 "--core", CORE, "--step", "5"],
                directory, 1200,
            )
            try:
                report = json.loads(conformance["stdout"])
            except (ValueError, UnicodeDecodeError):
                report = None
                errors.append("適合試験の標準出力がJSONではありません")
            evidence["conformance"] = {
                "exitCode": conformance["exitCode"],
                "report": report,
                "stderrSha256": sha256(conformance["stderr"]),
            }
            if conformance["exitCode"] != 0:
                errors.append("適合試験が成功しませんでした")

            tests = sorted(str(path.relative_to(directory))
                           for path in (directory / "tests/bitz-core").glob("test_*.py"))
            unit = run_command(
                [uv, "run", "--python", python_spec, "--project", CORE, "python",
                 UNIT_RUNNER, *tests],
                directory, 900,
            )
            count = unit_test_count(unit["stdout"], unit["stderr"])
            evidence["unit"] = {
                "exitCode": unit["exitCode"],
                "testsRun": count,
                "stdoutSha256": sha256(unit["stdout"]),
                "stderrSha256": sha256(unit["stderr"]),
            }
            if unit["exitCode"] != 0 or count is None:
                errors.append("Core単体試験が成功しませんでした")
            evidence["cleanAfter"] = clean(directory)
            if not evidence["cleanBefore"] or not evidence["cleanAfter"]:
                errors.append("新しいチェックアウトが実行前後でクリーンではありません")
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        errors.append(str(error).split("\n")[0])
    evidence["errors"] = errors
    return evidence, errors


def run_performance_evidence(commit: str) -> tuple[dict, list[str]]:
    """対象コミットの新しいチェックアウトで受入済みの性能ベースラインを再監査する。"""
    errors: list[str] = []
    uv = shutil.which("uv")
    evidence = {
        "schemaVersion": 1,
        "commit": commit,
        "checkoutId": uuid.uuid4().hex,
        "cleanBefore": False,
        "cleanAfter": False,
        "exitCode": None,
        "report": None,
        "stdoutSha256": None,
        "stderrSha256": None,
        "errors": errors,
    }
    if uv is None:
        errors.append("`uv`が見つかりません")
        return evidence, errors
    try:
        with tempfile.TemporaryDirectory(prefix="bitz-gate-c-performance-") as temporary:
            directory = Path(temporary) / "checkout"
            checkout(commit, directory)
            evidence["cleanBefore"] = clean(directory)
            audit = run_command([uv, "run", BENCHMARK_AUDIT], directory, 600)
            evidence["exitCode"] = audit["exitCode"]
            evidence["stdoutSha256"] = sha256(audit["stdout"])
            evidence["stderrSha256"] = sha256(audit["stderr"])
            try:
                evidence["report"] = json.loads(audit["stdout"])
            except (ValueError, UnicodeDecodeError):
                errors.append("性能ベースラインの監査の標準出力がJSONではありません")
            if audit["exitCode"] != 0:
                errors.append("性能ベースラインの監査が成功しませんでした")
            evidence["cleanAfter"] = clean(directory)
            if not evidence["cleanBefore"] or not evidence["cleanAfter"]:
                errors.append("性能ベースラインの監査の新しいチェックアウトが実行前後でクリーンではありません")
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        errors.append(str(error).split("\n")[0])
    evidence["errors"] = errors
    return evidence, errors


def run_priority_closure_evidence(commit: str) -> tuple[dict, list[str]]:
    """対象コミットの新しいチェックアウトでP0/P1 11件の対応の証跡を再監査する。"""
    errors: list[str] = []
    uv = shutil.which("uv")
    evidence = {
        "schemaVersion": 1,
        "commit": commit,
        "checkoutId": uuid.uuid4().hex,
        "cleanBefore": False,
        "cleanAfter": False,
        "exitCode": None,
        "report": None,
        "stdoutSha256": None,
        "stderrSha256": None,
        "errors": errors,
    }
    if uv is None:
        errors.append("`uv`が見つかりません")
        return evidence, errors
    try:
        with tempfile.TemporaryDirectory(prefix="bitz-gate-c-priority-") as temporary:
            directory = Path(temporary) / "checkout"
            checkout(commit, directory)
            evidence["cleanBefore"] = clean(directory)
            audit = run_command([uv, "run", PRIORITY_CLOSURE_AUDIT], directory, 300)
            evidence["exitCode"] = audit["exitCode"]
            evidence["stdoutSha256"] = sha256(audit["stdout"])
            evidence["stderrSha256"] = sha256(audit["stderr"])
            try:
                evidence["report"] = json.loads(audit["stdout"])
            except (ValueError, UnicodeDecodeError):
                errors.append("P0/P1閉包監査の標準出力がJSONではありません")
            if audit["exitCode"] != 0:
                errors.append("P0/P1閉包監査が成功しませんでした")
            evidence["cleanAfter"] = clean(directory)
            if not evidence["cleanBefore"] or not evidence["cleanAfter"]:
                errors.append("P0/P1閉包監査の新しいチェックアウトが実行前後でクリーンではありません")
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        errors.append(str(error).split("\n")[0])
    evidence["errors"] = errors
    return evidence, errors


def write_json(value: dict, output: str | None) -> None:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if output:
        Path(output).write_text(text, encoding="utf-8")
    else:
        print(text, end="")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Gate Cの実行・集約コマンド。")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="1環境の新しいチェックアウトの証跡を作る")
    run.add_argument("--role", required=True, choices=gate_c.ROLES)
    run.add_argument("--environment-id", required=True)
    run.add_argument("--python", required=True, dest="python_spec")
    run.add_argument("--output")
    collect = commands.add_parser(
        "collect", help="`minimum`・`reference`と受入済みの性能ベースラインの証跡を集約する")
    collect.add_argument("--input", required=True, action="append")
    collect.add_argument("--commit")
    collect.add_argument("--output")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.command == "run":
        evidence, errors = run_evidence(args.role, args.environment_id, args.python_spec)
        write_json(evidence, args.output)
        return 0 if not errors else 1

    head = git("rev-parse", "--verify", "HEAD")
    commit = args.commit or (head.stdout.strip() if head.returncode == 0 else "")
    try:
        rows = [json.loads(Path(path).read_text(encoding="utf-8")) for path in args.input]
        manifest = load_reference_manifest_at(commit)
        performance, performance_errors = run_performance_evidence(commit)
        if performance_errors:
            raise RuntimeError(performance_errors[0])
        priority_closure, priority_errors = run_priority_closure_evidence(commit)
        if priority_errors:
            raise RuntimeError(priority_errors[0])
        report = gate_c.collect(rows, commit=commit, fixture_ids=step_ids(5),
                                reference_manifest=manifest,
                                performance_evidence=performance,
                                priority_closure_evidence=priority_closure)
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
        report = {"schemaVersion": 1, "commit": commit, "gateC": "Failed",
                  "gateCFoundation": "Failed", "gateCPerformance": "Failed",
                  "gateCPriorityClosure": "Failed",
                  "errors": [str(error).split("\n")[0]]}
        write_json(report, args.output)
        return 1
    write_json(report, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
