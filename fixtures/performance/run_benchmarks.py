#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["jsonschema==4.23.0", "attrs==26.1.0", "jsonschema-specifications==2025.9.1", "referencing==0.37.0", "rpds-py==2026.6.3", "typing-extensions==4.13.2"]
# ///
"""Core 1.0の性能caseを基準環境の隔離cgroupで逐次測定する。"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import errno
import json
import os
from pathlib import Path
import platform
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import tomllib
import uuid


ROOT = Path(__file__).resolve().parents[2]
PERFORMANCE = ROOT / "fixtures/performance"
PLAN_PATH = PERFORMANCE / "benchmark-plan.json"
RESULT_SCHEMA_PATH = PERFORMANCE / "schemas/run-result.schema.json"
WRAPPER_PATH = PERFORMANCE / "scripts/cgroup_wrapper.sh"
CGROUP_ROOT = Path("/sys/fs/cgroup")
CORE_PROJECT = Path("plugins/bitz-core")
DEFAULT_TIMEOUT_SECONDS = 600


class BenchmarkError(RuntimeError):
    """測定基盤、入力、または実行結果が受け入れられない。"""


@dataclass(frozen=True)
class Measurement:
    wall_ms: float
    peak_rss_bytes: int
    exit_code: int
    stdout: bytes = b""
    stderr: bytes = b""


@dataclass(frozen=True)
class Series:
    cold: Measurement
    measured: tuple[Measurement, ...]


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise BenchmarkError(f"JSONのrootがobjectではありません: {path}")
    return value


def command_output(argv: list[str]) -> str:
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=30)
    except OSError:
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def checked(argv: list[str], *, cwd: Path = ROOT, timeout: int = 300) -> subprocess.CompletedProcess:
    result = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        reason = result.stderr.strip() or result.stdout.strip() or f"終了コード {result.returncode}"
        raise BenchmarkError(f"{' '.join(argv[:3])} が失敗しました: {reason.splitlines()[0]}")
    return result


def git(*args: str, cwd: Path = ROOT) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=120)


def clean(cwd: Path) -> bool:
    result = git("status", "--porcelain", "--untracked-files=all", cwd=cwd)
    return result.returncode == 0 and result.stdout == ""


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
    return "WSL2" if "microsoft" in lowered and "wsl2" in lowered else "native-linux"


def storage_class(source: str, observed_platform: str) -> str:
    if observed_platform == "WSL2":
        return "wsl2-virtual-disk"
    if not source.startswith("/dev/"):
        return "unknown"
    rotational = command_output(["lsblk", "-no", "ROTA", source]).split()
    if rotational and set(rotational) == {"0"}:
        return "local-ssd"
    if "1" in rotational:
        return "local-hdd"
    return "unknown"


def observed_environment(cwd: Path) -> dict:
    kernel = platform.release()
    observed_platform = platform_class(kernel)
    source = command_output(["findmnt", "-n", "-o", "SOURCE", "-T", str(cwd)])
    filesystem = command_output(["findmnt", "-n", "-o", "FSTYPE", "-T", str(cwd)])
    try:
        ram_bytes = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    except (OSError, ValueError):
        ram_bytes = 0
    return {
        "os": platform.system(),
        "kernel": kernel,
        "platformClass": observed_platform,
        "architecture": platform.machine(),
        "cpuModel": cpu_model(),
        "logicalCores": os.cpu_count() or 0,
        "ramBytes": ram_bytes,
        "storageClass": storage_class(source, observed_platform),
        "filesystem": filesystem or "unknown",
        "python": platform.python_version(),
        "git": command_output(["git", "--version"]),
        "memoryAccounting": "cgroup-v2-process-tree",
    }


def _version(value: str) -> tuple[int, ...] | None:
    matched = re.search(r"(?:^|\s)(\d+(?:\.\d+)+)(?:\s|$)", value)
    return tuple(map(int, matched.group(1).split("."))) if matched else None


def _at_least(actual: tuple[int, ...], minimum: tuple[int, ...]) -> bool:
    width = max(len(actual), len(minimum))
    return actual + (0,) * (width - len(actual)) >= minimum + (0,) * (width - len(minimum))


def comparison_mismatches(environment: dict, manifest: dict) -> list[str]:
    comparison = manifest["comparisonKey"]
    tools = manifest["requiredTools"]
    exact = {
        "os": comparison["os"],
        "platformClass": comparison["platformClass"],
        "architecture": comparison["architecture"],
        "cpuModel": comparison["cpuModel"],
        "logicalCores": comparison["logicalCores"],
        "storageClass": comparison["storageClass"],
        "filesystem": comparison["filesystem"],
        "memoryAccounting": tools["memoryAccounting"],
    }
    mismatches = [name for name, expected in exact.items() if environment.get(name) != expected]
    if environment.get("ramBytes", 0) < comparison["minimumRamBytes"]:
        mismatches.append("ramBytes")
    expected_python = tools["pythonVersion"]
    if not expected_python.endswith(".x") or not environment.get("python", "").startswith(expected_python[:-1]):
        mismatches.append("python")
    actual_git = _version(environment.get("git", ""))
    minimum_git = _version(tools["minimumGitVersion"])
    if actual_git is None or minimum_git is None or not _at_least(actual_git, minimum_git):
        mismatches.append("git")
    return sorted(mismatches)


def resolve_cgroup_path(control_group: str, root: Path = CGROUP_ROOT) -> Path:
    if not control_group.startswith("/"):
        raise BenchmarkError("ControlGroupが絶対pathではありません")
    resolved_root = root.resolve()
    resolved = (resolved_root / control_group.lstrip("/")).resolve()
    if resolved != resolved_root and resolved_root not in resolved.parents:
        raise BenchmarkError("ControlGroupがcgroup rootの外を指しています")
    return resolved


def _show_unit(unit: str) -> dict[str, str]:
    result = subprocess.run(
        ["systemctl", "--user", "show", unit, "--property=ControlGroup",
         "--property=PrivateNetwork", "--property=ActiveState", "--property=SubState"],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        return {}
    values = {}
    for line in result.stdout.splitlines():
        name, separator, value = line.partition("=")
        if separator:
            values[name] = value
    return values


def _signal_fifo(path: Path, deadline: float) -> None:
    while time.monotonic() < deadline:
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_NONBLOCK)
        except OSError as error:
            if error.errno not in (errno.ENXIO, errno.ENOENT):
                raise
            time.sleep(0.01)
            continue
        try:
            os.write(descriptor, b"go\n")
        finally:
            os.close(descriptor)
        return
    raise BenchmarkError(f"cgroup wrapperのFIFOが待機状態になりません: {path.name}")


class CgroupExecutor:
    def __init__(self, wrapper: Path = WRAPPER_PATH, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS):
        self.wrapper = wrapper
        self.timeout_seconds = timeout_seconds

    def _requirements(self) -> None:
        if platform.system() != "Linux":
            raise BenchmarkError("性能runnerはLinux専用です")
        if not Path("/sys/fs/cgroup/cgroup.controllers").is_file():
            raise BenchmarkError("cgroup v2がありません")
        for command in ("systemd-run", "systemctl"):
            if shutil.which(command) is None:
                raise BenchmarkError(f"{command}がありません")
        state = command_output(["systemctl", "--user", "is-system-running"])
        if state not in ("running", "degraded"):
            raise BenchmarkError("user systemd managerが実行中ではありません")
        if not self.wrapper.is_file():
            raise BenchmarkError("cgroup wrapperがありません")

    def measure(self, argv: list[str], cwd: Path, environment: dict[str, str]) -> Measurement:
        self._requirements()
        unit = f"bitz-perf-{os.getpid()}-{uuid.uuid4().hex[:12]}.service"
        with tempfile.TemporaryDirectory(prefix="bitz-performance-control-") as temporary:
            control = Path(temporary)
            start_fifo = control / "start"
            release_fifo = control / "release"
            os.mkfifo(start_fifo, 0o600)
            os.mkfifo(release_fifo, 0o600)
            systemd = [
                "systemd-run", "--user", "--quiet", "--slice=-.slice",
                f"--unit={unit}", "--property=PrivateNetwork=yes",
                "--property=MemoryAccounting=yes", f"--working-directory={cwd}",
            ]
            for name, value in sorted(environment.items()):
                if "\n" in value or "\0" in value:
                    raise BenchmarkError(f"環境変数{name}に不正な値があります")
                systemd.append(f"--setenv={name}={value}")
            systemd.extend(["/bin/sh", str(self.wrapper), str(control), *argv])
            started = subprocess.run(systemd, capture_output=True, text=True, timeout=30)
            if started.returncode != 0:
                raise BenchmarkError(started.stderr.strip() or "transient unitを開始できません")

            deadline = time.monotonic() + self.timeout_seconds
            cgroup = None
            try:
                while time.monotonic() < deadline:
                    properties = _show_unit(unit)
                    control_group = properties.get("ControlGroup", "")
                    if control_group:
                        candidate = resolve_cgroup_path(control_group)
                        if (candidate / "memory.peak").is_file():
                            cgroup = candidate
                            break
                    time.sleep(0.01)
                if cgroup is None:
                    raise BenchmarkError("memory controller付きの専用cgroupを作成できません")
                if properties.get("PrivateNetwork") != "yes":
                    raise BenchmarkError("transient unitのnetworkが隔離されていません")

                baseline_peak = int((cgroup / "memory.peak").read_text().strip())
                start_ns = time.monotonic_ns()
                _signal_fifo(start_fifo, deadline)
                status_path = control / "status"
                while not status_path.is_file():
                    if time.monotonic() >= deadline:
                        raise BenchmarkError("性能caseがtimeoutしました")
                    time.sleep(0.005)
                elapsed_ms = (time.monotonic_ns() - start_ns) / 1_000_000
                final_peak = int((cgroup / "memory.peak").read_text().strip())
                processes = [line for line in (cgroup / "cgroup.procs").read_text().splitlines() if line]
                if len(processes) != 1:
                    raise BenchmarkError("性能case終了後に子processが残っています")
                return Measurement(
                    wall_ms=elapsed_ms,
                    peak_rss_bytes=max(0, final_peak - baseline_peak),
                    exit_code=int(status_path.read_text().strip()),
                    stdout=(control / "stdout").read_bytes(),
                    stderr=(control / "stderr").read_bytes(),
                )
            finally:
                try:
                    _signal_fifo(release_fifo, time.monotonic() + 1)
                except (BenchmarkError, OSError):
                    pass
                subprocess.run(["systemctl", "--user", "stop", unit],
                               capture_output=True, timeout=30)
                subprocess.run(["systemctl", "--user", "reset-failed", unit],
                               capture_output=True, timeout=30)


def isolated_environment(root: Path, index: int) -> dict[str, str]:
    home = root / f"home-{index}"
    cache = root / f"cache-{index}"
    temporary = root / f"tmp-{index}"
    for path in (home, cache, temporary):
        path.mkdir(parents=True)
    return {
        "HOME": str(home),
        "XDG_CACHE_HOME": str(cache),
        "TMPDIR": str(temporary),
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "PYTHONDONTWRITEBYTECODE": "1",
    }


def measure_series(
    executor,
    argv: list[str],
    cwd: Path,
    environment_root: Path,
    warmup_runs: int,
    measured_runs: int,
) -> Series:
    counter = 0

    def one() -> Measurement:
        nonlocal counter
        environment = isolated_environment(environment_root, counter)
        counter += 1
        return executor.measure(argv, cwd, environment)

    cold = one()
    for _ in range(warmup_runs):
        one()
    measured = tuple(one() for _ in range(measured_runs))
    return Series(cold=cold, measured=measured)


def build_case_result(case: dict, primary: Series, baseline: Series | None, comparable: bool) -> dict:
    wall = [sample.wall_ms for sample in primary.measured]
    memory = [sample.peak_rss_bytes for sample in primary.measured]
    exit_codes = [sample.exit_code for sample in primary.measured]
    result = {
        "id": case["id"],
        "coldWallMs": primary.cold.wall_ms,
        "wallMs": wall,
        "medianWallMs": statistics.median(wall),
        "peakRssBytes": memory,
        "maximumPeakRssBytes": max(memory),
        "exitCodes": exit_codes,
    }
    failed = primary.cold.exit_code != 0 or any(code != 0 for code in exit_codes)
    failed = failed or result["maximumPeakRssBytes"] > case["maxPeakRssBytes"]
    if baseline is None:
        failed = failed or result["medianWallMs"] > case["maxMedianWallMs"]
    else:
        baseline_wall = [sample.wall_ms for sample in baseline.measured]
        baseline_exit_codes = [sample.exit_code for sample in baseline.measured]
        result["baselineWallMs"] = baseline_wall
        result["baselineMedianWallMs"] = statistics.median(baseline_wall)
        result["baselineExitCodes"] = baseline_exit_codes
        result["derivedOverheadMs"] = max(
            0.0, result["medianWallMs"] - result["baselineMedianWallMs"])
        failed = failed or baseline.cold.exit_code != 0
        failed = failed or any(code != 0 for code in baseline_exit_codes)
        failed = failed or result["derivedOverheadMs"] > case["maxDerivedOverheadMs"]
    result["status"] = "failed" if failed else "passed" if comparable else "not_comparable"
    return result


def initialize_repository(root: Path) -> None:
    checked(["git", "init", "--quiet"], cwd=root)
    checked(["git", "config", "user.email", "performance@bitz.invalid"], cwd=root)
    checked(["git", "config", "user.name", "Bitz Performance"], cwd=root)
    paths = [name for name in (".spec", ".perf", "tests", "workspaces") if (root / name).exists()]
    checked(["git", "add", "--", *paths], cwd=root)
    checked(["git", "commit", "--quiet", "-m", "performance fixture"], cwd=root)


def prepare_case_tree(source: Path, destination: Path, dataset: dict, case: dict) -> None:
    shutil.copytree(source, destination)
    initialize_repository(destination)
    if case["id"] == "single-changed-check":
        benchmark = dataset["benchmark"]
        changed = destination / benchmark["changedPath"]
        changed.write_text(
            changed.read_text(encoding="utf-8") + benchmark["changedAppendUtf8"],
            encoding="utf-8",
        )


def generate_datasets(checkout: Path, destination: Path, plan: dict) -> tuple[dict[str, Path], dict[str, dict], dict[str, str]]:
    identifiers = sorted({case["dataset"] for case in plan["cases"]})
    roots = {}
    manifests = {}
    digests = {}
    for identifier in identifiers:
        manifest_path = checkout / f"fixtures/performance/datasets/{identifier}.json"
        manifest = load_json(manifest_path)
        output = destination / identifier
        generated = checked(
            [sys.executable, str(checkout / "fixtures/performance/scripts/generate_fixture.py"),
             str(manifest_path), str(output)],
            cwd=checkout, timeout=300,
        )
        report = json.loads(generated.stdout)
        if report["datasetId"] != identifier or report["treeDigest"] != manifest["expectedTreeDigest"]:
            raise BenchmarkError(f"{identifier}の生成結果がmanifestと一致しません")
        roots[identifier] = output
        manifests[identifier] = manifest
        digests[identifier] = report["treeDigest"]
    return roots, manifests, digests


def benchmark_cases(
    executor,
    plan: dict,
    dataset_roots: dict[str, Path],
    dataset_manifests: dict[str, dict],
    bitz: Path,
    work: Path,
    comparable: bool,
) -> list[dict]:
    results = []
    for case in plan["cases"]:
        case_root = work / f"case-{case['id']}"
        prepare_case_tree(dataset_roots[case["dataset"]], case_root,
                          dataset_manifests[case["dataset"]], case)
        primary = measure_series(
            executor, [str(bitz), *case["argv"]], case_root,
            work / f"environment-{case['id']}-primary",
            plan["warmupRuns"], plan["measuredRuns"],
        )
        baseline = None
        if "baseline" in case:
            baseline = measure_series(
                executor, case["baseline"], case_root,
                work / f"environment-{case['id']}-baseline",
                plan["warmupRuns"], plan["measuredRuns"],
            )
        results.append(build_case_result(case, primary, baseline, comparable))
    return results


def prepare_checkout(commit: str, destination: Path) -> Path:
    checked(["git", "clone", "--quiet", "--no-checkout", str(ROOT), str(destination)])
    checked(["git", "checkout", "--quiet", "--detach", commit], cwd=destination)
    checked(["uv", "sync", "--frozen", "--python", "3.12", "--project",
             str(destination / CORE_PROJECT)], cwd=destination, timeout=300)
    bitz = destination / CORE_PROJECT / ".venv/bin/bitz"
    if not bitz.is_file():
        raise BenchmarkError("fresh checkoutにbitz実行体を構築できません")
    return bitz


def core_version(checkout: Path) -> str:
    value = tomllib.loads((checkout / CORE_PROJECT / "pyproject.toml").read_text(encoding="utf-8"))
    return value["project"]["version"]


def validate_result_schema(result: dict, schema_path: Path = RESULT_SCHEMA_PATH) -> None:
    from jsonschema import Draft202012Validator, FormatChecker
    validator = Draft202012Validator(load_json(schema_path), format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(result), key=lambda error: list(error.path))
    if errors:
        raise BenchmarkError(f"測定結果がschemaに適合しません: {errors[0].message}")


def validate_accepted_baseline(
    result: dict,
    plan: dict,
    environment_manifest: dict,
    dataset_manifests: dict[str, dict],
) -> dict:
    """受入済みbaselineが測定値から独立に再計算できることを検査する。"""
    if result.get("environmentId") != environment_manifest.get("environmentId"):
        raise BenchmarkError("baselineのenvironmentIdが基準環境manifestと一致しません")
    mismatches = comparison_mismatches(
        result.get("observedEnvironment", {}), environment_manifest)
    if result.get("comparability") != "comparable" or result.get("comparisonMismatches") != []:
        raise BenchmarkError("baselineが比較可能な測定結果ではありません")
    if mismatches:
        raise BenchmarkError(
            f"baselineの観測環境が基準環境manifestと一致しません: {', '.join(mismatches)}")

    expected_digests = {
        identifier: manifest["expectedTreeDigest"]
        for identifier, manifest in sorted(dataset_manifests.items())
    }
    if result.get("datasetDigests") != expected_digests:
        raise BenchmarkError("baselineのdataset digestが現在のmanifestと一致しません")

    cases = result.get("cases", [])
    expected_ids = [case["id"] for case in plan["cases"]]
    if [case.get("id") for case in cases] != expected_ids:
        raise BenchmarkError("baselineのcase集合または順序がbenchmark planと一致しません")

    for definition, measured in zip(plan["cases"], cases, strict=True):
        identifier = definition["id"]
        wall = measured.get("wallMs", [])
        peak = measured.get("peakRssBytes", [])
        if measured.get("status") != "passed":
            raise BenchmarkError(f"baselineの{identifier}がpassedではありません")
        if any(code != 0 for code in measured.get("exitCodes", [])):
            raise BenchmarkError(f"baselineの{identifier}に非0の終了コードがあります")
        if measured.get("medianWallMs") != statistics.median(wall):
            raise BenchmarkError(f"baselineの{identifier}の中央値を再計算できません")
        if measured.get("maximumPeakRssBytes") != max(peak):
            raise BenchmarkError(f"baselineの{identifier}のpeak RSS最大値を再計算できません")
        if measured["maximumPeakRssBytes"] > definition["maxPeakRssBytes"]:
            raise BenchmarkError(f"baselineの{identifier}がmemory SLOを超過しています")

        if "baseline" not in definition:
            if measured["medianWallMs"] > definition["maxMedianWallMs"]:
                raise BenchmarkError(f"baselineの{identifier}がelapsed time SLOを超過しています")
            continue

        baseline_wall = measured.get("baselineWallMs", [])
        if any(code != 0 for code in measured.get("baselineExitCodes", [])):
            raise BenchmarkError(f"baselineの{identifier}の比較commandが失敗しています")
        if measured.get("baselineMedianWallMs") != statistics.median(baseline_wall):
            raise BenchmarkError(f"baselineの{identifier}の比較中央値を再計算できません")
        overhead = max(0.0, measured["medianWallMs"] - measured["baselineMedianWallMs"])
        if measured.get("derivedOverheadMs") != overhead:
            raise BenchmarkError(f"baselineの{identifier}のoverheadを再計算できません")
        if overhead > definition["maxDerivedOverheadMs"]:
            raise BenchmarkError(f"baselineの{identifier}がoverhead SLOを超過しています")

    return {
        "coreCommit": result["coreCommit"],
        "environmentId": result["environmentId"],
        "cases": len(cases),
        "status": "Passed",
    }


def isolation_probe(executor: CgroupExecutor) -> dict:
    with tempfile.TemporaryDirectory(prefix="bitz-performance-probe-") as temporary:
        root = Path(temporary)
        environment = isolated_environment(root, 0)
        script = (
            "import os,sys;"
            "interfaces=set(os.listdir('/sys/class/net'));"
            "sys.exit(0 if interfaces <= {'lo'} else 1)"
        )
        measurement = executor.measure([sys.executable, "-c", script], root, environment)
    if measurement.exit_code != 0:
        raise BenchmarkError("PrivateNetwork内にloopback以外のinterfaceがあります")
    return {
        "networkDisabled": True,
        "memoryAccounting": "cgroup-v2-process-tree",
        "parallelCases": False,
        "persistentCoreCache": False,
        "report": False,
    }


def probe() -> dict:
    plan = load_json(PLAN_PATH)
    manifest = load_json(PERFORMANCE / plan["environment"])
    environment = observed_environment(ROOT)
    mismatches = comparison_mismatches(environment, manifest)
    isolation = isolation_probe(CgroupExecutor())
    return {
        "status": "Passed",
        "environmentId": manifest["environmentId"],
        "observedEnvironment": environment,
        "comparability": "comparable" if not mismatches else "not_comparable",
        "comparisonMismatches": mismatches,
        "isolation": isolation,
    }


def run(output: Path) -> tuple[dict, int]:
    if not clean(ROOT):
        raise BenchmarkError("性能測定はcleanなcommit済みtreeから実行してください")
    head = git("rev-parse", "--verify", "HEAD")
    if head.returncode != 0:
        raise BenchmarkError("HEAD commitを取得できません")
    commit = head.stdout.strip()
    plan = load_json(PLAN_PATH)
    manifest = load_json(PERFORMANCE / plan["environment"])
    environment = observed_environment(ROOT)
    mismatches = comparison_mismatches(environment, manifest)
    comparability = "comparable" if not mismatches else "not_comparable"
    executor = CgroupExecutor()
    isolation_probe(executor)

    with tempfile.TemporaryDirectory(prefix="bitz-performance-run-") as temporary:
        work = Path(temporary)
        checkout = work / "checkout"
        bitz = prepare_checkout(commit, checkout)
        datasets, manifests, digests = generate_datasets(
            checkout, work / "datasets", plan)
        cases = benchmark_cases(
            executor, plan, datasets, manifests, bitz, work,
            comparable=not mismatches,
        )
        if not clean(checkout):
            raise BenchmarkError("fresh checkoutが測定後にdirtyです")
        result = {
            "schemaVersion": "1.0",
            "startedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "environmentId": manifest["environmentId"],
            "datasetDigests": digests,
            "coreVersion": core_version(checkout),
            "coreCommit": commit,
            "observedEnvironment": environment,
            "comparability": comparability,
            "comparisonMismatches": mismatches,
            "cases": cases,
        }
    validate_result_schema(result)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary_output = output.with_name(f".{output.name}.{uuid.uuid4().hex}.tmp")
    temporary_output.write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary_output, output)
    return result, 0 if all(case["status"] == "passed" for case in result["cases"]) else 1


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Core 1.0性能runner")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("probe", help="基準環境と隔離機能だけを検査する")
    execute = commands.add_parser("run", help="全性能caseを逐次測定する")
    execute.add_argument("--output", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        if args.command == "probe":
            print(json.dumps(probe(), ensure_ascii=False, sort_keys=True, indent=2))
            return 0
        result, code = run(args.output)
        print(json.dumps({
            "output": str(args.output),
            "coreCommit": result["coreCommit"],
            "comparability": result["comparability"],
            "statuses": {case["id"]: case["status"] for case in result["cases"]},
        }, ensure_ascii=False, sort_keys=True, indent=2))
        return code
    except (BenchmarkError, OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"performance runner: {str(error).splitlines()[0]}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
