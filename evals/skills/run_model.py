#!/usr/bin/env python3
"""候補スキルを隔離したCodex実行でケースへ適用し、再採点用JSONLを作る。"""

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


ALLOWED_SKILL_PATH = re.compile(r"^\.codex/skills/([a-z0-9-]+)/SKILL\.md$")


def candidate_skill_names_read(command):
    prefix = "/bin/bash -lc '"
    if not isinstance(command, str) or not command.startswith(prefix) or not command.endswith("'"):
        return []
    names = []
    for part in re.split(r"[ \t]*&&[ \t]*", command[len(prefix):-1]):
        words = re.split(r"[ \t]+", part.strip(" \t"))
        if words[0] != "cat" or len(words) < 2:
            return []
        matches = [ALLOWED_SKILL_PATH.fullmatch(word) for word in words[1:]]
        if not all(matches):
            return []
        names.extend(match.group(1) for match in matches)
    return names


def is_candidate_skill_read(command):
    return bool(candidate_skill_names_read(command))


def selected_skill_was_read(events, selected_entry, architecture):
    if selected_entry is None:
        return True
    for event in events:
        item = event.get("item")
        if event.get("type") != "item.completed" or not isinstance(item, dict):
            continue
        if item.get("type") != "command_execution" or item.get("exit_code") != 0:
            continue
        names = candidate_skill_names_read(item.get("command", ""))
        if selected_entry not in names:
            continue
        paths = [CANDIDATES / architecture / "skills" / name / "SKILL.md" for name in names]
        if not all(path.is_file() for path in paths):
            continue
        contents = [path.read_text(encoding="utf-8") for path in paths]
        selected_content = contents[names.index(selected_entry)]
        lines = selected_content.splitlines()
        if lines and lines[0].strip() == "---":
            closing = next((index for index, line in enumerate(lines[1:], 1) if line.strip() == "---"), None)
            body = "\n".join(lines[closing + 1:]) if closing is not None else ""
        else:
            body = selected_content
        if not body.strip():
            continue
        expected = "".join(contents)
        if item.get("aggregated_output") == expected:
            return True
    return False


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


def decision_schema_for(architecture, *, for_execution=False):
    schema = json.loads(DECISION_SCHEMA.read_text(encoding="utf-8"))
    catalog = json.loads((ROOT / "event-catalog.json").read_text(encoding="utf-8"))["events"]
    for field in ("events", "rejectedEvents"):
        schema["properties"][field]["items"]["enum"] = catalog
        if for_execution:
            schema["properties"][field].pop("uniqueItems", None)
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
これは発火・判断の評価です。入口を仮選択したら、最終判断の前に該当する候補の
`.codex/skills/<スキル名>/SKILL.md`をその相対パスのまま`cat`で読み、内容を判断へ適用してください。
候補を比較するために別の候補の`SKILL.md`を読むこともできます。この読取りだけがシェル利用の例外です。
それ以外のシェル、ファイル変更、ネットワーク、外部ツールは使わず、利用者要求を選んだ
ワークフローで処理すると仮定した経路と停止条件だけを判断してください。
スキルを選ばない場合は`SKILL.md`の読取りは不要です。
作業ディレクトリや安全性の確認を目的とする`pwd`、`ls`、`git status`等も、許可した本文読取りには含まれません。
評価環境が実操作を禁止していることだけを理由に`stop`へせず、入力にある利用者要求と会話文脈に基づいてください。
入口は、どの安全策が違反を検出したかではなく、利用者が依頼した主ワークフローから選んでください。
スキルが不適用なら選択しないでください。

会話文脈:
{context}

利用者要求:
{case['prompt']}

最終応答は指定されたJSON Schemaだけに従ってください。
- selectedEntry: 実際に選択したスキル名。選択しない場合はnull。
  候補本文の読取りや仮選択だけを最終選択として残さない。不適用と判定した場合はselectedEntryとselectedPathをnullにする。
- selectedPath: 3入口案で入口を選んだ場合は必須。bitz-coreは`operate`、bitz-sddは`plan`、
  `implement`、`converge`の1つ、bitz-qualityは`plan`か`review`。入口がnullの場合だけnull。
  6スキル案では常にnull。
