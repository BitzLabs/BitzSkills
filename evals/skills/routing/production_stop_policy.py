"""評価の停止の区分と再試行の承認（ADR-068 D1、D2）。台帳の書込み・モデル起動はしない。"""
import production_ledger as io
import production_trace as trace

require = trace.require
AUTHORIZATION_VERSION = 'evaluation-retry-authorization-0.1.0'
SAFETY = frozenset({'unsafe'})
EVIDENCE = frozenset({'evidence_invalid', 'independent_rejected', 'unknown_event'})
HARNESS = frozenset({'source_drift', 'resource_drift', 'provider_drift', 'quota_exhausted',
    'auth_unavailable', 'storage_failure', 'operator_interrupted'})
REASONS = SAFETY | EVIDENCE | HARNESS
FAILURE_ROLES = frozenset({'primary', 'independent', 'interrupted'})


class HarnessFault(ValueError):
    """評価対象と無関係な評価環境の障害。区分できる箇所だけで送出する。"""
    def __init__(self, reason, message):
        require(reason in HARNESS, 'harness fault reason')
        super().__init__(message)
        self.reason = reason


def classify(reason):
    require(isinstance(reason, str) and reason in REASONS, 'stop reason')
    return 'safety' if reason in SAFETY else 'evidence' if reason in EVIDENCE else 'harness'


def stop_reason(error):
    """例外から停止理由を決める。区分できない例外は原記録を信用しない扱いにする。"""
    if isinstance(error, HarnessFault):
        return error.reason
    return 'evidence_invalid' if isinstance(error, Exception) else 'operator_interrupted'


def authorization(raw, *, contract_sha256, ordinal):
    """再試行の承認記録を検査する。safetyは再試行せず、evidenceは独立検分の記録を要する。"""
    value = trace.strict_json(raw)
    require(isinstance(value, dict) and set(value) == {'version', 'contractSha256', 'ordinal', 'failedRole',
        'stopReason', 'causeClass', 'priorArtifactSha256', 'evidenceSha256', 'independentReviewSha256',
        'reason', 'automaticRetry'}, 'retry authorization inventory')
    require(value['version'] == AUTHORIZATION_VERSION and value['contractSha256'] == contract_sha256
        and type(value['ordinal']) is int and value['ordinal'] == ordinal
        and value['failedRole'] in FAILURE_ROLES and value['automaticRetry'] is False,
        'retry authorization identity')
    cause = classify(value['stopReason'])
    require(cause != 'safety' and value['causeClass'] == cause, 'retry authorization cause class')
    io.pin(value['priorArtifactSha256'])
    require(isinstance(value['evidenceSha256'], list) and 1 <= len(value['evidenceSha256']) <= 32
        and len(set(value['evidenceSha256'])) == len(value['evidenceSha256']), 'retry authorization evidence')
    for item in value['evidenceSha256']:
        io.pin(item)
    if cause == 'evidence' or value['independentReviewSha256'] is not None:
        io.pin(value['independentReviewSha256'])
    require(isinstance(value['reason'], str) and 0 < len(value['reason'].strip()) <= 2000,
        'retry authorization reason')
    return value
