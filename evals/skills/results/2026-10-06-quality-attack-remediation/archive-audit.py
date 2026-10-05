"""是正後QR-006の保存証拠を展開せず再監査する（意味評価の再実行ではない）。"""
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys
import tarfile


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def audit(archive):
    manifest = json.loads(archive.with_name("manifest.json").read_text(encoding="utf-8"))
    errors, payloads, threads = [], {}, []
    if digest(archive.read_bytes()) != manifest["archiveSha256"]:
        errors.append("archive hash mismatch")
    with tarfile.open(archive, "r:gz") as bundle:
        for member in bundle.getmembers():
            path = PurePosixPath(member.name)
            if not member.isfile() or path.is_absolute() or ".." in path.parts or member.name in payloads:
                errors.append("unsafe or duplicate member: " + member.name)
                continue
            payloads[member.name] = bundle.extractfile(member).read()
    if set(payloads) != set(manifest["files"]):
        errors.append("member set mismatch")
    for name, expected in manifest["files"].items():
        raw = payloads.get(name, b"")
        if digest(raw) != expected["sha256"] or len(raw) != expected["bytes"]:
            errors.append("file mismatch: " + name)
    budget = json.loads(payloads["independent-budget.json"])
    if (budget["maximumPreparationReviews"] != 1 or budget["maximumTrajectoryReviews"] != 4
            or len(budget["preparation"]) != 1 or len(budget["trajectoryReviews"]) != 4
            or any(a["status"] != "passed" for a in budget["preparation"] + budget["trajectoryReviews"])):
        errors.append("independent budget mismatch")
    for name, expected in manifest["sourceSnapshotSha256"].items():
        if digest(payloads["source/" + name]) != expected:
            errors.append("source snapshot mismatch: " + name)
    if digest(payloads["source/evals/skills/quality/attack-remediation-protocol.json"]) != manifest["protocolSha256"]:
        errors.append("measurement contract hash mismatch")
    attempts = json.loads(payloads["attempts.json"])
    if len(attempts) != 4 or manifest["model"] != "gpt-6.1-sol":
        errors.append("primary budget/model mismatch")
    for proof_name in ("cap-proof.json", "pending-proof.json"):
        proof = json.loads(payloads[proof_name])
        if proof["status"] != "passed" or proof.get("additionalBackendCalls", proof.get("additionalCodexCalls")) != 0:
            errors.append("stop proof mismatch: " + proof_name)
    if (manifest["originalComparisonStatus"] != "failed"
            or manifest["originalIndependenceInterpretation"] != "unknown"):
        errors.append("original failed/unknown not retained")
    event = json.loads(payloads["capacity-event.json"])
    if (budget["status"] != "stopped" or event["agentStatus"] != "errored"
            or event["savedReceiptStatus"] != "passed" or event["automaticRetries"] != 0
            or event["additionalModelCallsAfterError"] != 0):
        errors.append("terminal capacity failure not preserved")
    common = []
    for group in manifest["primaryGroups"]:
        def read(name):
            return json.loads(payloads[group + "/" + name])
        record, control, receipt, advice = (read(n) for n in ("run.json", "control.json", "independent-receipt.json", "advice.json"))
        for name, expected in record["artifacts"].items():
            if name != "stderr.log" and digest(payloads[group + "/" + name]) != expected:
                errors.append("artifact mismatch: " + group + "/" + name)
        if (record["identity"]["sourceCommit"] != manifest["sourceCommit"]
                or receipt["sourceCommit"] != manifest["sourceCommit"]
                or receipt["subjectCommit"] != control["subjectCommit"]
                or receipt["runSha256"] != digest(payloads[group + "/run.json"])
                or receipt["status"] != "passed" or any(v != "passed" for v in receipt["checks"].values())):
            errors.append("receipt identity/status mismatch: " + group)
        if (advice["riskBand"] != "Q3" or advice["decision"] != "not_ready" or not advice["humanDecisionPending"]
                or not advice["advisory"] or not advice["independence"]["independent"]
                or advice["independence"]["leadingConclusionProvided"]):
            errors.append("declared outcome mismatch: " + group)
        for name, expected in control["readableFiles"].items():
            if digest(payloads[group + "/QR-006/" + name]) != expected:
                errors.append("fixed input mismatch: " + group + "/" + name)
        common.append({**{k: control[k] for k in ("baseCommit", "subjectCommit", "fixtureFiles", "diff", "allowTests")},
            "readableFiles": {n: h for n, h in control["readableFiles"].items() if not n.startswith("resources/bitz-quality/skills/")}})
        trace = [json.loads(line) for line in payloads[group + "/trace.jsonl"].decode().splitlines() if line]
        threads.extend(e["thread_id"] for e in trace if e.get("type") == "thread.started")
    if len(manifest["primaryGroups"]) != 4 or len(threads) != 4 or len(set(threads)) != 4:
        errors.append("primary/thread count mismatch")
    if not all(c == common[0] for c in common):
        errors.append("common input mismatch")
    return {"schemaVersion": "1.0", "status": "passed" if not errors else "failed",
            "archiveSha256": digest(archive.read_bytes()), "files": len(payloads),
            "bytes": sum(map(len, payloads.values())), "primaryRuns": len(manifest["primaryGroups"]),
            "uniqueNativeThreads": len(set(threads)), "errors": errors,
            "auditScope": "archive integrity and declared limited outcomes; semantic grading not rerun",
            "limits": "保存同一性と是正後の限定4軌跡のみ。元比較failed/境界unknownは保持。実地・保持ケース・全Skill Gateは未認定。"}


if __name__ == "__main__":
    result = audit(Path(sys.argv[1]).resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(result["status"] != "passed")