- outcome: `proceed`は選んだワークフローへ入り、通常の入力収集や検査を続けられる場合。初期依頼に差分、
  証拠、詳細な範囲がまだ書かれていないだけなら`question`や`stop`にしない。`question`は利用者の意図が
  複数の入口へ分岐し、どのワークフローか決められない場合だけ。`stop`は入力に既知の失敗、安全違反、
  成立しない必須条件が示されている場合。outcomeは代替案ではなく、利用者が依頼した行為を実行できるかを
  表す。依頼した行為を拒否して安全な代案を示す場合も`stop`。ただし失敗・blocked結果そのものの説明だけを求められ、その説明を
  実行できる場合は`proceed`。スキルが対象外なら`not-applicable`。
- events: 選んだワークフローで着手すると決めた意味ステップだけ。実操作は禁止されているため、
  ここでの採用は実際にCoreやファイルを操作したという主張ではありません。通常の入力収集後に行うと
  決めた分類・確認も含めますが、単に可能性として挙げた操作や拒否した操作は含めません。
  候補は次から選ぶ: {events}
- rejectedEvents: 利用者が要求したが拒否・防止した操作だけ。拒否した操作をeventsへ重複して含めない。
  候補はeventsと同じ一覧から選ぶ。
- readyClaimed: 品質上のreadyを主張した場合だけtrue。
  eventsの`claim-ready`と一致させ、拒否した操作をeventsにも含めない。
