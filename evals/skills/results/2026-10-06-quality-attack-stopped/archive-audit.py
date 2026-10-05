"""失敗停止した比較の原証拠を展開せず監査する。"""
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys
import tarfile


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def audit(archive):
    manifest = json.loads(archive.with_name("manifest.json").read_text(encoding="utf-8"))
    errors, payloads, threads, common = [], {}, [], []
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
    for name, expected in manifest["sourceSnapshotSha256"].items():
        if digest(payloads["source/" + name]) != expected:
            errors.append("source snapshot mismatch: " + name)
    stop = json.loads(payloads["stop.json"])
    diagnosis = json.loads(payloads["failure-diagnosis.json"])
    if (stop["status"] != "stopped" or stop["consumedPrimaryTrajectories"] != 2
            or stop["unusedBudgetReusable"] or diagnosis["originalComparisonStatus"] != "failed"
            or diagnosis["independenceInterpretation"]["status"] != "unknown"
            or diagnosis["riskClassificationPassed"] is not False):
        errors.append("failure/unknown preservation mismatch")
    for group in manifest["primaryGroups"]:
        record, control, advice = (json.loads(payloads[group + "/" + name]) for name in ("run.json", "control.json", "advice.json"))
        for name, expected in record["artifacts"].items():
            if name != "stderr.log" and digest(payloads[group + "/" + name]) != expected:
                errors.append("artifact mismatch: " + group + "/" + name)
        if record["identity"]["sourceCommit"] != manifest["sourceCommit"]:
            errors.append("primary source mismatch: " + group)
        for name, expected in control["readableFiles"].items():
            if digest(payloads[group + "/QR-006/" + name]) != expected:
                errors.append("fixed input mismatch: " + group + "/" + name)
        common.append({**{k: control[k] for k in ("baseCommit", "subjectCommit", "fixtureFiles", "diff", "allowTests")},
            "readableFiles": {n: h for n, h in control["readableFiles"].items() if not n.startswith("resources/bitz-quality/skills/")}})
        trace = [json.loads(line) for line in payloads[group + "/trace.jsonl"].decode().splitlines() if line]
        threads.extend(e["thread_id"] for e in trace if e.get("type") == "thread.started")
        if record["identity"]["variant"] == "skill":
            receipt = json.loads(payloads[group + "/independent-receipt.json"])
            if any(record["checks"].values()) or receipt["status"] != "passed" or receipt["runSha256"] != digest(payloads[group + "/run.json"]):
                errors.append("original skill receipt changed")
        elif record["checks"]["evidence"] != ["independent run identity does not match actual fresh run"] or advice["riskBand"] != "Q2":
            errors.append("original baseline failure changed")
    if len(threads) != 2 or len(set(threads)) != 2 or common[0] != common[1]:
        errors.append("native thread/common input mismatch")
    return {"schemaVersion": "1.0", "status": "passed" if not errors else "failed",
            "archiveSha256": digest(archive.read_bytes()), "files": len(payloads),
            "bytes": sum(map(len, payloads.values())), "primaryRuns": 2, "uniqueNativeThreads": len(set(threads)),
            "originalComparisonStatus": "failed", "independenceInterpretation": "unknown", "errors": errors,
            "limits": "保存監査のpassedであり、停止した比較や独立性の不明を合格へ変換しない。"}


if __name__ == "__main__":
    result = audit(Path(sys.argv[1]).resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(result["status"] != "passed")
