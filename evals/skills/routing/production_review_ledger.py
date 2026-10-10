"""静的検分の有限1枠をrepository共通で予約する。予約後停止も返金しない。"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import stat

import production_ledger as primary
from production_trace import require, strict_json


class StaticReviewLedger:
    """storage引数は隔離試験用。製品起動はreserve_static_reviewだけを使う。"""
    def __init__(self, storage: Path):
        self.storage = storage
        primary.safe_tree(storage)
        try:
            storage.mkdir(mode=0o700)
        except FileExistsError:
            pass
        info = storage.stat()
        require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid() and
                stat.S_IMODE(info.st_mode) == 0o700, 'static ledger directory ownership or mode')

    def reserve(self, contract_name: str, source: str, contract_raw: bytes):
        require(isinstance(contract_name, str) and
                re.fullmatch(r'evals/skills/routing/sdk-(?:trace|raw-response)-review-v0\.[0-9]+\.json', contract_name),
                'static contract identity')
        require(isinstance(source, str) and re.fullmatch(r'[0-9a-f]{40}', source), 'static source ref')
        contract = strict_json(contract_raw)
        require(type(contract['maximumInvocations']) is int and contract['maximumInvocations'] == 1 and
                type(contract['automaticRetries']) is int and contract['automaticRetries'] == 0 and
                type(contract['primaryModelTrajectories']) is int and contract['primaryModelTrajectories'] == 0 and
                contract['model'] == 'gpt-6.1-sol', 'finite static reservation')
        primary.safe_tree(self.storage)
        path = self.storage / (Path(contract_name).stem + '.json')
        value = dict(contractPath=contract_name, sourceCommit=source,
                     contractSha256=hashlib.sha256(contract_raw).hexdigest(),
                     maximumInvocations=1, consumedReservations=1, automaticRetry=False,
                     primaryModelTrajectories=0, model=contract['model'])
        # contract pathがidentity。source/output/worktreeを変えても同じ予約を作れない。
        primary.exclusive(path, primary.encoded(value))
        return dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest(), **value)


def reserve_static_review(repository: Path, contract_name: str, source: str, contract_raw: bytes):
    storage = primary.common_ledger_path(repository).parent / 'production-routing-static-review-ledger'
    return StaticReviewLedger(storage).reserve(contract_name, source, contract_raw)
