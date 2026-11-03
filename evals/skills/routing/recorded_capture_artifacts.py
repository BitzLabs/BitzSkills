"""回帰試験と保存済み捕捉の照合で使う、原ファイルの読取りと整合性検査。"""
from __future__ import annotations
import hashlib
from pathlib import Path
import production_sdk_trace as sdk
import source_guard

ROOT = Path(__file__).resolve().parents[3]
require = sdk.require


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def read(name: str):
    return sdk.trace.strict_json((ROOT / name).read_bytes())


def frames(base: Path, name: str):
    return [sdk.trace.strict_json(line) for line in (base / name).read_bytes().splitlines()]


def receipt(base: Path, *, expected_sha: str | None = None):
    require(not any(p.is_symlink() for p in (base, *base.parents)), 'artifact symlink')
    raw = (base / 'receipt.json').read_bytes()
    require(expected_sha is None or sha(raw) == expected_sha, 'original receipt hash drift')
    value = sdk.trace.strict_json(raw)
    for name, digest in value['artifactSha256'].items():
        require(Path(name).name == name and not (base / name).is_symlink(), 'artifact path')
        require(sha((base / name).read_bytes()) == digest, 'artifact hash drift')
    for stage in ('before', 'after'):
        guard = value['sourceGuards'][stage]
        require(guard['sourceCommit'] == value['sourceCommit'], 'artifact source binding')
        for name, digest in guard['sourceSha256'].items():
            require(sha(source_guard.git(ROOT, 'show', value['sourceCommit'] + ':' + name)) == digest,
                    'historical source hash drift')
    require(value['namespaceExitCode'] == 0 and value['paidModelCalls'] == 0 and
            value['runtime']['exitCode'] == 0 and value['runtime']['forcedShutdown'] is False, 'probe runtime failed')
    return value, sha(raw)
