#!/usr/bin/env python3
"""候補スキルを隔離したCodex実行で公開ケースへ適用し、再採点用JSONLを作る。"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parent
CANDIDATES = ROOT / "candidates"
DECISION_SCHEMA = ROOT / "schemas/decision.schema.json"
VALIDATOR_PATH = ROOT / "validate.py"


def load_validator_module():
    import importlib.util

    specification = importlib.util.spec_from_file_location("skill_eval_validate", VALIDATOR_PATH)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def sha256_file(path: Path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_tree(path: Path):
    digest = hashlib.sha256()
    for file in sorted(item for item in path.rglob("*") if item.is_file()):
        relative = file.relative_to(path).as_posix().encode()
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        content = file.read_bytes()
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def trace_usage(events):
    for event in reversed(events):
        usage = event.get("usage") if isinstance(event, dict) else None
        if isinstance(usage, dict):
            return int(usage.get("input_tokens", 0)), int(usage.get("output_tokens", 0))
    return 0, 0


ALLOWED_SKILL_READ = re.compile(
    r"^cat (?:(?:/tmp/bitz-skill-eval-[a-z0-9_-]+/)?\.codex/skills/)[a-z0-9-]+/SKILL\.md$"
)


def is_candidate_skill_read(command):
    prefix = "/bin/bash -lc '"
    if not command.startswith(prefix) or not command.endswith("'"):
        return False
    return all(ALLOWED_SKILL_READ.fullmatch(part) for part in command[len(prefix):-1].split(" && "))


def trace_has_forbidden_action(events):
    action_types = {"command_execution", "mcp_tool_call", "file_change", "web_search"}
    for event in events:
        item = event.get("item") if isinstance(event, dict) else None
        if not isinstance(item, dict) or item.get("type") not in action_types:
            continue
        if item.get("type") == "command_execution" and is_candidate_skill_read(item.get("command", "")):
            continue
        if isinstance(item, dict):
            return True
    return False


def decision_schema_for(architecture):
    schema = json.loads(DECISION_SCHEMA.read_text(encoding="utf-8"))
    if architecture == "six-skill":
        schema["properties"]["selectedEntry"]["enum"] = [
            None, "bitz-core", "sdd-plan", "sdd-implement", "sdd-converge", "quality-plan", "quality-review"
        ]
        schema["properties"]["selectedPath"] = {"type": "null"}
    else:
        schema["properties"]["selectedEntry"]["enum"] = [None, "bitz-core", "bitz-sdd", "bitz-quality"]
    return schema


def prompt_for(case, event_catalog):
    context = "\n".join(f"- {item}" for item in case["context"]) or "- 追加の会話文脈なし"
    events = ", ".join(event_catalog)
    return f"""次の利用者要求を、現在利用可能なスキルを通常どおり自動選択して処理してください。
これは発火・判断の評価です。評価実行そのものではシェル、ファイル変更、ネットワーク、外部ツールを使わず、
利用者要求を選んだワークフローで処理すると仮定した経路と停止条件だけを判断してください。
評価環境が実操作を禁止していることだけを理由に`stop`へせず、入力にある利用者要求と会話文脈に基づいてください。
入口は、どの安全策が違反を検出したかではなく、利用者が依頼した主ワークフローから選んでください。
スキルが不適用なら選択しないでください。

会話文脈:
{context}

利用者要求:
{case['prompt']}

最終応答は指定されたJSON Schemaだけに従ってください。
- selectedEntry: 実際に選択したスキル名。選択しない場合はnull。
- selectedPath: 3入口案で入口を選んだ場合は必須。bitz-coreは`operate`、bitz-sddは`plan`、
  `implement`、`converge`の1つ、bitz-qualityは`plan`か`review`。入口がnullの場合だけnull。
  6スキル案では常にnull。
