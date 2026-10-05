"""SDD中断是正の保存同一性と限定検査の記録を監査する。"""
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys
import tarfile


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def audit(archive):
    manifest = json.loads(archive.with_name("manifest.json").read_text())
    errors, files = [], {}
    if digest(archive.read_bytes()) != manifest["archiveSha256"]:
        errors.append("archive hash mismatch")
    with tarfile.open(archive, "r:gz") as bundle:
        for member in bundle.getmembers():
            path = PurePosixPath(member.name)
            if not member.isfile() or path.is_absolute() or ".." in path.parts or member.name in files:
                errors.append("unsafe or duplicate member: " + member.name)
                continue
            files[member.name] = bundle.extractfile(member).read()
    if set(files) != set(manifest["files"]):
        errors.append("member set mismatch")
    for name, expected in manifest["files"].items():
        raw = files.get(name, b"")
        if len(raw) != expected["bytes"] or digest(raw) != expected["sha256"]:
            errors.append("file mismatch: " + name)
    for name, expected in manifest["sourceSnapshotSha256"].items():
        if digest(files[name]) != expected:
            errors.append("source mismatch: " + name)
    failed = json.loads(files["first-review/review.json"])
    corrected = json.loads(files["final-review/review.json"])
    parent = json.loads(files["parent-audit.json"])
    if failed["status"] != "failed" or not any(f["priority"] == "P2" for f in failed["findings"]):
        errors.append("original failed/P2 not retained")
    if corrected["status"] != "passed" or corrected["findings"] or corrected["sourceCommit"] != manifest["sourceCommit"]:
        errors.append("corrected review mismatch")
    if parent["status"] != "passed" or parent["targetedTests"] != 52:
        errors.append("parent targeted tests mismatch")
    if manifest["newPrimaryModelTrajectories"] != 0 or manifest["automaticRetries"] != 0:
        errors.append("finite scope mismatch")
    return {"schemaVersion": "1.0", "status": "passed" if not errors else "failed",
            "archiveSha256": digest(archive.read_bytes()), "files": len(files),
            "bytes": sum(map(len, files.values())), "errors": errors,
            "limits": "保存同一性と限定52件。全件検証・実モデル適合・全Skill Gateの認定ではない。"}


if __name__ == "__main__":
    result = audit(Path(sys.argv[1]).resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(result["status"] != "passed")
