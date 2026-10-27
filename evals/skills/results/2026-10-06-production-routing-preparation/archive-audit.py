"""Read-only archive integrity and fixed-source audit; no Gate certification."""
import hashlib
import json
import pathlib
import subprocess
import tarfile

root = pathlib.Path(__file__).resolve().parent
repo = root.parents[3]
manifest = json.loads((root / "manifest.json").read_text())
archive = root / "evidence.tar.gz"
assert hashlib.sha256(archive.read_bytes()).hexdigest() == manifest["archiveSha256"]
with tarfile.open(archive, "r:gz") as bundle:
    members = {m.name: m for m in bundle.getmembers() if m.isfile()}
    assert set(members) == set(manifest["files"])
    for name, expected in manifest["files"].items():
        data = bundle.extractfile(members[name]).read()
        assert len(data) == expected["bytes"]
        assert hashlib.sha256(data).hexdigest() == expected["sha256"]
    for source in manifest["fixedSources"]:
        data = bundle.extractfile(members[source["archivePath"]]).read()
        fixed = subprocess.check_output(
            ["git", "show", source["ref"] + ":" + source["path"]], cwd=repo
        )
        assert data == fixed
print(json.dumps({"status": "passed", "files": len(members),
                  "fixedSources": len(manifest["fixedSources"]),
                  "bytes": sum(x["bytes"] for x in manifest["files"].values()),
                  "archiveSha256": manifest["archiveSha256"],
                  "certifiesSkillGate": False}, indent=2))