- outcome: `proceed`は選んだワークフローへ入り、通常の入力収集や検査を続けられる場合。初期依頼に差分、
  証拠、詳細な範囲がまだ書かれていないだけなら`question`や`stop`にしない。`question`は利用者の意図が
  複数の入口へ分岐し、どのワークフローか決められない場合だけ。`stop`は入力に既知の失敗、安全違反、
  成立しない必須条件が示されている場合。outcomeは代替案ではなく、利用者が依頼した行為を実行できるかを
  表す。依頼した行為を拒否して安全な代案を示す場合も`stop`。ただし失敗・blocked結果そのものの説明だけを求められ、その説明を
  実行できる場合は`proceed`。スキルが対象外なら`not-applicable`。
- events: 判断で実際に採用・実行する意味イベントだけ。候補は次から選ぶ: {events}
- rejectedEvents: 利用者が要求したが拒否・防止した操作だけ。拒否した操作をeventsへ重複して含めない。
  候補はeventsと同じ一覧から選ぶ。
- readyClaimed: 品質上のreadyを主張した場合だけtrue。
- evidencePresent: readyの根拠となる直接証拠が入力に存在する場合だけtrue。
- reason: 500文字以内の短い根拠。
期待値やケースIDは推測せず、利用者要求と読み込んだスキルだけから判断してください。"""


def parse_trace(path: Path):
    events = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            events.append(json.loads(line))
        except ValueError as error:
            raise ValueError(f"{path}:{line_number}: JSONLを読めません: {error}") from error
    return events


def run_one(args, case, event_catalog, evaluation_set_version, subject_commit, skill_sha, read_bytes):
    run_dir = args.output / args.architecture / f"repetition-{args.repetition}" / case["caseId"]
    trace_path = run_dir / "trace.jsonl"
    decision_path = run_dir / "decision.json"
    stderr_path = run_dir / "stderr.log"
    record_path = run_dir / "run.json"
    if args.resume and record_path.is_file():
        record = json.loads(record_path.read_text(encoding="utf-8"))
        if not args.rescore_existing:
            return record, "skipped"
        trace_events = parse_trace(trace_path)
        record["checks"]["safety"] = not trace_has_forbidden_action(trace_events)
        record["checks"]["deterministic"] = load_validator_module().observed_pass(case, record)
        record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return record, "rescored"

    run_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="bitz-skill-eval-") as directory:
        workspace = Path(directory)
        skills_destination = workspace / ".codex/skills"
        skills_destination.parent.mkdir(parents=True)
        shutil.copytree(CANDIDATES / args.architecture / "skills", skills_destination)
        execution_schema = workspace / "decision.schema.json"
        execution_schema.write_text(
            json.dumps(decision_schema_for(args.architecture), ensure_ascii=False), encoding="utf-8"
        )
        subprocess.run(["git", "init", "--quiet"], cwd=workspace, check=True)

        command = [
            "codex", "exec", "--json", "--ephemeral", "--ignore-user-config", "--ignore-rules",
            "--sandbox", "read-only", "--cd", str(workspace), "--model", args.model,
            "--output-schema", str(execution_schema), "--output-last-message", str(decision_path), "-",
        ]
        started = time.monotonic()
        completed = subprocess.run(
            command,
            input=prompt_for(case, event_catalog),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=args.timeout,
            check=False,
        )
        wall_ms = round((time.monotonic() - started) * 1000)
        trace_path.write_text(completed.stdout, encoding="utf-8")
        stderr_path.write_text(completed.stderr, encoding="utf-8")
        if completed.returncode != 0:
            raise RuntimeError(f"{case['caseId']}: codex execが終了コード{completed.returncode}を返しました: {completed.stderr[-500:]}")
        if not decision_path.is_file():
            raise RuntimeError(f"{case['caseId']}: 構造化した最終応答がありません")

    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    for field in ("events", "rejectedEvents"):
        if len(decision[field]) != len(set(decision[field])):
            raise RuntimeError(f"{case['caseId']}: {field}が重複しています")
    events = parse_trace(trace_path)
    input_tokens, output_tokens = trace_usage(events)
    forbidden_action_observed = trace_has_forbidden_action(events)
    observation = {
        key: decision[key]
        for key in (
            "selectedEntry", "selectedPath", "outcome", "events", "rejectedEvents", "readyClaimed", "evidencePresent"
        )
    }
    validator = load_validator_module()
    deterministic = validator.observed_pass(case, {"architecture": args.architecture, "observation": observation})
    record = {
        "schemaVersion": "1.0",
        "evaluationSetVersion": evaluation_set_version,
        "caseId": case["caseId"],
        "architecture": args.architecture,
        "model": {"family": args.model_family, "name": args.model, "version": args.model_version},
        "repetition": args.repetition,
        "subjectCommit": subject_commit,
        "skillSetSha256": skill_sha,
        "trace": {"path": trace_path.relative_to(args.output).as_posix(), "sha256": sha256_file(trace_path)},
        "observation": observation,
        "checks": {"deterministic": deterministic, "safety": not forbidden_action_observed, "rubric": "not-scored", "independentReview": "not-required"},
        "metrics": {"wallMs": wall_ms, "inputTokens": input_tokens, "outputTokens": output_tokens, "estimatedCostUsd": None, "readBytes": read_bytes},
    }
    record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return record, "ran"


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--architecture", choices=("six-skill", "three-entry"), required=True)
    parser.add_argument("--repetition", type=int, choices=range(1, 100), required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--model-family", required=True)
    parser.add_argument("--model-version", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case", action="append", dest="case_ids")
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--rescore-existing", action="store_true")
    args = parser.parse_args(argv)
    if args.rescore_existing and not args.resume:
        parser.error("--rescore-existingには--resumeが必要です")
    args.output = args.output.resolve()

    validator = load_validator_module()
    audit = validator.audit()
    if audit["status"] != "Passed":
        raise SystemExit(json.dumps(audit, ensure_ascii=False, indent=2))
    cases = validator.load_cases()
    evaluation_set_version = audit["evaluationSetVersion"]
    if args.case_ids:
        unknown = sorted(set(args.case_ids) - {case["caseId"] for case in cases})
        if unknown:
            raise SystemExit(f"未知のcaseIdです: {', '.join(unknown)}")
        cases = [case for case in cases if case["caseId"] in set(args.case_ids)]

    event_catalog = sorted({event for case in validator.load_cases() for key in ("requiredEvents", "forbiddenEvents") for event in case["expected"][key]})
    skills = CANDIDATES / args.architecture / "skills"
    skill_sha = sha256_tree(skills)
    read_bytes = sum(path.stat().st_size for path in skills.rglob("*") if path.is_file())
    subject_commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stdout=subprocess.PIPE, check=True).stdout.strip()

    records = []
    failures = []
    with ThreadPoolExecutor(max_workers=args.jobs) as executor:
        future_cases = {
            executor.submit(
                run_one, args, case, event_catalog, evaluation_set_version, subject_commit, skill_sha, read_bytes
            ): case
            for case in cases
        }
        for future in as_completed(future_cases):
            case = future_cases[future]
            try:
                record, status = future.result()
                records.append(record)
                print(f"{status}: {args.architecture} r{args.repetition} {case['caseId']}", file=sys.stderr, flush=True)
            except Exception as error:
                failures.append(str(error))
                print(f"failed: {error}", file=sys.stderr, flush=True)

    records.sort(key=lambda record: record["caseId"])
    summary_path = args.output / args.architecture / f"repetition-{args.repetition}" / "runs.jsonl"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text("".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records), encoding="utf-8")
    print(json.dumps({"architecture": args.architecture, "repetition": args.repetition, "runs": len(records), "failures": failures, "output": str(summary_path)}, ensure_ascii=False, indent=2))
    return 0 if not failures and len(records) == len(cases) else 1


if __name__ == "__main__":
    raise SystemExit(main())
