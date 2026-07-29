# テスト仕様書: トレース参照判定の正確化

sdd-test 工程で SDD-FR-146 / SDD-FR-147 / SDD-FR-148 の EARS 要件から導出した検証仕様。

- 実行日: 2026-07-29
- 対象リビジョン: base HEAD `fbb7cef` + working tree
- 最終実行コマンド: `.venv/bin/pytest -q` /
  `python3 plugins/bitz-sdd/skills/sdd-core/scripts/spec_inspect.py --workspace . plugins/* --check-only` /
  `python3 scripts/release_check.py`
- 最終結果: pytest **382 passed** / ローカル spec_inspect check-only **全7ワークスペース PASS** /
  release_check **PASS**

> 注: 本リポジトリは bitz-sdd をインストール済みプラグインとして消費するため、
> `scripts/spec inspect` はプラグインキャッシュ側の版へ委譲する。作業ツリーの変更を
> 検証するときは `plugins/bitz-sdd/skills/sdd-core/scripts/spec_inspect.py` を直接実行する。

## テスト仕様: SDD-FR-146 canonical実行時のworkspace横断テスト参照集約

- **対象要件**: SDD-FR-146
- **導出元種別**: Event-Driven（WHEN 節4つ）+ State-Driven（WHILE 節1つ）
- **Verification Method**: unit-test
- **テストケース一覧**:
  - `test_SDD_FR_146_root_test_reference_resolves_plugin_requirement`
    — ルート `tests/` がプラグイン要件を参照する fixture で未参照が解消し、
      参照元が `root/tests/test_plugin_feature.py` と識別できること（WHEN 節1・3）
  - `test_SDD_FR_146_single_workspace_inspection_is_unchanged`
    — 同じ配置でも単一ワークスペース検査では集約せず未参照のまま（WHEN 節2）
  - `test_SDD_FR_146_unreferenced_requirement_still_reported`
    — どこからも参照されない要件は集約後も未参照として残る（WHEN 節4）
  - `test_SDD_FR_146_aggregation_keeps_ghost_detection_and_exit_code`
    — 集約が幽霊参照検出と終了コード1を変えないこと（WHILE 節）
- **red 記録**: 実装前は集約と外部参照セクションが存在せず、対象2件が FAIL。
- **green 記録**: 実装後4件 green。

## テスト仕様: SDD-FR-147 実装コードディレクトリの参照走査対象拡張

- **対象要件**: SDD-FR-147（version 1.1）
- **導出元種別**: Event-Driven（WHEN 節3つ）+ State-Driven（WHILE 節1つ）+ Optional（WHERE 節1つ）
- **Verification Method**: unit-test
- **テストケース一覧**:
  - `test_SDD_FR_147_implementation_script_reference_resolves`
    — `skills/<name>/scripts/` のコードによる参照で未参照が解消（WHEN 節1）
  - `test_SDD_FR_147_markdown_in_scripts_dir_is_not_implementation_reference`
    — 追加走査対象の Markdown は実装参照として数えない（WHEN 節2）
  - `test_SDD_FR_147_example_id_in_implementation_code_is_not_ghost`
    — docstring の使用例 ID を幽霊参照にしない（WHEN 節3。v1.1 で改訂された節）
  - `test_SDD_FR_147_ghost_detection_in_existing_subdirs_unchanged`
    — 従来の走査対象での幽霊参照検出は不変（WHILE 節）
  - `test_SDD_FR_147_workspace_without_extra_dirs_is_unchanged`
    — 追加ディレクトリを持たないワークスペースの結果は従来どおり（WHERE 節）
- **red 記録**: 実装前は `test_SDD_FR_147_implementation_script_reference_resolves` が FAIL。
- **実装中の red**: 走査対象を幽霊参照判定にも使った初版では、実リポジトリの
  canonical 実行が3件の誤検知で FAIL（`commit_lint.py` のコミットメッセージ例に含まれる
  タスク ID、`spec_scaffold.py` の使用例のタスク ID、`spec_inspect.py` の `--impact`
  使用例の要件 ID。具体的な ID は本ファイルへ書くと同じ誤検知を招くため
  `.spec/reports/decision-2026-07-29-si-sdd-014.md` を参照）。人間裁定を経て要件を
  1.1 へ改訂し、追加走査対象を未参照判定専用にして解消した。
- **green 記録**: 実装後5件 green。

## テスト仕様: SDD-FR-148 manual-check要件の未参照報告分離

- **対象要件**: SDD-FR-148
- **導出元種別**: Event-Driven（WHEN 節3つ）+ State-Driven（WHILE 節1つ）
- **Verification Method**: unit-test
- **テストケース一覧**:
  - `test_SDD_FR_148_manual_check_requirement_is_listed_separately`
    — manual-check 要件が自動検証側に現れず、専用見出しと注記へ列挙される（WHEN 節2・3）
  - `test_SDD_FR_148_automated_requirement_stays_in_original_section`
    — 自動検証要件は従来の見出しへ列挙される（WHEN 節1）
  - `test_SDD_FR_148_separation_does_not_change_exit_code`
    — 分離報告が終了コードを変えない（WHILE 節）
- **red 記録**: 実装前は専用見出しが存在せず、対象2件が FAIL。
- **green 記録**: 実装後3件 green。

## 実リポジトリでの効果（canonical 実行）

| ワークスペース | 変更前 未参照 | 変更後 自動未参照 | manual-check 別掲 | 外部参照で解消 |
|---|---|---|---|---|
| BitzSkills（root） | 20 | 8 | 11 | 0 |
| bitz-sdd | 54 | 11 | 29 | 4 |
| bitz-env | 19 | 7 | 7 | 5 |
| bitz-flow | 2 | 0 | 1 | 0 |
| bitz-ddd | 2 | 0 | 2 | 0 |
| plugin-creator / skill-creator | 0 | 0 | 0 | 0 |
| **合計** | **97** | **26** | **50** | **9** |

判定は変更前後ともに全7ワークスペース PASS。本変更は未参照の報告内容だけを変え、
問題・幽霊参照・孤児要件による PASS / FAIL 判定には影響しない。

SI-SDD-014 が起票の契機とした FLW-FR-001 は、`skills/flow-pr/scripts/branch_preflight.py`
からの実装参照が拾われるようになり未参照から外れた。FLW-FR-002 は
`verification_method: manual-check` のため manual-check 別掲へ移った。

## 変更前実装に対する negative control

新規12件を変更前の `spec_inspect.py` に対して実行し、5件が FAIL することを確認した
（新機能を直接検証しているケースが確かに red になる）。残る7件は境界・回帰の確認であり、
変更前後どちらでも green である。
