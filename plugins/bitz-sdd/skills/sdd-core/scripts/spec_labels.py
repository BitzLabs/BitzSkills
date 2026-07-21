#!/usr/bin/env python3
"""spec_labels.py — BitzSDD ライフサイクル語彙の対訳辞書（SSOT・stdlib のみ）

SI-CORE-018 の裁定により、frontmatter の機械値は英語のまま維持し、表示層だけを
日本語化する。本ファイルがリポジトリ内の対訳の唯一の正（SSOT）である（SDD-FR-137）。

**このファイルは sdd-core と sdd-report の2箇所に同内容で存在する。**
AGENTS.md のスキル自己完結原則（他スキルのファイルを相対パスで参照しない）により
sdd-report は import せず複製を持つ。両者の一致は scripts/release_check.py が
機械検証するため、**片方だけを編集しないこと**。

併記の語順は種別で異なる（SI-CORE-018）:
  - status … 日本語主（`採用（accepted）`）。frontmatter の内部値でしかないため
  - フェーズ … 英語主（`Execute（実装）`）。工程名＝固有名詞として文書横断で通用するため
"""

# 種別ごとの status 対訳（機械値 → 日本語）。
# 集合は spec_update.py の権限マトリクス TRANSITIONS に現れる status と一致させる。
STATUS_LABELS_JA = {
    "requirement": {
        "draft": "起草中",
        "approved": "承認済み",
        "implementing": "実装中",
        "verified": "検証済み",
        "promoted": "確定",
        "deprecated": "廃止",
    },
    "spec-issue": {
        "open": "裁定待ち",
        "accepted": "採用",
        "rejected": "不採用",
        "superseded": "統合済み",
    },
    "task": {
        "pending": "着手待ち",
        "implementing": "実装中",
        "blocked": "介入待ち",
        "done": "完了",
    },
}

# フェーズ対訳（機械値 → 日本語）。spec_status.py の PHASE_CODES と1対1で対応する。
PHASE_LABELS_JA = {
    "map": "未着手",
    "discovery": "企画",
    "design": "設計",
    "plan": "要件定義",
    "execute": "実装",
    "verify": "検証",
    "done": "確定待ち",
}

# 人間裁定点（ゲート）待ちであることを表示に明示するフェーズ。
# done は「全検証 green だが Promotion Gate 未通過」であり、訳語だけでは
# 裁定が残っていることが伝わらないため Gate 名を合成する（SDD-FR-136）。
PHASE_GATE_HINTS = {
    "done": "Promotion Gate",
}


def status_label(kind: str, status: str) -> str:
    """status の機械値を日本語主の併記形にする。未知語は機械値のまま返す。"""
    ja = STATUS_LABELS_JA.get(kind, {}).get(status)
    return f"{ja}（{status}）" if ja else status


def phase_label(phase_code: str) -> str:
    """phase_code を英語主の併記形にする。ゲート待ちのフェーズは Gate 名を併記する。"""
    ja = PHASE_LABELS_JA.get(phase_code)
    if not ja:
        return phase_code
    hint = PHASE_GATE_HINTS.get(phase_code)
    return f"{phase_code.capitalize()}（{ja}: {hint}）" if hint else f"{phase_code.capitalize()}（{ja}）"


def normalize_status(kind: str, value: str) -> str:
    """日本語ラベルを機械値へ正規化する（SDD-FR-138）。

    受理するのは機械値と純粋な日本語ラベルの2種のみで、併記形は受理しない。
    未知語はそのまま返し、呼び出し側の権限マトリクス照合で不正遷移として弾かせる
    （ここでエラーにすると「不正遷移」と「未知語」でエラー経路が二重化するため）。
    """
    table = STATUS_LABELS_JA.get(kind, {})
    if value in table:
        return value
    for machine, ja in table.items():
        if value == ja:
            return machine
    return value