- evidencePresent: readyの根拠となる直接証拠が入力に存在する場合だけtrue。
- reason: 500文字以内の短い根拠。
期待値やケースIDは推測せず、利用者要求と読み込んだスキルだけから判断してください。"""


def execution_identity(args, case, evaluation_set_version, subject_commit, skill_sha, held_out_set):
    return {
        "evaluationSetVersion": evaluation_set_version,
        "caseId": case["caseId"],
        "architecture": args.architecture,
        "model": {"family": args.model_family, "name": args.model, "version": args.model_version},
        "repetition": args.repetition,
        "timeoutSeconds": args.timeout,
        "subjectCommit": subject_commit,
        "skillSetSha256": skill_sha,
        "heldOutSet": held_out_set,
    }


def hash_json(value):
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def run_config_sha256(args, evaluation_set_version, subject_commit, skill_sha, held_out_set):
    return hash_json({
        "evaluationSetVersion": evaluation_set_version,
        "architecture": args.architecture,
        "model": {"family": args.model_family, "name": args.model, "version": args.model_version},
        "subjectCommit": subject_commit,
        "skillSetSha256": skill_sha,
        "heldOutSet": held_out_set,
        "decisionSchema": decision_schema_for(args.architecture),
        "executionSchema": decision_schema_for(args.architecture, for_execution=True),
        "eventCatalogSha256": sha256_file(ROOT / "event-catalog.json"),
        "runnerSha256": sha256_file(Path(__file__)),
        "timeoutSeconds": args.timeout,
    })


def input_sha256(args, case, event_catalog, evaluation_set_version, subject_commit, skill_sha, held_out_set):
    return hash_json({
        "runConfigSha256": run_config_sha256(args, evaluation_set_version, subject_commit, skill_sha, held_out_set),
        "case": case,
        "prompt": prompt_for(case, event_catalog),
        "repetition": args.repetition,
    })


def parse_trace(path: Path):
    events = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except ValueError as error:
            raise ValueError(f"{path}:{line_number}: JSONLを読めません: {error}") from error
        if not isinstance(event, dict):
            raise ValueError(f"{path}:{line_number}: traceイベントはJSON objectが必要です")
        events.append(event)
    return events


OBSERVATION_FIELDS = (
    "selectedEntry", "selectedPath", "outcome", "events", "rejectedEvents", "readyClaimed", "evidencePresent"
)


def observation_from_trace(events):
    starts = [index for index, event in enumerate(events) if event.get("type") == "turn.started"]
    completions = [index for index, event in enumerate(events) if event.get("type") == "turn.completed"]
    if (len(starts) != 1 or len(completions) != 1 or not events
            or completions[0] != len(events) - 1 or starts[0] >= completions[0]
            or any(event.get("type") != "thread.started" for event in events[:starts[0]])
            or any(event.get("type") == "turn.failed" for event in events)):
        raise ValueError("traceは単一の成功したturn.completedが必要です")
    pending = {}
    completed_ids = set()
    for event in events[starts[0] + 1:completions[0]]:
        event_type = event.get("type")
        if event_type not in {"item.started", "item.updated", "item.completed"}:
            raise ValueError("traceのturn内に予期しないイベントがあります")
        item = event.get("item")
        item_id = item.get("id") if isinstance(item, dict) else None
        if not isinstance(item_id, str):
            raise ValueError("traceのitem識別子が不正です")
        item_type = item.get("type")
        if not isinstance(item_type, str):
            raise ValueError("traceのitem種別が不正です")
        if event_type == "item.started":
            if item_id in pending or item_id in completed_ids:
                raise ValueError("traceのitem開始が不正です")
            pending[item_id] = item_type
        elif event_type == "item.updated":
            if pending.get(item_id) != item_type:
                raise ValueError("traceのitem更新が開始済みitemと一致しません")
        else:
            if item_id in completed_ids:
                raise ValueError("traceのitem完了が重複しています")
            if item_id in pending and pending[item_id] != item_type:
                raise ValueError("traceのitem種別が開始時と一致しません")
            completed_ids.add(item_id)
            pending.pop(item_id, None)
    if pending:
        raise ValueError("traceに未完了のitemがあります")
    item_events = [event for event in events[starts[0] + 1:completions[0]]
                   if isinstance(event.get("type"), str) and event["type"].startswith("item.")]
    final_event = item_events[-1] if item_events else None
    final_item = final_event.get("item") if final_event else None
    if (not final_event or final_event.get("type") != "item.completed"
            or not isinstance(final_item, dict) or final_item.get("type") != "agent_message"):
        raise ValueError("traceの最終itemが判断ではありません")
    try:
        decision = json.loads(final_item["text"])
        return {key: decision[key] for key in OBSERVATION_FIELDS}
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"traceの最終応答を判断として読めません: {error}") from error


def run_one(args, case, event_catalog, evaluation_set_version, subject_commit, skill_sha, read_bytes, held_out_set):
    run_dir = args.output / args.architecture / f"repetition-{args.repetition}" / case["caseId"]
    trace_path = run_dir / "trace.jsonl"
    decision_path = run_dir / "decision.json"
    stderr_path = run_dir / "stderr.log"
    record_path = run_dir / "run.json"
    identity = execution_identity(args, case, evaluation_set_version, subject_commit, skill_sha, held_out_set)
    expected_config_sha = run_config_sha256(args, evaluation_set_version, subject_commit, skill_sha, held_out_set)
    expected_input_sha = input_sha256(args, case, event_catalog, evaluation_set_version, subject_commit, skill_sha, held_out_set)
    if args.resume and record_path.is_file():
        record = json.loads(record_path.read_text(encoding="utf-8"))
        if any(record.get(key) != value for key, value in identity.items() if key != "heldOutSet") or record.get("heldOutSet") != held_out_set:
            raise RuntimeError(f"{case['caseId']}: 実行条件が前回の記録と一致しません")
        if record.get("runConfigSha256") != expected_config_sha or record.get("inputSha256") != expected_input_sha:
            raise RuntimeError(f"{case['caseId']}: 入力条件のhashが前回の記録と一致しません")
        if (not trace_path.is_file()
                or record.get("trace", {}).get("path") != trace_path.relative_to(args.output).as_posix()
                or record.get("trace", {}).get("sha256") != sha256_file(trace_path)):
            raise RuntimeError(f"{case['caseId']}: 保存されたtraceのhashが一致しません")
        if not args.rescore_existing:
            return record, "skipped"
        trace_events = parse_trace(trace_path)
        if record["observation"] != observation_from_trace(trace_events):
            raise RuntimeError(f"{case['caseId']}: 記録した判断がtraceの最終応答と一致しません")
        record["checks"]["safety"] = not trace_has_forbidden_action(trace_events)
        record["checks"]["skillRead"] = selected_skill_was_read(
            trace_events, record["observation"]["selectedEntry"], args.architecture)
        record["checks"]["deterministic"] = (
            not load_validator_module().observation_errors(record["observation"], args.architecture)
            and record["checks"]["skillRead"]
        )
        record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return record, "rescored"

    run_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="workspace-", dir=run_dir) as directory:
        workspace = Path(directory)
        skills_destination = workspace / ".codex/skills"
        skills_destination.parent.mkdir(parents=True)
        shutil.copytree(CANDIDATES / args.architecture / "skills", skills_destination)
        execution_schema = workspace / "decision.schema.json"
        execution_schema.write_text(
            json.dumps(decision_schema_for(args.architecture, for_execution=True), ensure_ascii=False), encoding="utf-8"
        )
        subprocess.run(["git", "init", "--quiet"], cwd=workspace, check=True)

        command = [
            "codex", "exec", "--json", "--ephemeral", "--ignore-user-config", "--ignore-rules",
            "-c", f"log_dir={json.dumps(str(workspace / 'logs'))}",
            "-c", f"sqlite_home={json.dumps(str(workspace / 'state'))}",
            "-c", "features.shell_snapshot=false",
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
    observation = {key: decision[key] for key in OBSERVATION_FIELDS}
    if observation != observation_from_trace(events):
        raise RuntimeError(f"{case['caseId']}: 保存した判断がtraceの最終応答と一致しません")
    validator = load_validator_module()
    skill_read = selected_skill_was_read(events, observation["selectedEntry"], args.architecture)
    deterministic = not validator.observation_errors(observation, args.architecture) and skill_read
    record = {
        "schemaVersion": "1.1",
        "evaluationSetVersion": evaluation_set_version,
        "caseId": case["caseId"],
        "architecture": args.architecture,
        "model": identity["model"],
        "repetition": args.repetition,
        "timeoutSeconds": args.timeout,
        "subjectCommit": subject_commit,
        "skillSetSha256": skill_sha,
        "runConfigSha256": expected_config_sha,
        "inputSha256": expected_input_sha,
        "trace": {"path": trace_path.relative_to(args.output).as_posix(), "sha256": sha256_file(trace_path)},
        "observation": observation,
        "checks": {"deterministic": deterministic, "safety": not forbidden_action_observed,
                   "skillRead": skill_read,
                   "rubric": "not-scored", "independentReview": "not-required"},
        "metrics": {"wallMs": wall_ms, "inputTokens": input_tokens, "outputTokens": output_tokens, "estimatedCostUsd": None, "readBytes": read_bytes},
    }
    if held_out_set is not None:
        record["heldOutSet"] = held_out_set
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
    parser.add_argument("--held-out-cases", type=Path)
    parser.add_argument("--case", action="append", dest="case_ids")
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--rescore-existing", action="store_true")
    args = parser.parse_args(argv)
    if args.rescore_existing and not args.resume:
        parser.error("--rescore-existingには--resumeが必要です")
    args.output = args.output.resolve()
    if args.held_out_cases is not None and args.output.is_relative_to(ROOT.parent.parent):
        parser.error("保持ケースの実行結果は公開リポジトリ外へ保存してください")

    validator = load_validator_module()
    audit = validator.audit()
    if audit["status"] != "Passed":
        raise SystemExit(json.dumps(audit, ensure_ascii=False, indent=2))
    cases = validator.load_cases()
    held_out = None
    if args.held_out_cases is not None:
        private_cases, held_out = validator.load_held_out_cases(args.held_out_cases)
        cases.extend(private_cases)
    evaluation_set_version = audit["evaluationSetVersion"]
    if args.case_ids:
        unknown = sorted(set(args.case_ids) - {case["caseId"] for case in cases})
        if unknown:
            raise SystemExit(f"未知のcaseIdです: {', '.join(unknown)}")
        cases = [case for case in cases if case["caseId"] in set(args.case_ids)]

    event_catalog = validator.load_event_catalog()["events"]
    skills = CANDIDATES / args.architecture / "skills"
    skill_sha = sha256_tree(skills)
    read_bytes = sum(path.stat().st_size for path in skills.rglob("*") if path.is_file())
    subject_commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stdout=subprocess.PIPE, check=True).stdout.strip()

    records = []
    failures = []
    with ThreadPoolExecutor(max_workers=args.jobs) as executor:
        future_cases = {
            executor.submit(
                run_one, args, case, event_catalog, evaluation_set_version, subject_commit, skill_sha, read_bytes,
                held_out
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
    print(json.dumps({"architecture": args.architecture, "repetition": args.repetition, "runs": len(records), "heldOut": held_out, "failures": failures, "output": str(summary_path)}, ensure_ascii=False, indent=2))
    return 0 if not failures and len(records) == len(cases) else 1


if __name__ == "__main__":
    raise SystemExit(main())
