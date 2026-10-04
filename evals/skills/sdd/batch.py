"""固定した有限SDD測定。旧測定の再開・再採点には使わない。"""
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from types import SimpleNamespace
import uuid


def save(path, value):
    temporary = path.with_suffix(".new")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def plan(evaluation, args, cases):
    root, here = evaluation.ROOT.resolve(), evaluation.HERE.resolve()
    approval = evaluation.load(here.parent / "sol-authorization.json")
    if (approval.get("approvalStatus") != "approved" or approval.get("approvedBy") != "user"
            or approval.get("models") != ["gpt-6.1-sol"] or args.model != "gpt-6.1-sol"
            or approval.get("scope") != "BitzSkillsの開発に必要なsol評価、独立検分と是正後の新測定"):
        raise ValueError("sol限定の評価承認が一致しません")
    manifest = args.batch.resolve()
    if manifest.parent != here / "batches":
        raise ValueError("確定refのbatches内の測定条件が必要です")
    committed = subprocess.check_output(["git", "show", "HEAD:" + manifest.relative_to(root).as_posix()], cwd=root)
    if committed != manifest.read_bytes():
        raise ValueError("測定条件が確定refと一致しません")
    batch = evaluation.load(manifest)
    protocol = evaluation.load(here / "protocol.json")
    if (batch.get("schemaVersion") != "1.0" or not re.fullmatch(r"[a-z0-9-]+", batch.get("id", ""))
            or batch.get("model") != args.model or batch.get("automaticRetries") != 0
            or batch.get("protocolSha256") != evaluation.digest((here / "protocol.json").read_bytes())
            or batch.get("casesSha256") != evaluation.digest((here / "cases.json").read_bytes())
            or batch.get("candidateVersion") != evaluation.load(root / "plugins/bitz-sdd/plugin.json")["version"]
            or protocol.get("model") != args.model or protocol.get("automaticRetries") != 0):
        raise ValueError("評価版・入力・候補版・モデルの固定条件が一致しません")
    slots = batch.get("slots", [])
    known = {c["id"] for c in cases}
    if (not slots or type(batch.get("maximumPrimaryCalls")) is not int
            or batch["maximumPrimaryCalls"] != len(slots) or len(slots) > protocol["maximumCalls"]
            or any(set(s) != {"caseId", "variant", "repetition"} or s["caseId"] not in known
                   or s["variant"] not in {"skill", "baseline"} or type(s["repetition"]) is not int
                   or s["repetition"] not in {1, 2} for s in slots)
            or len({evaluation.json_digest(s) for s in slots}) != len(slots)):
        raise ValueError("有限のケース・反復・分母が不正です")
    if (args.jobs != 1 or args.resume or type(args.timeout) is not int
            or not 1 <= args.timeout <= 600 or args.timeout != batch.get("timeoutSeconds")
            or not args.model_version.strip() or not args.pythonpath
            or any(not Path(p).is_absolute() or not Path(p).is_dir() for p in args.pythonpath.split(os.pathsep))
            or Path(args.pythonpath.split(os.pathsep)[0]).resolve() != (root / "plugins/bitz-core/src").resolve()):
        raise ValueError("逐次実行・再試行なし・固定timeout・絶対Python pathが必要です")
    args.output = args.output.resolve()
    storage = root / ".venv"
    ledgers = storage / "sdd-batch-ledgers"
    if (not args.output.is_relative_to(storage) or args.output == storage
            or args.output.is_relative_to(ledgers) or ledgers.is_relative_to(args.output)):
        raise ValueError("出力は台帳と分離したリポジトリ内.venvへ置いてください")
    if subprocess.run(["git", "check-ignore", "-q", str(args.output)], cwd=root).returncode != 0:
        raise ValueError("評価出力はGitの管理対象から除外してください")
    # モデル起動・台帳作成前に、ホストと同じ環境で公開Core CLIを実行する。
    doctor = subprocess.run([sys.executable, "-B", "-m", "bitz.cli", "doctor", "--format", "json"],
        cwd=root, env={"PATH": "/usr/bin:/bin", "PYTHONPATH": args.pythonpath,
                       "PYTHONDONTWRITEBYTECODE": "1", "LC_ALL": "C.UTF-8"},
        capture_output=True, text=True, timeout=20)
    if doctor.returncode != 0:
        raise ValueError("公開Core doctorが起動前検査で非成功でした")
    doctor_result = json.loads(doctor.stdout)
    if doctor_result.get("status") not in evaluation.PASS:
        raise ValueError("公開Core doctorが起動前検査で非成功でした")
    doctor_result.pop("durationMs", None)  # 実時間は同条件で変動するため入力同一性へ含めない。
    return batch, {"output": str(args.output), "batchSha256": evaluation.digest(committed),
                   "authorizationSha256": evaluation.digest((here.parent / "sol-authorization.json").read_bytes()),
                   "codexVersion": subprocess.check_output(["codex", "--version"], text=True).strip(),
                   "timeoutSeconds": args.timeout,
                   "pythonExecutable": sys.executable, "pythonVersion": sys.version,
                   "coreDoctorSha256": evaluation.json_digest(doctor_result),
                   "identities": [evaluation.identity(SimpleNamespace(**(vars(args) | {
                       "variant": s["variant"], "repetition": s["repetition"]})), next(c for c in cases if c["id"] == s["caseId"]))
                       for s in slots]}


