"""一次実行の固定Node/CLI資源を照合する。認証・ユーザー設定を読まない。"""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
import stat

import production_ledger as ledger
import production_trace as trace

ROOT = Path('/home/hide/BitzLabs/BitzSkills/.venv/skills-integration-worktree/.venv/fixed-codex-0.160.1')
MANIFEST = 'evals/skills/routing/production-canary-runtime-v0.1.json'
PACKAGE = 'lib/node_modules/@openai/codex/'
PLATFORM = PACKAGE+'node_modules/@openai/codex-linux-x64/'
VENDOR = PLATFORM+'vendor/x86_64-unknown-linux-musl/'
REQUIRED = {'bin/node', PACKAGE+'package.json', PACKAGE+'bin/codex.js', PLATFORM+'package.json',
    VENDOR+'codex-package.json', VENDOR+'bin/codex', VENDOR+'bin/codex-code-mode-host',
    VENDOR+'codex-path/rg', VENDOR+'codex-resources/bwrap'}
LINK = '../'+PACKAGE+'bin/codex.js'
require = trace.require


def specification(raw, contract):
    require(ledger.sha(raw) == ledger.pin(contract['runtimeManifestSha256']), 'fixed runtime manifest hash')
    value = trace.strict_json(raw)
    require(isinstance(value,dict) and set(value)=={'package','version','files','treeSha256'} and
        value['package']=='@openai/codex' and value['version']=='0.160.1' and isinstance(value['files'],dict) and
        REQUIRED <= set(value['files']) and len(value['files']) <= 128, 'fixed runtime inventory')
    for name,digest in value['files'].items():
        require(isinstance(name,str) and (name=='bin/node' or name.startswith(PACKAGE)) and
            all(p not in {'','..','.'} for p in name.split('/')) and '\\' not in name and
            not any(p in {'.env','auth.json','.credentials.json'} for p in name.split('/')), 'unknown runtime path')
        ledger.pin(digest)
    # 原inventoryのtreeShaはファイル集合を順序・パス込みで表す。
    ledger.pin(value['treeSha256'])
    require(contract['codexPath']==str(ROOT/'bin/codex'), 'fixed runtime entry path')
    return value


def file_hash(path):
    """親からNOFOLLOWで開く。既知の配布runtimeのhardlinkは許容し全bytesをhashする。"""
    parts = path.parts[1:]
    fd = os.open('/',os.O_RDONLY|os.O_DIRECTORY)
    try:
        for name in parts[:-1]:
            child=os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
            os.close(fd);fd=child
        child=os.open(parts[-1],os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=fd)
        try:
            require(stat.S_ISREG(os.fstat(child).st_mode),'regular runtime file required')
            digest=hashlib.sha256()
            while block:=os.read(child,1024*1024):digest.update(block)
            return digest.hexdigest()
        finally:os.close(child)
    finally:os.close(fd)


def verify(raw, contract):
    value=specification(raw,contract)
    ledger.safe_tree(ROOT)
    expected=set(value['files'])|{'bin/codex'}
    directories={ROOT}
    for name in expected:
        path=ROOT/name
        directories.update(p for p in path.parents if p==ROOT or p.is_relative_to(ROOT))
    actual=set()
    # 既知のディレクトリにだけ降り、未知名は内容を開く前に拒否する。
    for directory in sorted(directories):
        require(directory.is_dir() and not directory.is_symlink(),'runtime directory shape')
        for child in directory.iterdir():
            if child in directories:
                require(not child.is_symlink(),'runtime parent symlink')
            else:
                name=str(child.relative_to(ROOT))
                require(name in expected,'unknown runtime inventory member')
                actual.add(name)
    require(actual==expected,'runtime inventory missing')
    require((ROOT/'bin/codex').is_symlink() and os.readlink(ROOT/'bin/codex')==LINK,'fixed packaged CLI symlink')
    for name,digest in value['files'].items():
        require(file_hash(ROOT/name)==digest,'fixed runtime bytes drift')
    return dict(status='fixed_runtime_bytes_match',runtimeManifestSha256=ledger.sha(raw),
                codexPath=contract['codexPath'],files=len(value['files']))
