"""一次カナリアの原通知・host・最終応答の相関。独立採点・台帳確定は別工程。"""
from __future__ import annotations
import production_canary_evidence as evidence
import production_canary_trace as canary
import production_sdk_trace as sdk
import production_trace as trace
import production_primary_review as primary
require=trace.require
json_lines=primary.json_lines
raw_projection=primary.raw_projection


def verify_native(capture):
    require(isinstance(capture,evidence.VerifiedCapture),'verified capture context required')
    originals,fixed=capture.originals,capture.fixed
    require({name:evidence.ledger.sha(raw) for name,raw in originals.items()}==capture.result['artifactSha256'],
            'consumed original artifact binding drift')
    result=primary.native(originals,fixed.bound.raw_inputs[2],fixed.bound.raw_inputs[1],fixed.decision_schema_raw,cwd=str(capture.base/'work'))
    return dict(status='primary_native_and_host_correlated',artifactBinding=capture.result,**result,
        rawPayloadCorrelationVerified=False,eligibleForMeasurement=False,certifiesProviderWireBodies=False,
        certifiesBehavior=False,certifiesSkillGate=False,independentReviewPerformed=False,ledgerFinalized=False)


def verify_complete(capture):
    result=verify_native(capture)
    require(evidence.ledger.sha(capture.fixed.context_profile_raw)==capture.fixed.bound.contract['contextProfileSha256'],
            'consumed fixed context profile drift')
    correlated=primary.correlate_rollout(capture.originals,result['native'],capture.fixed.context_profile_raw,
        evidence.read_original(capture.base/'receipt.json'),capture.result.get('receiptSha256'),capture.result.get('captureElapsedSeconds'))
    return dict(result,status='primary_original_capture_correlated',rollout=correlated,
        rawPayloadCorrelationVerified=True,eligibleForMeasurement=False,independentReviewPerformed=False,ledgerFinalized=False)
