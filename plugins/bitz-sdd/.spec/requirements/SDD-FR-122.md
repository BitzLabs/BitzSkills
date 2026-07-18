---
id: SDD-FR-122
version: 1.0
status: verified
domain: execution
priority: high
origin: SI-SDD-007
verification_method: manual-check
derived_from:
supersedes:
superseded_by:
confidence: high
---

### SDD-FR-122 accepted spec-issue 着手時の起票時前提再検証

- **説明**: accepted のまま保留されていた spec-issue を実装へ移す際、起票時に前提とした
  対象ファイル・件数・書式などが現状と一致するかを、要件化およびタスク分解より前に
  再検証しなければならない。前提の乖離が提案の趣旨を変えない場合は現状に合わせて要件を
  補正して履歴を残し、趣旨自体を変える場合は実装せず人間の再裁定へ戻す。
- **受入基準 (EARS)**:
  - WHEN accepted の spec-issue を要件化または既存要件へ対応付ける THEN sdd-implement は spec-issue 本文が前提とする対象ファイル・件数・書式を現状と照合 SHALL
  - IF 起票時前提と現状の乖離が提案の趣旨を変えない場合 THEN sdd-implement は現状に合わせて要件を補正し、要件の Revision History に乖離内容と補正理由を記録 SHALL
  - IF 起票時前提と現状の乖離が提案の趣旨自体を変える場合 THEN sdd-implement は要件化および実装を開始せず、spec-issue を人間の再裁定へ戻すよう提示 SHALL
- **検証手段**: sdd-implement の SKILL.md に起票時前提の再検証手順と2つの乖離分岐が
  明記され、skill-validator チェックリスト、release_check、spec inspect がすべて PASS することを
  目視および機械検証で確認する。
- **Revision History**:
  - 1.0 (2026-07-18) 初版（draft 起票）
  - 1.0 (2026-07-18) SI-SDD-007 の起票時前提を再検証。対象の
    `skills/sdd-implement/SKILL.md` は現存し、前提再検証ステップは未実装のため提案趣旨に乖離なし。
    配布マニフェストは起票本文の想定どおり3ファイルで、いずれも version 1.11.2。
