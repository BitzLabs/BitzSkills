"""可変ID・一次独立予約の原試験と原SOL結果を照合する。新モデル/一次起動0。"""
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'evals/skills/routing'))
import production_trace as trace


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def run():
    public = trace.strict_json((Path(__file__).parent / 'summary.json').read_bytes())
    review = module('raw_review_record', 'evals/skills/results/2026-10-09-sdk-raw-response-capture/verify-recorded-results.py')
    preparation = module('design_preparation_record', 'evals/skills/results/2026-10-10-production-canary-design/verify-recorded-results.py')
    stages = [public['originalStage'], *public.get('remediationStages', [])]
    counts = [preparation.check_stage(stage, review) for stage in stages]
    trace.require(public['independentSolInvocations'] == len(stages) and
                  all(public[key] == 0 for key in ['primaryModelTrajectories', 'automaticRetries', 'delegations']) and
                  public['eligibleForMeasurement'] is public['phaseComplete'] is False, 'finite diagnostic scope')
    print(json.dumps(dict(status='recorded_canary_trace_matches_original_bytes', tests=counts[-1],
                         originalTests=counts[0], independentSolInvocations=len(stages),
                         originalFindings=stages[0]['independentReview']['findings'],
                         latestFindings=stages[-1]['independentReview']['findings'],
                         primaryModelTrajectories=0, eligibleForMeasurement=False), ensure_ascii=False))


if __name__ == '__main__':
    run()
