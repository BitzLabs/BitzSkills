# テスト仕様書: Discovery成果物の同期マッピング

sdd-test 工程で SDD-FR-149 / SDD-FR-150 の EARS 要件から導出した検証仕様。

- 実行日: 2026-07-29
- 対象リビジョン: base HEAD `4c5d6e0` + working tree
- 最終実行コマンド: `.venv/bin/pytest -q` / `python3 scripts/release_check.py` /
  `python3 plugins/bitz-sdd/skills/sdd-core/scripts/spec_inspect.py --workspace . plugins/* --check-only`
- 最終結果: 下段「実行結果」を参照

> 注: 本リポジトリは bitz-sdd をインストール済みプラグインとして消費するため、
> `scripts/spec inspect` はプラグインキャッシュ側の版へ委譲する。作業ツリーの変更を
> 検証するときは `plugins/bitz-sdd/skills/sdd-core/scripts/spec_inspect.py` を直接実行する。

## テスト仕様: SDD-FR-149 Discovery成果物のdocs同期マッピング網羅

- **対象要件**: SDD-FR-149
- **導出元種別**: Event-Driven（WHEN 節8つ）+ Unwanted Behavior（IF 節2つ）
- **Verification Method**: unit-test
- **テストケース一覧**:
  - `test_pull_uses_japanese_mapping`（パラメタライズを Discovery 6対 + 設計4対へ拡張）
    — 各同期元が対応する docs 文書へ本文だけ展開され、docs の frontmatter が保たれること
      （WHEN 節1〜4。既存の vision / scope と設計マッピングは回帰確認）
  - `test_SDD_FR_149_push_reverse_syncs_discovery_document`（Discovery 6対）
    — docs 側の手直しが単一の `.spec/discovery/` 文書へ逆反映され、
      `.spec` の frontmatter が保たれること（WHEN 節6。1:1 契約の実証）
  - `test_SDD_FR_149_constraints_and_scope_sync_independently`
    — 制約.md と 対象外.md がそれぞれ独立した同期元から展開され、互いを上書きしないこと（WHEN 節5）
  - `test_SDD_FR_149_pull_skips_missing_discovery_sources_without_failing`
    — 未作成の成果物は SKIP と報告され、失敗0件で他の同期が完了すること（IF 節1）
  - `test_SDD_FR_149_push_skips_missing_docs_targets_without_failing`
    — docs 側が未作成のマッピングは SKIP され、他の逆反映を妨げないこと（IF 節2）
  - `test_SDD_FR_149_diff_reports_every_discovery_mapping`
    — diff が Discovery 6対すべてを報告し、`.spec/` も `docs/` も作らないこと（WHEN 節9）
  - `test_SDD_FR_149_pull_all_discovery_then_docs_inspect_strict_passes`
    — 6成果物を pull した直後の docs が `docs_inspect.py --strict` を通ること（WHEN 節10）
- **red 記録**: 変更前の `sdd_sync.py` に対して 12 件が FAIL（新規4マッピングの pull / push
  各4件、SKIP・diff・独立展開の各1件）。
- **green 記録**: 実装後 39 件 green（既存 27 件の回帰を含む）。

## テスト仕様: SDD-FR-150 同期マッピングSSOTと文書側同期表の一致検証

- **対象要件**: SDD-FR-150
- **導出元種別**: Event-Driven（WHEN 節3つ）+ Unwanted Behavior（IF 節5つ）
- **Verification Method**: unit-test
- **テストケース一覧**:
  - `test_sync_mapping_pass`
    — マーカー・可読表・`DEFAULT_MAPPING` の三者一致で両文書とも PASS（WHEN 節1）
  - `test_sync_mapping_marker_missing_pair` / `test_sync_mapping_marker_extra_pair`
    — マーカーの欠落・余剰をそれぞれ該当の対つきで FAIL（IF 節1）
  - `test_sync_mapping_marker_target_tampered`
    — 同期先だけを差し替えた改竄も不一致として検出（IF 節1）
  - `test_sync_mapping_visible_table_drift`
    — マーカーが正しくても可読表がドリフトしていれば FAIL（IF 節2）
  - `test_sync_mapping_marker_absent`
    — マーカーを持たない文書は FAIL（IF 節3）
  - `test_sync_mapping_discovery_scope_is_subset`
    — sdd-discovery のマーカーに設計マッピングが混ざれば余剰として FAIL（WHEN 節2）
  - `test_sync_mapping_rejects_one_to_many`
    — 複数の同期元が同じ docs 文書を指す 1:N 定義を FAIL（IF 節4。SDD-FR-149 の前提の保護）
  - `test_sync_mapping_additive_change_passes`
    — コードと2文書を同時更新した加算的変更は FAIL しない（WHEN 節3）
  - `test_sync_mapping_skipped_without_bitz_sdd`
    — bitz-sdd 不在のリポジトリでは SKIP し終了コードに影響しない（IF 節5）
- **red 記録**: 変更前の `release_check.py` に対して新規 10 件すべてが FAIL。
- **green 記録**: 実装後 36 件 green（既存 26 件の回帰を含む）。
- **備考**: フェーズ語彙検査の fixture（`_make_phase_repo`）にも整合した同期マッピング一式を
  seed した。検査を追加すると既存 fixture が巻き添えで FAIL するため、
  「bitz-sdd 相当の最小リポジトリ」の定義を更新している。

## 実行結果

| 検証 | 結果 |
|---|---|
| `.venv/bin/pytest -q` | 別掲（PR 本文に実出力） |
| `python3 scripts/release_check.py` | PASS（同期マッピング 1:1 性 + マーカー2文書） |
| ローカル `spec_inspect --workspace . plugins/* --check-only` | 全7ワークスペース PASS |

## 適用範囲外（裁定点3）

このリポジトリ自身の各ワークスペースの `scope.md` に同居している「制約」節は、
本 PR では `constraints.md` へ切り出さない。`constraints.md` 不在のワークスペースは
pull で SKIP されるだけで既存挙動は不変であり、切り出しは各プロジェクトの裁量とする
（裁定の根拠は `.spec/reports/decision-2026-07-29-si-sdd-011.md`）。
