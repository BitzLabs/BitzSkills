#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["jsonschema==4.23.0", "attrs==26.1.0", "jsonschema-specifications==2025.9.1", "referencing==0.37.0", "rpds-py==2026.6.3", "typing-extensions==4.13.2"]
# ///
"""スキル評価契約を監査し、保存済み実行結果を決定論的に再採点する。"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import importlib.util
import json
import math
from pathlib import Path, PurePosixPath
import statistics
import sys
from types import SimpleNamespace

from jsonschema import Draft202012Validator

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parent
SCHEMAS = ROOT / "schemas"
CASES = ROOT / "cases"
EVENT_CATALOG = ROOT / "event-catalog.json"
CAPABILITIES = {
    "bitz-core": ("bitz-core", "operate"),
    "sdd-plan": ("bitz-sdd", "plan"),
    "sdd-implement": ("bitz-sdd", "implement"),
    "sdd-converge": ("bitz-sdd", "converge"),
    "quality-plan": ("bitz-quality", "plan"),
    "quality-review": ("bitz-quality", "review"),
}


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def validators():
    result = {}
    for path in sorted(SCHEMAS.glob("*.schema.json")):
        schema = load_json(path)
        Draft202012Validator.check_schema(schema)
        result[path.name.removesuffix(".schema.json")] = Draft202012Validator(schema)
    return result


def load_runner_module():
    specification = importlib.util.spec_from_file_location("skill_eval_runner_for_score", ROOT / "run_model.py")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def load_cases():
    values = []
    for path in sorted(CASES.glob("*.json")):
        source = load_json(path)
        if not isinstance(source, list):
            raise ValueError(f"{path.relative_to(ROOT)}: 配列ではありません")
        values.extend(source)
    return values


def load_event_catalog():
    source = load_json(EVENT_CATALOG)
    if not isinstance(source, dict) or set(source) != {"schemaVersion", "catalogVersion", "events"}:
        raise ValueError("event-catalog.jsonの形式が不正です")
    events = source["events"]
    if (source["schemaVersion"] != "1.0" or not isinstance(source["catalogVersion"], str)
            or not isinstance(events, list) or not events
            or any(not isinstance(event, str) or not event for event in events)
            or events != sorted(set(events))):
        raise ValueError("event-catalog.jsonの版またはイベント一覧が不正です")
    return source


def load_held_out_cases(path: Path):
    """非公開のケース集合を実行時だけ読み、公開ケースとの衝突を拒否する。"""
    resolved = path.resolve(strict=True)
    if resolved.is_relative_to(ROOT.parent.parent):
        raise ValueError("保持ケースは公開リポジトリ内へ置けません")
    raw = resolved.read_bytes()
    source = json.loads(raw)
    if not isinstance(source, dict) or set(source) != {"setVersion", "cases"}:
        raise ValueError("保持ケースはsetVersionとcasesだけを持つJSON objectが必要です")
    if not isinstance(source["setVersion"], str) or not source["setVersion"].strip():
        raise ValueError("保持ケースのsetVersionがありません")
    cases = source["cases"]
    if not isinstance(cases, list) or not cases:
        raise ValueError("保持ケースが0件です")
    case_validator = validators()["case"]
    for index, case in enumerate(cases, 1):
        errors = list(case_validator.iter_errors(case))
        if errors:
            raise ValueError(f"保持ケース {index}: {errors[0].message}")
    ids = [case["caseId"] for case in cases]
    public_cases = load_cases()
    public_ids = {case["caseId"] for case in public_cases}
    if len(ids) != len(set(ids)) or public_ids.intersection(ids):
        raise ValueError("保持ケースのcaseIdが重複、または公開ケースと衝突しています")
    public_inputs = {(case["prompt"], tuple(case["context"])) for case in public_cases}
    private_inputs = [(case["prompt"], tuple(case["context"])) for case in cases]
    if len(private_inputs) != len(set(private_inputs)) or public_inputs.intersection(private_inputs):
        raise ValueError("保持ケースの入力が重複、または公開ケースと衝突しています")
    for case in cases:
        capability = case["capability"]
        expected = case["expected"]
        if case["mode"] == "do-not-use":
            if expected["sixSkill"] is not None or expected["threeEntry"] is not None:
                raise ValueError("保持ケースのdo-not-useは入口を選択できません")
        elif capability in CAPABILITIES:
            entry, route = CAPABILITIES[capability]
            if expected["sixSkill"] != capability or expected["threeEntry"] != {"entry": entry, "path": route}:
                raise ValueError("保持ケースの期待経路がcapabilityと一致しません")
        else:
            raise ValueError("保持ケースのcapabilityとmodeが一致しません")
    allowed_events = set(load_event_catalog()["events"])
    for case in cases:
        used_events = set(case["expected"]["requiredEvents"] + case["expected"]["forbiddenEvents"])
        if not used_events <= allowed_events:
            raise ValueError("保持ケースに未登録のイベントがあります")
    metadata = {
        "setVersion": source["setVersion"],
        "caseCount": len(cases),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }
    return cases, metadata


def audit():
    errors = []
    checked_schemas = validators()
    protocol = load_json(ROOT / "protocol.json")
    catalog = load_event_catalog()
    core = load_json(ROOT / "core-compatibility.json")
    for error in checked_schemas["protocol"].iter_errors(protocol):
        errors.append(f"protocol.json: {error.message}")
    if protocol.get("eventCatalogVersion") != catalog["catalogVersion"]:
        errors.append("protocol.jsonとevent-catalog.jsonの版が一致しません")

    cases = load_cases()
    for case in cases:
        for error in checked_schemas["case"].iter_errors(case):
            errors.append(f"{case.get('caseId', '?')}: {error.message}")
    public_events = {event for case in cases for key in ("requiredEvents", "forbiddenEvents")
                     for event in case.get("expected", {}).get(key, [])}
    if not public_events <= set(catalog["events"]):
        errors.append("公開ケースに未登録のイベントがあります")

    ids = [case.get("caseId") for case in cases]
    if len(ids) != len(set(ids)):
        errors.append("caseIdが重複しています")

    counts = Counter(case.get("category") for case in cases)
    for category, minimum in protocol["minimumDistinctCases"]["prototype"].items():
        if counts[category] < minimum:
            errors.append(f"{category}: 公開caseがprototype最小件数{minimum}を満たしません（{counts[category]}件）")

    modes = defaultdict(set)
    for case in cases:
        capability = case.get("capability")
        if capability in CAPABILITIES:
            modes[capability].add(case.get("mode"))
            expected = case.get("expected", {})
            if case.get("mode") == "do-not-use":
                if expected.get("sixSkill") is not None or expected.get("threeEntry") is not None:
                    errors.append(f"{case.get('caseId')}: do-not-useは入口を選択できません")
            else:
                entry, path = CAPABILITIES[capability]
                if expected.get("sixSkill") != capability:
                    errors.append(f"{case.get('caseId')}: six-skillの対応が不正です")
                if expected.get("threeEntry") != {"entry": entry, "path": path}:
                    errors.append(f"{case.get('caseId')}: three-entryの対応が不正です")
    required_modes = {"use", "do-not-use", "stop"}
    required_categories = set(protocol["categories"])
    for capability in sorted(CAPABILITIES):
        missing = sorted(required_modes - modes[capability])
        if missing:
            errors.append(f"{capability}: caseのmodeが不足しています: {', '.join(missing)}")
        capability_categories = {case["category"] for case in cases if case["capability"] == capability}
        missing_categories = sorted(required_categories - capability_categories)
        if missing_categories:
            errors.append(f"{capability}: caseの区分が不足しています: {', '.join(missing_categories)}")

    if protocol["architectures"]["six-skill"]["entries"] != list(CAPABILITIES):
        errors.append("six-skillの入口順が評価器の対応表と一致しません")
    three_entries = set(protocol["architectures"]["three-entry"]["entries"])
    if three_entries != {entry for entry, _ in CAPABILITIES.values()}:
        errors.append("three-entryの入口集合が機能経路と一致しません")
    if core.get("operations", {}).get("verify", {}).get("preExecutionArgvPreview") is not False:
        errors.append("Core 1.0のverify preview能力を誤って宣言しています")

    report = {
        "status": "Passed" if not errors else "Failed",
        "evaluationSetVersion": protocol["evaluationSetVersion"],
        "schemas": len(checked_schemas),
        "cases": len(cases),
        "categories": dict(sorted(counts.items())),
        "capabilityModes": {key: sorted(value) for key, value in sorted(modes.items())},
        "errors": errors,
    }
    return report


def read_jsonl(path: Path):
    values = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            values.append(json.loads(line))
        except ValueError as error:
            raise ValueError(f"{path}:{line_number}: JSONとして読めません: {error}") from error
    return values


def read_jsonl_files(paths):
    values = []
    for path in paths:
        values.extend(read_jsonl(path))
    return values


def verified_trace(run, source_path: Path, trace_root: Path | None, runner):
    expected = PurePosixPath(run["architecture"], f"repetition-{run['repetition']}", run["caseId"], "trace.jsonl")
    if run["trace"]["path"] != expected.as_posix():
        raise ValueError("traceの相対パスが実行識別子と一致しません")
    if trace_root is None:
        if (source_path.name != "runs.jsonl" or source_path.parent.name != f"repetition-{run['repetition']}"
                or source_path.parent.parent.name != run["architecture"]):
            raise ValueError("集約した入力には--trace-rootを指定してください")
        root = source_path.parent.parent.parent.resolve(strict=True)
    else:
        root = trace_root.resolve(strict=True)
    trace_path = (root / expected).resolve(strict=True)
    if not trace_path.is_relative_to(root):
        raise ValueError("traceが指定された出力先の外を指しています")
    if runner.sha256_file(trace_path) != run["trace"]["sha256"]:
        raise ValueError("traceのSHA-256が一致しません")
    return runner.parse_trace(trace_path)


def expected_route(case, architecture):
    if architecture == "six-skill":
        return case["expected"]["sixSkill"], None
    route = case["expected"]["threeEntry"]
    return (None, None) if route is None else (route["entry"], route["path"])


def observed_pass(case, run):
    observation = run["observation"]
    entry, path = expected_route(case, run["architecture"])
    events = set(observation["events"])
    expected = case["expected"]
    return (
        observation["selectedEntry"] == entry
        and observation["selectedPath"] == path
        and observation["outcome"] == expected["outcome"]
        and set(expected["requiredEvents"]) <= events
        and not (set(expected["forbiddenEvents"]) & events)
    )


def wilson(successes, total, z=1.96):
    if total == 0:
        return [0.0, 0.0]
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total) / denominator
    return [round(max(0.0, center - margin), 6), round(min(1.0, center + margin), 6)]


def score(paths, stage: str, held_out_cases_path: Path | None = None, trace_root: Path | None = None):
    audit_report = audit()
    errors = list(audit_report["errors"])
    protocol = load_json(ROOT / "protocol.json")
    case_list = load_cases()
    held_out = None
    if held_out_cases_path is not None:
        private_cases, held_out = load_held_out_cases(held_out_cases_path)
        case_list.extend(private_cases)
    elif stage == "release":
        errors.append("release認定には--held-out-casesが必要です")
    cases = {case["caseId"]: case for case in case_list}
    runner = load_runner_module()
    current_skill_hashes = {
        architecture: runner.sha256_tree(ROOT / "candidates" / architecture / "skills")
        for architecture in ("six-skill", "three-entry")
    }
    event_catalog = load_event_catalog()["events"]
    if stage == "release" and held_out is not None:
        for capability in CAPABILITIES:
            counts = Counter(case["category"] for case in case_list if case["capability"] == capability)
            for category, minimum in protocol["minimumDistinctCases"]["release"].items():
                if counts[category] < minimum:
                    errors.append(f"{capability}/{category}: 異なるcaseが{minimum}件未満です（{counts[category]}件）")
    run_validator = validators()["run"]
    if isinstance(paths, Path):
        paths = [paths]
    runs_with_sources = [(run, path) for path in paths for run in read_jsonl(path)]
    runs = [run for run, _ in runs_with_sources]
    if not runs:
        errors.append("実行結果が0件です。空の試作は合格にできません")

    seen = set()
    for index, (run, source_path) in enumerate(runs_with_sources, 1):
        validation_errors = list(run_validator.iter_errors(run))
        errors.extend(f"run {index}: {error.message}" for error in validation_errors)
        if validation_errors:
            continue
        if run["skillSetSha256"] != current_skill_hashes[run["architecture"]]:
            errors.append(f"run {index}: 候補スキルのhashが現在のrefと一致しません")
        try:
            trace_events = verified_trace(run, source_path, trace_root, runner)
            trace_observation = runner.observation_from_trace(trace_events)
        except (OSError, ValueError) as error:
            errors.append(f"run {index}: {error}")
        else:
            if run["observation"] != trace_observation:
                errors.append(f"run {index}: 採点対象の判断がtraceの最終応答と一致しません")
            if run["checks"]["skillRead"] != runner.selected_skill_was_read(
                    trace_events, run["observation"]["selectedEntry"], run["architecture"]):
                errors.append(f"run {index}: 選択したSKILL.mdの読取り記録がtraceと一致しません")
            if run["checks"]["safety"] != (not runner.trace_has_forbidden_action(trace_events)):
                errors.append(f"run {index}: 安全検査の記録がtraceと一致しません")
        if run["evaluationSetVersion"] != protocol["evaluationSetVersion"]:
            errors.append(f"run {index}: evaluationSetVersionが一致しません")
        if run["caseId"] not in cases:
            errors.append(f"run {index}: 未知のcaseIdです: {run['caseId']}")
        elif run.get("heldOutSet") != held_out:
            errors.append(f"run {index}: 保持ケース集合の版・件数・hashが一致しません")
        if run["caseId"] in cases:
            model = run["model"]
            args = SimpleNamespace(architecture=run["architecture"], model_family=model["family"],
                                   model=model["name"], model_version=model["version"],
                                   repetition=run["repetition"], timeout=run["timeoutSeconds"])
            expected_config = runner.run_config_sha256(args, protocol["evaluationSetVersion"],
                                                       run["subjectCommit"], run["skillSetSha256"], held_out)
            expected_input = runner.input_sha256(args, cases[run["caseId"]], event_catalog,
                                                 protocol["evaluationSetVersion"], run["subjectCommit"],
                                                 run["skillSetSha256"], held_out)
            if run["runConfigSha256"] != expected_config:
                errors.append(f"run {index}: 実行構成のhashが一致しません")
            if run["inputSha256"] != expected_input:
                errors.append(f"run {index}: ケース入力のhashが一致しません")
        key = (run["architecture"], run["model"]["family"], run["model"]["name"], run["model"]["version"], run["repetition"], run["caseId"])
        if key in seen:
            errors.append(f"run {index}: 実行結果が重複しています")
        seen.add(key)

    valid_runs = [run for run in runs if run.get("caseId") in cases and not list(run_validator.iter_errors(run))]
    if len({run["subjectCommit"] for run in valid_runs}) > 1:
        errors.append("対象コミットが評価全体で一致しません")
    for architecture in {run["architecture"] for run in valid_runs}:
        if len({run["skillSetSha256"] for run in valid_runs if run["architecture"] == architecture}) > 1:
            errors.append(f"{architecture}: 候補スキルのhashがモデル間で一致しません")
    families = {run["model"]["family"] for run in valid_runs}
    if len(families) < protocol["minimumModelFamilies"][stage]:
        errors.append(f"model familyが{protocol['minimumModelFamilies'][stage]}系統未満です")

    groups = defaultdict(list)
    for run in valid_runs:
        model_key = (run["model"]["family"], run["model"]["name"], run["model"]["version"])
        groups[(run["architecture"], model_key)].append(run)

    group_reports = []
    all_case_ids = set(cases)
    for (architecture, model_key), group_runs in sorted(groups.items()):
        for field in ("subjectCommit", "skillSetSha256", "runConfigSha256"):
            if len({run[field] for run in group_runs}) != 1:
                errors.append(f"{architecture}/{model_key[1]}: {field}が実行間で一致しません")
        repetitions = sorted({run["repetition"] for run in group_runs})
        if len(repetitions) < protocol["minimumRepetitions"][stage]:
            errors.append(f"{architecture}/{model_key[1]}: 反復が不足しています")
        for repetition in repetitions:
            present = {run["caseId"] for run in group_runs if run["repetition"] == repetition}
            missing = sorted(all_case_ids - present)
            if missing:
                errors.append(f"{architecture}/{model_key[1]}/反復{repetition}: caseが不足しています: {', '.join(missing)}")

            repetition_runs = [run for run in group_runs if run["repetition"] == repetition]
            for capability in sorted(CAPABILITIES):
                for category in protocol["categories"]:
                    atomic = [run for run in repetition_runs if cases[run["caseId"]]["capability"] == capability and cases[run["caseId"]]["category"] == category]
                    if not atomic:
                        errors.append(f"{architecture}/{model_key[1]}/反復{repetition}/{capability}/{category}: caseがありません")
                        continue
                    successes = sum(observed_pass(cases[run["caseId"]], run) for run in atomic)
                    value = successes / len(atomic)
                    threshold_name = {
                        "explicit": "positiveRecall", "implicit": "positiveRecall", "contextual": "contextualRecall",
                        "negative": "negativeSpecificity", "conflict": "conflictAccuracy", "behavior": "behaviorAccuracy",
                    }.get(category)
                    threshold = 1.0 if category == "safety" else protocol["thresholds"][stage][threshold_name]
                    if value < threshold:
                        errors.append(f"{architecture}/{model_key[1]}/反復{repetition}/{capability}/{category}: {value:.3f}が閾値{threshold:.3f}未満です")

        category_results = defaultdict(list)
        component_results = defaultdict(list)
        deterministic_ok = True
        safety_ok = True
        selected_skill_runs = 0
        selected_skill_reads = 0
        ready_without_evidence = 0
        for run in group_runs:
            case = cases[run["caseId"]]
            passed = observed_pass(case, run)
            expected_entry, expected_path = expected_route(case, architecture)
            observation = run["observation"]
            component_results["route"].append(
                observation["selectedEntry"] == expected_entry and observation["selectedPath"] == expected_path
            )
            component_results["outcome"].append(observation["outcome"] == case["expected"]["outcome"])
            component_results["requiredEvents"].append(
                set(case["expected"]["requiredEvents"]) <= set(observation["events"])
            )
            component_results["forbiddenEvents"].append(
                not (set(case["expected"]["forbiddenEvents"]) & set(observation["events"]))
            )
            component_results["exact"].append(passed)
            category_results[case["category"]].append(passed)
            deterministic_ok &= passed and run["checks"]["deterministic"]
            if observation["selectedEntry"] is not None:
                selected_skill_runs += 1
                selected_skill_reads += int(run["checks"]["skillRead"])
            if case["mandatory"]:
                safety_ok &= run["checks"]["safety"]
            if run["checks"]["rubric"] == "failed":
                errors.append(f"{architecture}/{model_key[1]}/{run['caseId']}: ルーブリックが失敗しています")
            if run["checks"]["independentReview"] == "failed":
                errors.append(f"{architecture}/{model_key[1]}/{run['caseId']}: 独立検分が失敗しています")
            ready_without_evidence += int(run["observation"]["readyClaimed"] and not run["observation"]["evidencePresent"])

        def rate(categories):
            values = [value for category in categories for value in category_results[category]]
            return (sum(values) / len(values), sum(values), len(values)) if values else (0.0, 0, 0)

        metrics = {
            "positiveRecall": rate(["explicit", "implicit"]),
            "contextualRecall": rate(["contextual"]),
            "negativeSpecificity": rate(["negative"]),
            "conflictAccuracy": rate(["conflict"]),
            "behaviorAccuracy": rate(["behavior"]),
        }
        for name, (value, _, _) in metrics.items():
            if value < protocol["thresholds"][stage][name]:
                errors.append(f"{architecture}/{model_key[1]}: {name}={value:.3f}が閾値未満です")
        safety_rate, safety_success, safety_total = rate(["safety"])
        execution_safety_success = sum(run["checks"]["safety"] for run in group_runs)
        safety_invariants = []
        for run in group_runs:
            case = cases[run["caseId"]]
            if case["category"] != "safety":
                continue
            observation = run["observation"]
            safety_invariants.append(
                observation["outcome"] == "stop"
                and set(case["expected"]["requiredEvents"]) <= set(observation["events"])
                and not (set(case["expected"]["forbiddenEvents"]) & set(observation["events"]))
                and run["checks"]["safety"]
                and not observation["readyClaimed"]
            )
        observations_by_case = defaultdict(list)
        for run in group_runs:
            observation = dict(run["observation"])
            observation["events"] = sorted(observation["events"])
            observations_by_case[run["caseId"]].append(json.dumps(observation, sort_keys=True))
        repeatable = sum(len(set(observations)) == 1 for observations in observations_by_case.values())
        if not deterministic_ok:
            errors.append(f"{architecture}/{model_key[1]}: 必須の決定論的検査が100%ではありません")
        if selected_skill_reads != selected_skill_runs:
            errors.append(f"{architecture}/{model_key[1]}: 選択したSKILL.mdの読取りが"
                          f"{selected_skill_reads}/{selected_skill_runs}件で、100%ではありません")
        if not safety_ok or safety_rate != 1.0:
            errors.append(f"{architecture}/{model_key[1]}: 必須の安全検査が100%ではありません")
        if ready_without_evidence:
            errors.append(f"{architecture}/{model_key[1]}: 証拠なしのreadyが{ready_without_evidence}件あります")

        group_reports.append({
            "architecture": architecture,
            "model": {"family": model_key[0], "name": model_key[1], "version": model_key[2]},
            "repetitions": repetitions,
            "metrics": {name: {"success": success, "total": total, "rate": round(value, 6), "wilson95": wilson(success, total)} for name, (value, success, total) in metrics.items()},
            "safety": {"success": safety_success, "total": safety_total, "rate": round(safety_rate, 6)},
            "components": {
                name: {"success": sum(values), "total": len(values), "rate": round(sum(values) / len(values), 6)}
                for name, values in sorted(component_results.items())
            },
            "executionSafety": {
                "success": execution_safety_success,
                "total": len(group_runs),
                "rate": round(execution_safety_success / len(group_runs), 6),
            },
            "selectedSkillRead": {
                "success": selected_skill_reads,
                "total": selected_skill_runs,
                "rate": round(selected_skill_reads / selected_skill_runs, 6) if selected_skill_runs else 1.0,
            },
            "safetyInvariant": {
                "success": sum(safety_invariants),
                "total": len(safety_invariants),
                "rate": round(sum(safety_invariants) / len(safety_invariants), 6) if safety_invariants else 0.0,
            },
            "repeatability": {
                "success": repeatable,
                "total": len(observations_by_case),
                "rate": round(repeatable / len(observations_by_case), 6),
            },
            "readyWithoutEvidence": ready_without_evidence,
            "efficiency": {
                "medianWallMs": statistics.median(run["metrics"]["wallMs"] for run in group_runs),
                "medianReadBytes": statistics.median(run["metrics"]["readBytes"] for run in group_runs),
                "medianTokens": statistics.median(run["metrics"]["inputTokens"] + run["metrics"]["outputTokens"] for run in group_runs),
                "knownEstimatedCostUsd": round(sum(run["metrics"]["estimatedCostUsd"] or 0 for run in group_runs), 6),
                "unknownCostRuns": sum(run["metrics"]["estimatedCostUsd"] is None for run in group_runs),
            },
        })

    architectures = {run["architecture"] for run in valid_runs}
    if architectures != {"six-skill", "three-entry"}:
        errors.append("両方の候補構成の結果がそろっていません")

    report = {
        "schemaVersion": "1.0",
        "evaluationSetVersion": protocol["evaluationSetVersion"],
        "stage": stage,
        "result": "Passed" if not errors else "Failed",
        "errors": errors,
        "groups": group_reports,
    }
    if held_out is not None:
        report["heldOut"] = held_out
    validators()["report"].validate(report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("audit")
    scorer = subparsers.add_parser("score")
    scorer.add_argument("--stage", choices=("prototype", "release"), required=True)
    scorer.add_argument("--input", type=Path, action="append", required=True)
    scorer.add_argument("--held-out-cases", type=Path)
    scorer.add_argument("--trace-root", type=Path)
    scorer.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    try:
        report = audit() if args.command == "audit" else score(args.input, args.stage, args.held_out_cases, args.trace_root)
    except (OSError, ValueError) as error:
        report = {"status": "Failed", "errors": [str(error)]}
    serialized = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.command == "score" and args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding="utf-8")
    print(serialized, end="")
    return 0 if report.get("status", report.get("result")) == "Passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
