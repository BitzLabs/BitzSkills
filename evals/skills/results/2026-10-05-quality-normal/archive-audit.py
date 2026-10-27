"""保存tarの来歴と入力を標準ライブラリのみで検査する。展開/実行しない。"""
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys
import tarfile

path = Path(sys.argv[1])
files = {}
with tarfile.open(path, "r:gz") as archive:
    members = archive.getmembers()
    for member in members:
        name = PurePosixPath(member.name)
        assert not name.is_absolute() and ".." not in name.parts
        assert not member.issym() and not member.islnk()
        assert member.isfile() or member.isdir()
        assert not set(name.parts) & {".git", "codex-state", "logs", "state", ".env", ".credentials.json"}
        assert name.name != "stderr.log" and not name.name.endswith((".sqlite", ".sqlite-shm", ".sqlite-wal"))
        if member.isfile():
            assert str(name) not in files
            files[str(name)] = archive.extractfile(member).read()

def load(name):
    return json.loads(files[name])

attempts = load("attempts.json")
conditions = load("conditions.json")
summary = load("summary.json")
budget = load("independent-budget.json")
assert len(attempts) == summary["primaryAttempts"] == summary["independentPassed"] == 8
assert load("authorization-ledger.json")["attemptCount"] == 8
assert load("cap-proof.json")["codexCalls"] == 0
assert len(budget["preparation"]) == budget["maximumPreparationReviews"] == 1
assert budget["preparation"][0]["status"] == "passed"
assert len(budget["trajectoryReviews"]) == budget["maximumTrajectoryReviews"] == 8
assert all(r["status"] == "passed" for r in budget["trajectoryReviews"])
assert summary["sourceCommit"] == conditions["sourceCommit"]
source_manifest = load("source-manifest.json")
assert source_manifest["sourceCommit"] == conditions["sourceCommit"] and source_manifest["matchesCommittedRef"]
for item in source_manifest["files"].values():
    assert hashlib.sha256(files[item["archivePath"]]).hexdigest() == item["sha256"]
artifact_count = input_count = receipt_count = 0
threads = []
for attempt in attempts:
    directory = attempt["directory"]
    record = load(directory + "/run.json")
    control = load(directory + "/control.json")
    receipt = load(directory + "/independent-receipt.json")
    assert all(record["identity"][key] == value for key, value in conditions.items())
    for name, digest in record["artifacts"].items():
        if name == "stderr.log":
            continue
        assert hashlib.sha256(files[directory + "/" + name]).hexdigest() == digest, (directory, name)
        artifact_count += 1
    for name, digest in control["readableFiles"].items():
        key = directory + "/" + record["identity"]["caseId"] + "/" + name
        assert hashlib.sha256(files[key]).hexdigest() == digest, key
        input_count += 1
    assert receipt["runSha256"] == hashlib.sha256(files[directory + "/run.json"]).hexdigest()
    assert receipt["comparisonRunId"] == record["identity"]["runId"]
    assert receipt["sourceCommit"] == record["identity"]["sourceCommit"]
    assert receipt["subjectCommit"] == control["subjectCommit"]
    assert receipt["status"] == "passed" and all(v == "passed" for v in receipt["checks"].values())
    assert any(r["comparisonRunId"] == receipt["comparisonRunId"] and r["reviewRunId"] == receipt["reviewRunId"] for r in budget["trajectoryReviews"])
    row = next(row for row in summary["rows"] if row["runId"] == record["identity"]["runId"])
    assert row["runSha256"] == receipt["runSha256"]
    assert row["receiptSha256"] == hashlib.sha256(files[directory + "/independent-receipt.json"]).hexdigest()
    events = [json.loads(line) for line in files[directory + "/trace.jsonl"].splitlines() if line.strip()]
    threads.extend(event["thread_id"] for event in events if event.get("type") == "thread.started")
    receipt_count += 1
assert len(threads) == len(set(threads)) == 8
print(json.dumps({"status": "passed", "archiveSha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    "members": len(members), "files": len(files), "fileBytes": sum(len(v) for v in files.values()),
    "sourceCommit": conditions["sourceCommit"], "verifiedArtifactsExcludingStderr": artifact_count,
    "verifiedModelInputs": input_count, "verifiedIndependentReceipts": receipt_count,
    "verifiedSourceSnapshots": len(source_manifest["files"]),
    "uniqueNativeThreads": 8, "links": 0, "gitStateCredentialsAndStderrIncluded": False, "errors": []}, ensure_ascii=False))
