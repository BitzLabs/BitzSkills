# テスト仕様書: accepted spec-issue 着手時の起票時前提再検証

sdd-test 工程で SDD-FR-122 の EARS 要件から導出した manual-check 検証仕様。

- 実行日: 2026-07-18
- 実行コマンド: `python3 scripts/release_check.py` /
  `.venv/bin/pytest` / `python3 scripts/spec inspect --workspace . plugins/*`
- 最終結果: release_check **PASS** / pytest **165 passed** /
  spec inspect 全ワークスペース **PASS**

## テスト仕様: SDD-FR-122 accepted spec-issue 着手時の起票時前提再検証

- **対象要件**: SDD-FR-122
- **EARS 節**:
  - WHEN accepted の spec-issue を要件化または既存要件へ対応付ける THEN 対象ファイル・件数・書式を現状と照合 SHALL
  - IF 乖離が提案の趣旨を変えない場合 THEN 現状に合わせて要件を補正し Revision History に理由を記録 SHALL
  - IF 乖離が提案の趣旨自体を変える場合 THEN 要件化・実装を開始せず人間の再裁定へ戻すよう提示 SHALL
- **導出元種別**: Event-Driven + Unwanted Behavior
- **Verification Method**: manual-check
- **検証項目と結果**:
  - `sdd-implement/SKILL.md` の実行手順先頭に、要件化・既存要件への対応付けより前の照合を明記 ✅
  - 趣旨を変えない乖離について、要件補正と Revision History への記録を明記 ✅
  - 趣旨自体を変える乖離について、実装中止と人間の再裁定を明記 ✅
  - skill-validator チェックリスト A〜F: 全項目 PASS（46行、相対参照3件はすべて実在、metadata 0.2.2）✅
  - bitz-sdd の3マニフェスト: version 1.11.3 で一致 ✅
  - release_check: 全チェック合格 ✅
  - pytest: 165 passed in 2.72s ✅
  - spec inspect: 問題0・幽霊参照0・孤児要件0、全ワークスペース PASS ✅
- **検証ステータス**: green
