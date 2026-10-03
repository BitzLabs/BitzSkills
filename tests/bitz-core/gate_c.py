"""Gate Cの新しいチェックアウトの証跡を、失敗時に通さない扱いで集約する。"""
from __future__ import annotations

import copy
import hashlib
import json
import re

ROLES = ("minimum", "reference")
MINIMUM_ENVIRONMENT_ID = "minimum-cpython-3-12"
PYTHON_MINOR = (3, 12)
PRIORITY_RULES = {
    "P0": {
        "FIN-FIX-001": {"allConformance": True, "evidence": "all-conformance"},
        "FIN-DIAG-001": {"prefixes": ("SINGLE-089", "SINGLE-090", "SINGLE-091",
                                             "SINGLE-092", "SINGLE-093", "SINGLE-094",
                                             "SINGLE-095"),
                         "evidence": "conformance-and-diagnostic-audit"},
        "FIN-EAI-001": {"prefixes": tuple(f"SINGLE-{number:03d}" for number in range(96, 104)),
                        "evidence": "conformance"},
        "FIN-OUT-001": {"prefixes": ("SINGLE-104", "SINGLE-105", "SINGLE-106"),
                        "evidence": "conformance"},
        "FIN-TARGET-001": {"prefixes": tuple(f"SINGLE-{number:03d}" for number in range(107, 114)),
                           "evidence": "conformance"},
        "FIN-FM-001": {"prefixes": tuple(f"SINGLE-{number:03d}" for number in range(114, 121)),
                       "evidence": "conformance"},
    },
    "P1": {
        "FIN-DIGEST-001": {"exact": ("SINGLE-042", "MULTI-002-01", "SINGLE-121",
                                      "SINGLE-122", "SINGLE-123", "SINGLE-124"),
                           "evidence": "conformance"},
        "FIN-IO-001": {"prefixes": ("SINGLE-125",), "evidence": "conformance"},
        "FIN-PROC-001": {"prefixes": ("SINGLE-126",), "evidence": "conformance"},
        "FIN-CLI-001": {"prefixes": ("SINGLE-127",), "evidence": "conformance"},
        "FIN-PERF-001": {"performance": True, "evidence": "performance"},
    },
}
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
                   f"`environment.{field}`が不正です")
        else:
            _error(isinstance(value, str) and bool(value),
                   f"`environment.{field}`が不正です")
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
    """新しいチェックアウトで実行した性能fixtureの監査の証跡を検査する。"""
    _error(isinstance(row, dict), "性能ベースラインの監査の証跡がありません")
    _error(row.get("schemaVersion") == 1, "性能ベースラインの監査の証跡の`schemaVersion`が不正です")
    _error(row.get("commit") == commit, "性能ベースラインの監査の証跡の`commit`が対象コミットと一致しません")
    _error(isinstance(row.get("checkoutId"), str) and row["checkoutId"],
           "性能ベースラインの監査の証跡の`checkoutId`がありません")
    _error(row.get("cleanBefore") is True and row.get("cleanAfter") is True,
           "性能ベースラインの監査の新しいチェックアウトがクリーンではありません")
    _error(row.get("errors") == [], "性能ベースラインの監査の証跡にエラーがあります")
    _error(row.get("exitCode") == 0, "性能ベースラインの監査の終了コードが0ではありません")
    for name in ("stdoutSha256", "stderrSha256"):
        _error(isinstance(row.get(name), str) and SHA256.fullmatch(row[name]) is not None,
               f"性能ベースラインの監査の証跡の{name}が不正です")

    report = row.get("report")
    _error(isinstance(report, dict) and report.get("status") == "Passed",
           "性能ベースラインの監査が`Passed`ではありません")
    report_bytes = (json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    _error(row["stdoutSha256"] == hashlib.sha256(report_bytes).hexdigest(),
           "性能ベースラインの監査のレポートのハッシュ値が標準出力と一致しません")
    _error(isinstance(report.get("schemas"), int) and report["schemas"] > 0,
           "性能ベースラインの監査のスキーマ件数がありません")
    _error(isinstance(report.get("inputs"), int) and report["inputs"] > 0,
           "性能ベースラインの監査の入力件数がありません")
    _error(report.get("generationRunsPerDataset") == 2,
           "性能データセットの決定性検査が2回実行されていません")
    _error(isinstance(report.get("shapeRejectionChecks"), int)
           and report["shapeRejectionChecks"] > 0,
           "性能データセットの形状陰性対照がありません")

    baselines = report.get("baselines")
    _error(isinstance(baselines, list) and baselines,
           "受入済みの性能ベースラインがありません")
    expected_environment = reference_manifest.get("environmentId")
    identities = set()
    summaries = []
    for baseline in baselines:
        _error(isinstance(baseline, dict), "性能ベースラインの監査結果がオブジェクトではありません")
        core_commit = baseline.get("coreCommit")
        environment_id = baseline.get("environmentId")
        _error(isinstance(core_commit, str)
               and re.fullmatch(r"[0-9a-f]{40}", core_commit) is not None,
               "性能ベースラインの`coreCommit`が不正です")
        _error(environment_id == expected_environment,
               "性能ベースラインの`environmentId`が基準環境のマニフェストと一致しません")
        _error(isinstance(baseline.get("cases"), int) and baseline["cases"] > 0,
               "性能ベースラインのケース件数がありません")
        _error(baseline.get("status") == "Passed", "性能ベースラインが`Passed`ではありません")
        _error(isinstance(baseline.get("sha256"), str)
               and SHA256.fullmatch(baseline["sha256"]) is not None,
               "性能ベースラインの`sha256`が不正です")
        identity = (environment_id, core_commit)
        _error(identity not in identities, "性能ベースラインの監査結果が重複しています")
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


def _closure_fixture_ids(fixture_ids: list[str], rule: dict) -> list[str]:
    if rule.get("allConformance"):
        return fixture_ids
    selected = [identifier for identifier in rule.get("exact", ()) if identifier in fixture_ids]
    for prefix in rule.get("prefixes", ()):
        selected.extend(identifier for identifier in fixture_ids
                        if identifier == prefix or identifier.startswith(prefix + "-"))
    return list(dict.fromkeys(selected))


def validate_priority_closure_evidence(row: dict, *, commit: str,
                                       fixture_ids: list[str]) -> dict:
    """対象コミットで再計算した提案25のP0/P1の閉包の証跡を検査する。"""
    _error(isinstance(row, dict), "P0/P1閉包の証跡がありません")
    _error(row.get("schemaVersion") == 1, "P0/P1閉包の証跡の`schemaVersion`が不正です")
    _error(row.get("commit") == commit, "P0/P1閉包の証跡の`commit`が対象コミットと一致しません")
    _error(isinstance(row.get("checkoutId"), str) and row["checkoutId"],
           "P0/P1閉包の証跡の`checkoutId`がありません")
    _error(row.get("cleanBefore") is True and row.get("cleanAfter") is True,
           "P0/P1閉包監査の新しいチェックアウトがクリーンではありません")
    _error(row.get("exitCode") == 0, "P0/P1閉包監査の終了コードが0ではありません")
    _error(row.get("errors") == [], "P0/P1閉包監査の証跡にエラーがあります")
    for name in ("stdoutSha256", "stderrSha256"):
        _error(isinstance(row.get(name), str) and SHA256.fullmatch(row[name]) is not None,
               f"P0/P1閉包監査の{name}が不正です")

    report = row.get("report")
    _error(isinstance(report, dict), "P0/P1閉包監査のレポートがありません")
    _error(report.get("status") == "Passed" and report.get("errors") == [],
           "P0/P1閉包監査が通過していません")
    report_bytes = (json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    _error(row["stdoutSha256"] == hashlib.sha256(report_bytes).hexdigest(),
           "P0/P1閉包監査のレポートのハッシュ値が標準出力と一致しません")
    _error(report.get("source") ==
           "docs/04.提案資料/25_Core-1.0実装前最終reviewと修正提案.md",
           "P0/P1閉包監査の`source`が不正です")
    expected_source = {priority: list(rules) for priority, rules in PRIORITY_RULES.items()}
    _error(report.get("sourceFindings") == expected_source,
           "提案25のP0/P1集合が閉包対象と一致しません")
    _error(report.get("diagnosticCoverage") == "Passed",
           "診断の意味の網羅のレビューが通過していません")
    _error(report.get("fixtureCount") == len(fixture_ids),
           "P0/P1閉包監査のfixture件数が全matrixと一致しません")

    findings = report.get("findings")
    _error(isinstance(findings, list), "P0/P1閉包監査の`findings`がありません")
    expected_rows = []
    for priority, rules in PRIORITY_RULES.items():
        for identifier, rule in rules.items():
            expected_rows.append({
                "id": identifier,
                "priority": priority,
                "evidence": rule["evidence"],
                "fixtureIds": _closure_fixture_ids(fixture_ids, rule),
            })
    _error(findings == expected_rows, "P0/P1閉包監査の個別の証跡が一致しません")
    return {
        "status": "Passed",
        "findingCount": len(findings),
        "findings": [{"id": item["id"], "priority": item["priority"],
                      "evidence": item["evidence"], "fixtureCount": len(item["fixtureIds"])}
                     for item in findings],
        "stdoutSha256": row["stdoutSha256"],
    }


def validate_reference_environment(environment: dict, manifest: dict) -> None:
    _error(isinstance(manifest, dict), "基準環境のマニフェストがありません")
    _error(manifest.get("schemaVersion") == "1.0", "基準環境のマニフェストの`schemaVersion`が不正です")
    comparison = manifest.get("comparisonKey")
    tools = manifest.get("requiredTools")
    _error(isinstance(comparison, dict) and isinstance(tools, dict),
           "基準環境のマニフェストの比較条件がありません")

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
               f"基準環境の{manifest_name}がマニフェストと一致しません")

    ram = environment.get("ramBytes")
    minimum_ram = comparison.get("minimumRamBytes")
    _error(isinstance(ram, int) and isinstance(minimum_ram, int) and ram >= minimum_ram,
           "基準環境のRAMがマニフェストの下限を満たしません")
    expected_python = tools.get("pythonVersion", "")
    _error(expected_python.endswith(".x")
           and environment.get("python", "").startswith(expected_python[:-1]),
           "基準環境のPythonがマニフェストと一致しません")
    actual_git = _git_version(environment.get("git", ""))
    minimum_git = _git_version(str(tools.get("minimumGitVersion", "")))
    _error(actual_git is not None and minimum_git is not None
           and _version_at_least(actual_git, minimum_git),
           "基準環境のGitがマニフェストの下限を満たしません")


def conformance_digest(report: dict) -> str:
    return _digest(_normalized_conformance(report))


def validate_evidence(row: dict, *, commit: str, fixture_ids: list[str],
                      reference_manifest: dict) -> dict:
    _error(isinstance(row, dict), "証跡はオブジェクトでなければなりません")
    _error(row.get("schemaVersion") == 1, "証跡の`schemaVersion`が不正です")
    _error(row.get("commit") == commit, "証跡の`commit`が対象コミットと一致しません")
    role = row.get("role")
    _error(role in ROLES, "未知の環境のロールです")
    expected_environment_id = (MINIMUM_ENVIRONMENT_ID if role == "minimum"
                               else reference_manifest.get("environmentId"))
    _error(row.get("environmentId") == expected_environment_id,
           "`environmentId`が環境のロールの規定値と一致しません")
    _error(isinstance(row.get("requestedPython"), str) and row["requestedPython"],
           "要求したPython実行体が記録されていません")
    _error(isinstance(row.get("checkoutId"), str) and row["checkoutId"],
           "`checkoutId`がありません")
    _error(row.get("cleanBefore") is True and row.get("cleanAfter") is True,
           "新しいチェックアウトがクリーンではありません")
    _error(row.get("errors") == [], "実行の証跡にエラーがあります")

    environment = row.get("environment")
    _error(isinstance(environment, dict), "環境の証跡がありません")
    _error(environment.get("system") == "Linux", "Gate Cの検証環境はLinuxでなければなりません")
    _error(environment.get("implementation") == "CPython", "CPythonの証跡ではありません")
    _error(_python_minor(environment.get("python", "")) == PYTHON_MINOR,
           "CPython 3.12の証跡ではありません")
    _error(isinstance(environment.get("executable"), str) and environment["executable"],
           "Python実行体のパスがありません")
    _error(isinstance(environment.get("machine"), str) and environment["machine"],
           "`machine`の環境の証跡がありません")
    _error(isinstance(environment.get("git"), str) and environment["git"],
           "Gitの環境の証跡がありません")
    fingerprint = environment_fingerprint(environment)
    if role == "reference":
        _error(row.get("referenceManifestSha256") == manifest_digest(reference_manifest),
               "基準環境のマニフェストのハッシュ値が対象コミットと一致しません")
        validate_reference_environment(environment, reference_manifest)

    conformance = row.get("conformance")
    _error(isinstance(conformance, dict), "適合試験の証跡がありません")
    _error(conformance.get("exitCode") == 0, "適合試験の終了コードが0ではありません")
    report = conformance.get("report")
    _error(isinstance(report, dict), "適合試験のレポートがありません")
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
           "適合試験の`stderrSha256`が不正です")

    unit = row.get("unit")
    _error(isinstance(unit, dict), "Core単体試験の証跡がありません")
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
            reference_manifest: dict, performance_evidence: dict,
            priority_closure_evidence: dict) -> dict:
    _error(isinstance(reference_manifest, dict), "基準環境のマニフェストがありません")
    _error(re.fullmatch(r"[0-9a-f]{40}", commit) is not None, "対象コミットが40桁SHAではありません")
    _error(len(rows) == len(ROLES), "下限環境と基準環境の2件の証跡が必要です")
    validated = [validate_evidence(row, commit=commit, fixture_ids=fixture_ids,
                                   reference_manifest=reference_manifest) for row in rows]
    by_role = {entry["role"]: entry for entry in validated}
    _error(set(by_role) == set(ROLES) and len(by_role) == len(validated),
           "下限環境と基準環境が1件ずつ必要です")
    _error(len({entry["environmentId"] for entry in validated}) == len(ROLES),
           "環境のロールごとに異なる`environmentId`が必要です")
    _error(len({entry["checkoutId"] for entry in validated}) == len(ROLES),
           "環境のロールごとに独立した新しいチェックアウトが必要です")
    _error(len({entry["environmentFingerprint"] for entry in validated}) == len(ROLES),
           "下限環境と基準環境が同じ環境フィンガープリントです")
    _error(len({entry["conformanceSha256"] for entry in validated}) == 1,
           "下限環境と基準環境の適合結果が一致しません")
    _error(len({entry["unitTests"] for entry in validated}) == 1,
           "下限環境と基準環境のCore単体試験件数が一致しません")

    performance = validate_performance_evidence(
        performance_evidence, commit=commit, reference_manifest=reference_manifest)
    priority_closure = validate_priority_closure_evidence(
        priority_closure_evidence, commit=commit, fixture_ids=fixture_ids)

    environments = {role: by_role[role] for role in ROLES}
    return {
        "schemaVersion": 1,
        "commit": commit,
        "gateC": "Passed",
        "gateCFoundation": "Passed",
        "gateCPerformance": "Passed",
        "gateCPriorityClosure": "Passed",
        "fixtureCount": len(fixture_ids),
        "conformanceSha256": validated[0]["conformanceSha256"],
        "referenceManifestSha256": manifest_digest(reference_manifest),
        "environments": environments,
        "performance": performance,
        "priorityClosure": priority_closure,
        "covered": [
            "all conformance fixtures on CPython 3.12 minimum and reference roles",
            "Core unit tests on Linux in both roles",
            "cross-environment conformance determinism",
            "reference environment manifest and observed comparison key",
            "read-only/report/cache/timeout/signal/child-process acceptance in the full matrix",
            "accepted performance baseline and fixed SLO audit",
            "proposal 25 P0/P1 findings with per-finding acceptance evidence",
        ],
        "pending": [],
        "errors": [],
    }
