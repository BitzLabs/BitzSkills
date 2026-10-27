"""合成故障検証の保存証拠を展開せず、manifestと独立判定を再確認する。"""
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys
import tarfile


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def audit(archive):
    manifest = json.loads(archive.with_name("manifest.json").read_text(encoding="utf-8"))
    errors, payloads = [], {}
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
        errors.append("archive member set mismatch")
    for name, expected in manifest["files"].items():
        raw = payloads.get(name, b"")
        if digest(raw) != expected["sha256"] or len(raw) != expected["bytes"]:
            errors.append("file mismatch: " + name)
    for prefix, status, ref in (("original", "failed", manifest["originalSourceCommit"]),
                               ("remediation", "passed", manifest["sourceCommit"])):
        record = json.loads(payloads[prefix + "-review.json"])
        if record["status"] != status or record["sourceCommit"] != ref:
            errors.append("review identity/status mismatch: " + prefix)
    corrected = json.loads(payloads["remediation-review.json"])
    for name, expected in corrected["changedFileSha256"].items():
        if digest(payloads["source/" + PurePosixPath(name).name]) != expected:
            errors.append("source snapshot mismatch: " + name)
    for name, expected in manifest["originalSourceSha256"].items():
        if digest(payloads[name]) != expected:
            errors.append("original source snapshot mismatch: " + name)
    for name in ("scope.json", "remediation-scope.json"):
        scope = json.loads(payloads[name])
        if scope["maximumNewPrimaryTrajectories"] != 0 or scope["maximumNewIndependentCalls"] != 1 or scope["automaticRetries"] != 0:
            errors.append("finite scope mismatch: " + name)
        expected_status = "failed" if name == "scope.json" else "passed"
        if scope["model"] != "gpt-6.1-sol" or scope["attempts"][0]["status"] != expected_status:
            errors.append("scope result mismatch: " + name)
    return {"status": "passed" if not errors else "failed", "archiveSha256": digest(archive.read_bytes()),
            "files": len(payloads), "bytes": sum(map(len, payloads.values())), "errors": errors,
            "limits": "保存同一性と判定の分離のみ。実モデル測定・Skill Gate認定ではない。"}


if __name__ == "__main__":
    result = audit(Path(sys.argv[1]).resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(result["status"] != "passed")
