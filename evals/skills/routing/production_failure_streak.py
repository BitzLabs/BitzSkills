"""同じ型の評価失敗の連続を検出する（ADR-068 D4）。モデル起動・予約・台帳の書込みはしない。"""
import argparse
from pathlib import Path
import re
import sys
import tarfile

import production_ledger as io
import production_trace as trace

require = trace.require
VERSION = 'evaluation-failure-streak-0.1.0'
ACKNOWLEDGEMENT_VERSION = 'evaluation-failure-acknowledgement-0.1.0'
LIMIT = 2
SLOT_NAME = re.compile(r'actual-slot-([0-9]{4})\.json')
MAX_RECORD_BYTES = 1024*1024


def survey_signature(record):
    """公開調査の枠記録。正常な測定はNone、評価失敗は段階と例外の型を返す。"""
    require(isinstance(record, dict) and type(record.get('ordinal')) is int, 'failure streak slot record')
    if record.get('status') != 'evaluation_failed':
        return None
    phase = record.get('failurePhase')
    require(phase in {'primary', 'independent', 'parent'}, 'failure streak phase')
    stage = record.get(phase) if isinstance(record.get(phase), dict) else {}
    return (phase, stage.get('status'), stage.get('errorType'), stage.get('timedOut'))


def ledger_signature(row):
    """保持台帳の終端event。parent_verifiedはNone、評価失敗は段階を返す。終端以外は対象外。"""
    stage = row['stage']
    if stage == 'parent_verified':
        return None
    require(stage in {'primary_failed', 'independent_failed'}, 'failure streak terminal stage')
    return (stage,)


def trailing(items):
    """(ordinal, signature)の列の末尾で、同じsignatureの評価失敗が続く範囲を返す。"""
    run = []
    for ordinal, signature in items:
        if signature is None or (run and run[-1][1] != signature):
            run = []
        if signature is not None:
            run.append((ordinal, signature))
    return dict(ordinals=[ordinal for ordinal, _ in run], signature=list(run[-1][1]) if run else None)


def ledger_terminals(rows):
    return [(row['ordinal'], ledger_signature(row)) for row in rows
        if row['stage'] in {'parent_verified', 'primary_failed', 'independent_failed'}]


def acknowledgement(raw, streak, next_ordinal):
    """連続失敗の後に続けるための確認記録を検査する。中身の妥当性は人が判断する。"""
    value = trace.strict_json(raw)
    require(isinstance(value, dict) and set(value) == {'version', 'nextOrdinal', 'failedOrdinals',
        'signature', 'decision', 'reason'}, 'failure acknowledgement inventory')
    require(value['version'] == ACKNOWLEDGEMENT_VERSION and value['nextOrdinal'] == next_ordinal
        and value['failedOrdinals'] == streak['ordinals'] and value['signature'] == streak['signature']
        and value['decision'] == 'continue' and isinstance(value['reason'], str)
        and 0 < len(value['reason'].strip()) <= 2000, 'failure acknowledgement binding')
    return value


def guard(items, next_ordinal, acknowledgement_raw=None):
    """直前LIMIT枠以上が同じ型で失敗していれば、確認記録なしに次の枠を始めさせない。"""
    streak = trailing(items)
    if len(streak['ordinals']) < LIMIT:
        return dict(version=VERSION, status='clear', streak=streak)
    require(acknowledgement_raw is not None,
        'consecutive identical evaluation failures; record the investigation before the next slot')
    acknowledgement(acknowledgement_raw, streak, next_ordinal)
    return dict(version=VERSION, status='acknowledged', streak=streak)


def survey_records(archive):
    """公開archiveのactual-slot記録だけを、展開せずに読む。"""
    records = {}
    with tarfile.open(archive, 'r:gz') as bundle:
        for member in bundle.getmembers():
            match = SLOT_NAME.fullmatch(member.name)
            if match is None:
                continue
            require(member.isfile() and 0 < member.size <= MAX_RECORD_BYTES, 'failure streak archive member')
            record = trace.strict_json(bundle.extractfile(member).read())
            require(record.get('ordinal') == int(match.group(1)) and record['ordinal'] not in records,
                'failure streak archive ordinal')
            records[record['ordinal']] = record
    require(records, 'failure streak archive has no slot records')
    return [records[n] for n in sorted(records)]


def summarize(records):
    items = [(record['ordinal'], survey_signature(record)) for record in records]
    streaks, current = [], []
    for ordinal, signature in [*items, (None, None)]:
        if current and (signature is None or signature != current[-1][1]):
            if len(current) >= LIMIT:
                streaks.append(dict(first=current[0][0], last=current[-1][0], length=len(current),
                    signature=list(current[0][1]),
                    cases=sorted({r['caseId'] for r in records if current[0][0] <= r['ordinal'] <= current[-1][0]})))
            current = []
        if signature is not None:
            current.append((ordinal, signature))
    measured = {r['caseId'] for r in records if r.get('eligibleForMeasurement') is True}
    counts = {}
    for record in records:
        counts[record['status']] = counts.get(record['status'], 0)+1
    return dict(version=VERSION, slots=len(records), firstOrdinal=records[0]['ordinal'],
        lastOrdinal=records[-1]['ordinal'], statusCounts=dict(sorted(counts.items())), streaks=streaks,
        casesWithoutMeasurement=sorted({r['caseId'] for r in records} - measured),
        modelsExecuted=0, certifiesSkillGate=False)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    args = parser.parse_args(argv)
    sys.stdout.write(io.encoded(summarize(survey_records(args.archive))).decode() + '\n')


if __name__ == '__main__':
    main()
