---
id: ENV-CON-002
version: 1.0
status: approved
domain: collab
priority: medium
origin: 製作プラン（契約の先行固定リスクへの対処）
verification_method: manual-check
derived_from:
supersedes:
superseded_by:
confidence: high
---

### ENV-CON-002 アダプタ契約の後方互換拡張

- **説明**: 協調アダプタ契約（collab-contract.md）は公開契約であり、拡張は後方互換で
  行う（既存フィールドの意味を変えない・必須項目を後から増やさない）。
  破壊的な変更が避けられない場合は契約バージョンを上げ、旧バージョンの
  アダプタを非準拠として扱わない移行期間を設ける。
- **受入基準 (EARS)**:
  - WHEN collab-contract.md を変更する THEN 既存の準拠アダプタが非準拠に ならないことを確認 SHALL
  - IF 破壊的変更が必要 THEN 契約バージョンを更新し移行方針を契約に明記 SHALL
- **検証手段**: コードレビュー（PR。契約変更は Design Gate 対象・軽量レーン禁止）
- **Revision History**:
  - 1.0 (2026-07-11) 初版
  - 1.0 (2026-07-11) 人間裁定により approved 化（チャット指示）
