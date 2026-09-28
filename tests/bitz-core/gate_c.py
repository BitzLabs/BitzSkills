"""Gate Cのfresh-checkout証拠をfail-closedで集約する。"""
from __future__ import annotations

import copy
import hashlib
import json
import re

ROLES = ("minimum", "reference")
MINIMUM_ENVIRONMENT_ID = "minimum-cpython-3-12"
PYTHON_MINOR = (3, 12)
PENDING = [
    "Small Flow and Markdown comparison evidence",
    "unresolved P0/P1 closure",
]
SHA256 = re.compile(r"^[0-9a-f]{64}$")
FINGERPRINT_FIELDS = (
    "system",
    "kernel",
    "machine",
    "cpuModel",
    "logicalCores",
    "platformClass",
    "storageClass",
    "filesystem",
)


def _error(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _python_minor(value: str) -> tuple[int, int] | None:
    matched = re.match(r"^(\d+)\.(\d+)(?:\.|$)", value)
    return tuple(map(int, matched.groups())) if matched else None


def _normalized_conformance(report: dict) -> dict:
    value = copy.deepcopy(report)
    value.pop("core", None)
    value.pop("environment", None)
    for fixture in value.get("fixtures", []):
        fixture.pop("durationMs", None)
    return value


def _digest(value: dict) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def manifest_digest(manifest: dict) -> str:
    return _digest(manifest)


def environment_fingerprint(environment: dict) -> str:
    values = {}
    for field in FINGERPRINT_FIELDS:
        value = environment.get(field)
        if field == "logicalCores":
            _error(isinstance(value, int) and value > 0,
                   f"environment.{field}が不正です")
        else:
            _error(isinstance(value, str) and bool(value),
                   f"environment.{field}が不正です")
        values[field] = value
    return _digest(values)


def _git_version(value: str) -> tuple[int, ...] | None:
    matched = re.search(r"(?:^|\s)(\d+(?:\.\d+)+)(?:\s|$)", value)
    return tuple(map(int, matched.group(1).split("."))) if matched else None


def _version_at_least(actual: tuple[int, ...], minimum: tuple[int, ...]) -> bool:
    width = max(len(actual), len(minimum))
    return actual + (0,) * (width - len(actual)) >= minimum + (0,) * (width - len(minimum))


def validate_performance_evidence(row: dict, *, commit: str,
                                  reference_manifest: dict) -> dict:
    """fresh checkoutで実行した性能fixture監査の証拠を検査する。"""
    _error(isinstance(row, dict), "性能baseline監査証拠がありません")
    _error(row.get("schemaVersion") == 1, "性能baseline監査証拠のschemaVersionが不正です")
    _error(row.get("commit") == commit, "性能baseline監査証拠のcommitが対象commitと一致しません")
    _error(isinstance(row.get("checkoutId"), str) and row["checkoutId"],
           "性能baseline監査証拠のcheckoutIdがありません")
    _error(row.get("cleanBefore") is True and row.get("cleanAfter") is True,
           "性能baseline監査のfresh checkoutがcleanではありません")
    _error(row.get("errors") == [], "性能baseline監査証拠にerrorがあります")
    _error(row.get("exitCode") == 0, "性能baseline監査の終了コードが0ではありません")
    for name in ("stdoutSha256", "stderrSha256"):
        _error(isinstance(row.get(name), str) and SHA256.fullmatch(row[name]) is not None,
               f"性能baseline監査証拠の{name}が不正です")

    report = row.get("report")
    _error(isinstance(report, dict) and report.get("status") == "Passed",
           "性能baseline監査がPassedではありません")
    report_bytes = (json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    _error(row["stdoutSha256"] == hashlib.sha256(report_bytes).hexdigest(),
           "性能baseline監査reportのhashが標準出力と一致しません")
    _error(isinstance(report.get("schemas"), int) and report["schemas"] > 0,
           "性能baseline監査のSchema件数がありません")
    _error(isinstance(report.get("inputs"), int) and report["inputs"] > 0,
           "性能baseline監査の入力件数がありません")
    _error(report.get("generationRunsPerDataset") == 2,
           "性能datasetの決定性検査が2回実行されていません")
    _error(isinstance(report.get("shapeRejectionChecks"), int)
           and report["shapeRejectionChecks"] > 0,
           "性能datasetの形状陰性対照がありません")

    baselines = report.get("baselines")
    _error(isinstance(baselines, list) and baselines,
           "受入済み性能baselineがありません")
    expected_environment = reference_manifest.get("environmentId")
    identities = set()
    summaries = []
    for baseline in baselines:
        _error(isinstance(baseline, dict), "性能baselineの監査結果がobjectではありません")
        core_commit = baseline.get("coreCommit")
        environment_id = baseline.get("environmentId")
        _error(isinstance(core_commit, str)
               and re.fullmatch(r"[0-9a-f]{40}", core_commit) is not None,
               "性能baselineのcoreCommitが不正です")
        _error(environment_id == expected_environment,
               "性能baselineのenvironmentIdが基準環境manifestと一致しません")
        _error(isinstance(baseline.get("cases"), int) and baseline["cases"] > 0,
               "性能baselineのcase件数がありません")
        _error(baseline.get("status") == "Passed", "性能baselineがPassedではありません")
        _error(isinstance(baseline.get("sha256"), str)
               and SHA256.fullmatch(baseline["sha256"]) is not None,
               "性能baselineのsha256が不正です")
        identity = (environment_id, core_commit)
        _error(identity not in identities, "性能baselineの監査結果が重複しています")
        identities.add(identity)
        summaries.append({
            "environmentId": environment_id,
            "coreCommit": core_commit,
            "cases": baseline["cases"],
            "sha256": baseline["sha256"],
        })
    return {
        "checkoutId": row["checkoutId"],
        "validationReportSha256": row["stdoutSha256"],
        "baselines": summaries,
    }


def validate_reference_environment(environment: dict, manifest: dict) -> None:
    _error(isinstance(manifest, dict), "基準環境manifestがありません")
    _error(manifest.get("schemaVersion") == "1.0", "基準環境manifestのschemaVersionが不正です")
    comparison = manifest.get("comparisonKey")
    tools = manifest.get("requiredTools")
    _error(isinstance(comparison, dict) and isinstance(tools, dict),
           "基準環境manifestの比較条件がありません")

    exact = {
        "system": ("os", comparison.get("os")),
        "platformClass": ("platformClass", comparison.get("platformClass")),
        "machine": ("architecture", comparison.get("architecture")),
        "cpuModel": ("cpuModel", comparison.get("cpuModel")),
        "logicalCores": ("logicalCores", comparison.get("logicalCores")),
        "storageClass": ("storageClass", comparison.get("storageClass")),
        "filesystem": ("filesystem", comparison.get("filesystem")),
        "implementation": ("pythonImplementation", tools.get("pythonImplementation")),
        "memoryAccounting": ("memoryAccounting", tools.get("memoryAccounting")),
    }
    for observed, (manifest_name, expected) in exact.items():
        _error(environment.get(observed) == expected,
               f"基準環境の{manifest_name}がmanifestと一致しません")

    ram = environment.get("ramBytes")
    minimum_ram = comparison.get("minimumRamBytes")
    _error(isinstance(ram, int) and isinstance(minimum_ram, int) and ram >= minimum_ram,
           "基準環境のRAMがmanifestの下限を満たしません")
    expected_python = tools.get("pythonVersion", "")
    _error(expected_python.endswith(".x")
           and environment.get("python", "").startswith(expected_python[:-1]),
           "基準環境のPythonがmanifestと一致しません")
    actual_git = _git_version(environment.get("git", ""))
    minimum_git = _git_version(str(tools.get("minimumGitVersion", "")))
    _error(actual_git is not None and minimum_git is not None
           and _version_at_least(actual_git, minimum_git),
           "基準環境のGitがmanifestの下限を満たしません")


def conformance_digest(report: dict) -> str:
    return _digest(_normalized_conformance(report))


def validate_evidence(row: dict, *, commit: str, fixture_ids: list[str],
                      reference_manifest: dict) -> dict:
    _error(isinstance(row, dict), "証拠はobjectでなければなりません")
    _error(row.get("schemaVersion") == 1, "証拠のschemaVersionが不正です")
    _error(row.get("commit") == commit, "証拠のcommitが対象commitと一致しません")
    role = row.get("role")
    _error(role in ROLES, "未知の環境roleです")
    expected_environment_id = (MINIMUM_ENVIRONMENT_ID if role == "minimum"
                               else reference_manifest.get("environmentId"))
    _error(row.get("environmentId") == expected_environment_id,
           "environmentIdが環境roleの規定値と一致しません")
    _error(isinstance(row.get("requestedPython"), str) and row["requestedPython"],
           "要求したPython実行体が記録されていません")
    _error(isinstance(row.get("checkoutId"), str) and row["checkoutId"],
           "checkoutIdがありません")
    _error(row.get("cleanBefore") is True and row.get("cleanAfter") is True,
           "fresh checkoutがcleanではありません")
    _error(row.get("errors") == [], "実行証拠にerrorがあります")

    environment = row.get("environment")
    _error(isinstance(environment, dict), "環境証拠がありません")
    _error(environment.get("system") == "Linux", "Gate Cの検証環境はLinuxでなければなりません")
    _error(environment.get("implementation") == "CPython", "CPythonの証拠ではありません")
    _error(_python_minor(environment.get("python", "")) == PYTHON_MINOR,
           "CPython 3.12の証拠ではありません")
    _error(isinstance(environment.get("executable"), str) and environment["executable"],
           "Python実行体のpathがありません")
    _error(isinstance(environment.get("machine"), str) and environment["machine"],
           "machineの環境証拠がありません")
    _error(isinstance(environment.get("git"), str) and environment["git"],
           "Gitの環境証拠がありません")
    fingerprint = environment_fingerprint(environment)
    if role == "reference":
        _error(row.get("referenceManifestSha256") == manifest_digest(reference_manifest),
               "基準環境manifestのhashが対象commitと一致しません")
        validate_reference_environment(environment, reference_manifest)

    conformance = row.get("conformance")
    _error(isinstance(conformance, dict), "適合試験の証拠がありません")
    _error(conformance.get("exitCode") == 0, "適合試験の終了コードが0ではありません")
    report = conformance.get("report")
    _error(isinstance(report, dict), "適合試験reportがありません")
    _error(report.get("allPassed") is True, "適合試験が全件成功していません")
    fixtures = report.get("fixtures")
    _error(isinstance(fixtures, list), "適合試験のfixture結果がありません")
    _error([entry.get("id") for entry in fixtures] == fixture_ids,
           "適合試験のfixture集合または順序が全matrixと一致しません")
    _error(all(entry.get("result") == "passed" and entry.get("differences") == []
               for entry in fixtures), "適合試験に非成功または差分があります")
    counts = report.get("counts")
    _error(counts == {"passed": len(fixture_ids), "failed": 0, "error": 0},
           "適合試験の件数が結果と一致しません")
    report_environment = report.get("environment")
    _error(isinstance(report_environment, dict), "適合試験の環境情報がありません")
    _error(_python_minor(report_environment.get("python", "")) == PYTHON_MINOR,
           "適合試験がCPython 3.12で実行されていません")
    _error(isinstance(conformance.get("stderrSha256"), str)
           and SHA256.fullmatch(conformance["stderrSha256"]) is not None,
           "適合試験のstderrSha256が不正です")

    unit = row.get("unit")
    _error(isinstance(unit, dict), "Core単体試験の証拠がありません")
    _error(unit.get("exitCode") == 0, "Core単体試験の終了コードが0ではありません")
    _error(isinstance(unit.get("testsRun"), int) and unit["testsRun"] > 0,
           "Core単体試験の実行件数がありません")
    for name in ("stdoutSha256", "stderrSha256"):
        _error(isinstance(unit.get(name), str) and SHA256.fullmatch(unit[name]) is not None,
               f"Core単体試験の{name}が不正です")

    return {
        "role": role,
        "environmentId": row["environmentId"],
        "environmentFingerprint": fingerprint,
        "checkoutId": row["checkoutId"],
        "python": environment["python"],
        "executable": environment["executable"],
        "fixtureCount": len(fixtures),
        "unitTests": unit["testsRun"],
        "conformanceSha256": conformance_digest(report),
    }


def collect(rows: list[dict], *, commit: str, fixture_ids: list[str],
            reference_manifest: dict, performance_evidence: dict) -> dict:
    _error(isinstance(reference_manifest, dict), "基準環境manifestがありません")
    _error(re.fullmatch(r"[0-9a-f]{40}", commit) is not None, "対象commitが40桁SHAではありません")
    _error(len(rows) == len(ROLES), "下限環境と基準環境の2件の証拠が必要です")
    validated = [validate_evidence(row, commit=commit, fixture_ids=fixture_ids,
                                   reference_manifest=reference_manifest) for row in rows]
    by_role = {entry["role"]: entry for entry in validated}
    _error(set(by_role) == set(ROLES) and len(by_role) == len(validated),
           "下限環境と基準環境が1件ずつ必要です")
    _error(len({entry["environmentId"] for entry in validated}) == len(ROLES),
           "環境roleごとに異なるenvironmentIdが必要です")
    _error(len({entry["checkoutId"] for entry in validated}) == len(ROLES),
           "環境roleごとに独立したfresh checkoutが必要です")
    _error(len({entry["environmentFingerprint"] for entry in validated}) == len(ROLES),
           "下限環境と基準環境が同じenvironment fingerprintです")
    _error(len({entry["conformanceSha256"] for entry in validated}) == 1,
           "下限環境と基準環境の適合結果が一致しません")
    _error(len({entry["unitTests"] for entry in validated}) == 1,
           "下限環境と基準環境のCore単体試験件数が一致しません")

    performance = validate_performance_evidence(
        performance_evidence, commit=commit, reference_manifest=reference_manifest)

    environments = {role: by_role[role] for role in ROLES}
    return {
        "schemaVersion": 1,
        "commit": commit,
        "gateC": "Pending",
        "gateCFoundation": "Passed",
        "gateCPerformance": "Passed",
        "fixtureCount": len(fixture_ids),
        "conformanceSha256": validated[0]["conformanceSha256"],
        "referenceManifestSha256": manifest_digest(reference_manifest),
        "environments": environments,
        "performance": performance,
        "covered": [
            "all conformance fixtures on CPython 3.12 minimum and reference roles",
            "Core unit tests on Linux in both roles",
            "cross-environment conformance determinism",
            "reference environment manifest and observed comparison key",
            "read-only/report/cache/timeout/signal/child-process acceptance in the full matrix",
            "accepted performance baseline and fixed SLO audit",
        ],
        "pending": list(PENDING),
        "errors": [],
    }
