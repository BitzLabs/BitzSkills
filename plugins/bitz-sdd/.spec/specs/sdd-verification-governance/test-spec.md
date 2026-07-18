# テスト仕様書: 軽量レーン検証証跡と unit-test 統制語彙

sdd-test 工程で SDD-FR-123 / SDD-FR-124 の EARS 要件から導出した検証仕様。

- 実行日: 2026-07-18
- 対象リビジョン: base HEAD `9407e3d` + working tree
- 最終実行コマンド: `.venv/bin/pytest` / `python3 scripts/release_check.py` /
  `python3 scripts/spec inspect --workspace . plugins/*`
- 最終結果: pytest **167 passed** / release_check **PASS** /
  spec inspect **全7ワークスペース PASS**

## テスト仕様: SDD-FR-123 軽量レーンの検証証跡基準

- **対象要件**: SDD-FR-123
- **導出元種別**: Event-Driven + Unwanted Behavior + Optional
- **Verification Method**: manual-check
- **検証項目と結果**:
  - lifecycle.md が STATE.md を判定の正本とし、対象リビジョン・秘匿情報を除いたコマンド・
    期待件数・成功失敗スキップ件数・終了コード・機械チェック結果・実行日を必須化 ✅
  - 失敗・中断・結果欠落・期待件数不一致・未許容スキップ時の verified 拒否を明記 ✅
  - PR の有無、STATE.md との不一致、verified 後の再照合、秘密値のプレースホルダー化を明記 ✅
  - 通常フローの `.spec/specs/` 記録継続と既存 verified 要件への非遡及を明記 ✅
  - sdd-test 0.1.2 に同じ必須証跡チェックリストを実装 ✅

## テスト仕様: SDD-FR-124 unit-test 検証手段の統制語彙追加

- **対象要件**: SDD-FR-124
- **導出元種別**: Event-Driven + State-Driven
- **Verification Method**: example-test
- **テストケース一覧**:
  - `test_SDD_FR_124_unit_test_verification_method_succeeds`
  - `test_SDD_FR_124_active_requirement_accepts_unit_test`
- **red 記録**: 実装前は2件とも FAIL。scaffold は exit 2 で語彙外、inspect は
  frontmatter 問題1件・exit 1で語彙外と判定。
- **green 記録**: `VMETHODS` 追加後の対象実行は **2 passed in 0.20s**、最終全体実行は
  **167 passed in 2.65s**。
- **後方互換**: 既存 `example-test` を含む全 pytest と全ワークスペース inspect が PASS ✅
- **バージョン**: sdd-core 1.13.3 / sdd-test 0.1.2 / bitz-sdd 1.11.4（3マニフェスト同値）✅

## Design Review / Skill Validation

- SDD-REV-001: consistency 5.00 / operations 4.20 / risk 4.33 / business 4.70、
  正規化総合 4.50、critical 0 / major 0、統合判定 **PASS**。
- skill-validator（sdd-core / sdd-test）:
  - A: SKILL.md・YAML frontmatter・標準ディレクトリ構成 ✅
  - B: name の文字数・文字種・フォルダ一致 ✅
  - C: description の長さ・責務・発動条件 ✅
  - D: 147行 / 67行（500行未満）、直接参照実在、クロススキル連携はスキル名を明記 ✅
  - E: 単一責務・安全確認・記述スタイルに新規懸念なし ✅
  - F: semver / author / created / updated、installed-* 混入なし ✅

- **検証ステータス**: green