@contextmanager
def locked(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError("同じ測定を別プロセスが実行中です") from error
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def directory(args, slot):
    return args.output / slot["variant"] / f"repetition-{slot['repetition']}" / slot["caseId"]


def verify_previous(evaluation, args, attempt, cases):
    if attempt["status"] != "completed":
        raise ValueError("失敗・中断済み測定を自動再開しません")
    target = directory(args, attempt["slot"])
    record = evaluation.load(target / "run.json")
    if (evaluation.digest((target / "run.json").read_bytes()) != attempt["runSha256"]
            or evaluation.inspect(record, cases[attempt["slot"]["caseId"]], target) != record["checks"]
            or not all(c["passed"] for c in record["checks"].values())):
        raise ValueError("前件の実証拠または必須検査が一致しません")
    receipt = evaluation.load(target / "independent-review.json")
    required = set(record["checks"]) | {"semantic"}
    if (receipt.get("schemaVersion") != "1.0" or receipt.get("status") != "passed"
            or receipt.get("independent") is not True or receipt.get("implementationPrivateHistoryInherited") is not False
            or receipt.get("evaluationRunId") != attempt["evaluationRunId"]
            or not isinstance(receipt.get("reviewRunId"), str) or not receipt["reviewRunId"].strip()
            or receipt["reviewRunId"] == attempt["evaluationRunId"]
            or receipt.get("subjectCommit") != record["identity"]["subjectCommit"]
            or receipt.get("runSha256") != attempt["runSha256"]
            or receipt.get("checks") != {name: "passed" for name in required}
            or not isinstance(receipt.get("directChecks"), list) or not receipt["directChecks"]
            or any(not isinstance(c, str) or not c.strip() for c in receipt["directChecks"])
            or not isinstance(receipt.get("reason"), str) or not receipt["reason"].strip()):
        raise ValueError("前件の別文脈の実検分と意味適合が必要です")


def run(evaluation, args, cases):
    batch, conditions = plan(evaluation, args, cases)
    path = evaluation.ROOT / ".venv/sdd-batch-ledgers" / (batch["id"] + ".json")
    if (path.is_symlink() or path.with_suffix(".lock").is_symlink()
            or not path.resolve().is_relative_to(evaluation.ROOT.resolve() / ".venv")):
        raise ValueError("台帳のsymlinkまたはリポジトリ外保存は許可しません")
    with locked(path.with_suffix(".lock")):
        if path.exists():
            ledger = evaluation.load(path)
            if ledger["conditions"] != conditions:
                raise ValueError("確定ref・出力・実行条件の変更で台帳をリセットしません")
        else:
            if args.output.exists():
                raise ValueError("既存出力を新測定へ流用しません")
            ledger = {"conditions": conditions, "attemptCount": 0, "attempts": []}
        count = ledger["attemptCount"]
        if (type(count) is not int or count != len(ledger["attempts"]) or count < 0
                or count > batch["maximumPrimaryCalls"]
                or [a["slot"] for a in ledger["attempts"]] != batch["slots"][:count]):
            raise ValueError("台帳の呼出し数または固定順序が不正です")
        by_id = {c["id"]: c for c in cases}
        for attempt in ledger["attempts"]:
            verify_previous(evaluation, args, attempt, by_id)
        if count == batch["maximumPrimaryCalls"]:
            raise ValueError("固定した一次評価の呼出し上限に到達しました")
        slot = batch["slots"][count]
        if args.case != [slot["caseId"]] or args.variant != slot["variant"] or args.repetition != slot["repetition"]:
            raise ValueError("台帳の次の固定ケースを1件だけ指定してください")
        if directory(args, slot).exists():
            raise ValueError("未登録の既存出力を上書きしません")
        attempt = {"slot": slot, "evaluationRunId": str(uuid.uuid4()), "status": "started"}
        ledger["attempts"].append(attempt)
        ledger["attemptCount"] += 1
        save(path, ledger)  # 外部呼出し前に消費する。例外・強制終了でも巻き戻さない。
        try:
            record = evaluation.run_one(args, by_id[slot["caseId"]])
            attempt["runSha256"] = evaluation.digest((directory(args, slot) / "run.json").read_bytes())
            attempt["status"] = "completed" if all(c["passed"] for c in record["checks"].values()) else "failed"
        except BaseException as error:
            attempt["status"] = "interrupted"
            attempt["errorType"] = type(error).__name__
            save(path, ledger)
            raise
        save(path, ledger)
        print(json.dumps({"caseId": slot["caseId"], "evaluationRunId": attempt["evaluationRunId"],
                          "checks": record["checks"], "primaryCallsUsed": ledger["attemptCount"],
                          "primaryCallsMaximum": batch["maximumPrimaryCalls"],
                          "nextRequiresIndependentReview": True, "gateDecision": "not-certified"}, ensure_ascii=False))
        return int(attempt["status"] != "completed")
