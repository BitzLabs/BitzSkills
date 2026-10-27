"""固定private stageの既知原だけをowner-only/NOFOLLOWで読み、メモリ内で照合する。"""
import os
import re
from pathlib import Path
import stat

import production_heldout_evidence as evidence

x, io, require = evidence.x, evidence.io, evidence.require
MAX_FILE_BYTES = 64*1024*1024
MAX_TOTAL_BYTES = 256*1024*1024
MAX_ORIGINALS = 512


def _open_root(root):
    require(isinstance(root, Path) and root.is_absolute() and '..' not in root.parts
        and root.is_relative_to(x.inputs.PRIVATE_CASES.parent), 'heldout private original root')
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    current = Path('/')
    try:
        for part in root.parts[1:]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
            current /= part
            if current.is_relative_to(x.inputs.PRIVATE_CASES.parent):
                value = os.fstat(fd)
                require(stat.S_IMODE(value.st_mode) == 0o700 and value.st_uid == os.getuid()
                    and value.st_nlink >= 2, 'heldout original private directory')
        return fd
    except BaseException:
        os.close(fd)
        raise


def additional_names(values):
    require(isinstance(values,frozenset) and not values & {'auth.json','.env','.credentials.json'}
        and all(isinstance(name,str) and re.fullmatch(r'[a-z][a-z0-9-]*\.(json|jsonl|txt|bin)',name) is not None
            for name in values), 'heldout fixed additional names')


def read_original(root, name, *, additional_artifacts=frozenset()):
    additional_names(additional_artifacts)
    require(isinstance(name, str), 'heldout original name')
    if name not in evidence.ADDITIONAL | {'receipt.json'} | additional_artifacts:
        evidence.inventory.artifact_name(name)
    fd = _open_root(root)
    root_info = os.fstat(fd)
    try:
        for part in Path(name).parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
            value = os.fstat(fd)
            require(stat.S_IMODE(value.st_mode) == 0o700 and value.st_uid == os.getuid(), 'heldout original directory drift')
        file = os.open(Path(name).name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        try:
            before = os.fstat(file)
            require(stat.S_ISREG(before.st_mode) and stat.S_IMODE(before.st_mode) == 0o600
                and before.st_uid == os.getuid() and before.st_nlink == 1
                and 0 <= before.st_size <= MAX_FILE_BYTES, 'heldout private original file')
            with os.fdopen(file, 'rb', closefd=False) as stream:
                raw = stream.read(MAX_FILE_BYTES+1)
            after = os.fstat(file)
            identity = lambda s: (s.st_dev, s.st_ino, s.st_mode, s.st_uid, s.st_nlink,
                s.st_size, s.st_mtime_ns, s.st_ctime_ns)
            directory = os.fstat(fd)
            require(identity(before) == identity(after) and len(raw) == before.st_size
                and stat.S_IMODE(directory.st_mode) == 0o700 and directory.st_uid == os.getuid(),
                'heldout original read drift')
            root_fd = _open_root(root)
            try:
                current = os.fstat(root_fd)
                require((current.st_dev, current.st_ino) == (root_info.st_dev, root_info.st_ino),
                    'heldout original root identity drift')
            finally:
                os.close(root_fd)
            return raw
        finally:
            os.close(file)
    finally:
        os.close(fd)


def load(bound, ordinal, *, source_repository):
    x.rebound(bound)
    base = bound.stage_root(ordinal, 'primary')
    receipt_raw = read_original(base, 'receipt.json')
    receipt = x.inputs.parse(receipt_raw)
    require(isinstance(receipt, dict) and set(receipt) == evidence.RECEIPT_KEYS
        and receipt['version'] == evidence.VERSION, 'heldout private original receipt')
    declared = receipt['artifactSha256']
    names = evidence.inventory.artifact_inventory(base, declared, additional_artifacts=evidence.ADDITIONAL)
    require(len(names) <= MAX_ORIGINALS, 'heldout finite original inventory')
    fd = _open_root(base)
    try:
        for name in evidence.inventory.OPAQUE_DIRECTORIES:
            if name in os.listdir(fd):
                value = os.stat(name, dir_fd=fd, follow_symlinks=False)
                require(stat.S_ISDIR(value.st_mode) and stat.S_IMODE(value.st_mode) == 0o700
                    and value.st_uid == os.getuid(), 'heldout opaque directory metadata')
    finally:
        os.close(fd)
    originals, total = {}, 0
    for name in names:
        raw = read_original(base, name)
        total += len(raw)
        require(total <= MAX_TOTAL_BYTES, 'heldout finite original bytes')
        originals[name] = raw
    d = x.deployment_for_execution(bound.execution_raw, bound.deployment_raw)
    p = evidence.preflight.public
    fixed_sources = {name: io.sha(p.guard.git(source_repository, 'show',
        bound.contract['sourceCommit']+':'+name)) for name in evidence.preflight.SOURCE_FILES}
    guards = x.inputs.parse(originals['resource-guards.json'])
    require(isinstance(guards, dict) and set(guards) == {'before', 'invoke', 'after'}
        and all(isinstance(value, dict) and value.get('sourceSha256') == fixed_sources
            for value in guards.values()), 'heldout original fixed Git source mismatch')
    schema_raw = p.decision_schema(p.guard.git(source_repository, 'show',
        bound.contract['sourceCommit']+':'+p.inventory.SCHEMA))
    context_raw = p.guard.git(source_repository, 'show', bound.contract['sourceCommit']+':'+p.inventory.CONTEXT)
    manifest_raw = io.read_regular(source_repository/d['snapshotRelativePath']/'manifest.json')
    result = evidence.bind_originals(bound, ordinal, originals, receipt_raw, manifest_raw, schema_raw,
        context_raw, source_repository=source_repository)
    evidence.verify_complete(result)
    return result
