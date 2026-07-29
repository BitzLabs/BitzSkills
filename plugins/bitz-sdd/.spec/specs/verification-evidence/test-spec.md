# テスト仕様書: 検証結果の機械可読証跡

sdd-test 工程で SDD-FR-151 / 152 / 153 / 154 の EARS 要件から導出した検証仕様。

- 実行日: 2026-07-29
- 対象リビジョン: base HEAD `6d04825` + working tree
- 最終実行コマンド: `.venv/bin/pytest -q` / `python3 scripts/release_check.py` /
  `python3 plugins/bitz-sdd/skills/sdd-core/scripts/spec_inspect.py --workspace . plugins/* --check-only`

> **本テスト仕様書の件数はナラティブである**（SDD-FR-151 の趣旨）。green 判定の正は
> `.spec/verification/` の証跡であり、本文の数値と食い違った場合は証跡が正。
> 再実行のたびに本文の数値を手で追随させる必要はない。

> 注: 本リポジトリは bitz-sdd をインストール済みプラグインとして消費するため、
> `scripts/spec inspect` はプラグインキャッシュ側の版へ委譲する。作業ツリーの変更を
> 検証するときは `plugins/bitz-sdd/skills/sdd-core/scripts/spec_inspect.py` を直接実行する。

## テスト仕様: SDD-FR-151 検証コマンド実出力からの機械可読証跡の記録

- **対象要件**: SDD-FR-151
- **導出元種別**: Event-Driven（WHEN 節5つ）+ Unwanted Behavior（IF 節3つ）
- **Verification Method**: unit-test
- **テストケース一覧**（`tests/test_spec_verify.py`）:
  - `test_SDD_FR_151_records_stable_fields_from_real_execution`
    — schema・command_id・command・commit・exit_code・requirements・recorded_at・tool が
      実行結果から記録される（WHEN 節1・2）
  - `test_SDD_FR_151_duration_is_isolated_in_observed`
    — 実行時間が `observed` 配下にだけ現れ、安定項目に混ざらない（WHEN 節3）
  - `test_SDD_FR_151_rerun_at_same_commit_overwrites_same_file`
    — 3回実行しても証跡ファイルが1件のままであること（WHEN 節4。冪等性）
  - `test_SDD_FR_151_parses_pytest_summary_counts`
    — pytest 要約行から passed / failed / skipped と duration を解析（WHEN 節5）
  - `test_SDD_FR_151_counts_are_null_without_a_recognized_summary`
    — 解析できないときに件数を捏造せず `null` にする（WHEN 節5の境界）
  - `test_SDD_FR_151_records_nonzero_exit_code`
    — 失敗した実行も隠さず記録する（WHEN 節1の境界）
  - `test_SDD_FR_151_multiple_requirements_are_deduplicated_and_sorted`
    — 対象要件が重複除去・安定順で記録される（冪等性の前提）
  - `test_SDD_FR_151_dirty_tree_is_rejected_without_opt_in` /
    `test_SDD_FR_151_dirty_tree_is_allowed_with_explicit_flag`
    — dirty 時の拒否と `--allow-dirty` 明示時の暫定記録（IF 節1）
  - `test_SDD_FR_151_rejects_workspace_without_git` — HEAD 未解決時の拒否（IF 節2）
  - `test_SDD_FR_151_rejects_malformed_requirement_id` /
    `test_SDD_FR_151_rejects_malformed_command_id`
    — 要件 ID・command-id の書式強制（IF 節3。command-id はファイル名になるため）
- **実装中の red**: 初版では証跡の書き込み自体が作業ツリーを dirty にし、2回目の記録が
  自分の1回目に拒否される自己ブロックが起きた（冪等性テストが検出）。証跡ディレクトリ配下の
  差分を dirty 判定から除外して解消した。また、ワークスペース配下の絶対パスを相対化すると
  実行ファイルが PATH 探索に落ちて起動できなくなったため、先頭要素だけ `./` を付ける。

## テスト仕様: SDD-FR-152 検証証跡における秘密値と環境固有情報の非保存

- **対象要件**: SDD-FR-152
- **導出元種別**: Event-Driven（WHEN 節4つ）+ Unwanted Behavior（IF 節2つ）
- **Verification Method**: unit-test
- **テストケース一覧**（`tests/test_spec_verify.py`）:
  - `test_SDD_FR_152_evidence_keys_are_limited_to_the_allow_list`
    — トップレベルキーが許可リストを超えない（WHEN 節1・2 の網羅的な担保）
  - `test_SDD_FR_152_raw_output_is_not_persisted`
    — **引数ではなく出力にだけ現れる**マーカーを使い、出力本文が証跡に残らないこと（WHEN 節1）
  - `test_SDD_FR_152_real_output_is_passed_through_to_the_caller`
    — 実出力は端末へそのまま流れる（WHEN 節4。保存しないことと隠すことを区別する）
  - `test_SDD_FR_152_rejects_secret_looking_arguments`（token / api-key / password / credential）
    — 秘密値らしき引数はコマンドを実行せず拒否（IF 節1）
  - `test_SDD_FR_152_rejects_home_absolute_paths` — ホーム絶対パスの拒否（IF 節2）
  - `test_SDD_FR_152_workspace_absolute_paths_are_relativized` — 相対化（WHEN 節3）
- **備考**: raw 出力の非保存は、当初「コマンド引数にマーカーを置く」形で書いたため
  常に FAIL した（引数は正当に記録される）。出力にだけ現れる値で検証する形へ改めた。

## テスト仕様: SDD-FR-153 検証証跡の構造検証と参照切れ検出

- **対象要件**: SDD-FR-153
- **導出元種別**: Unwanted Behavior（IF 節8つ）+ Event-Driven（WHEN 節2つ）
- **設計上の要点**: 「古い証跡」は HEAD との commit 一致では判定できない。証跡ファイルを
  コミットすると HEAD が進むため、証跡の commit が HEAD と一致することは原理的にありえない。
  そのため**記録時 commit 以降に証跡ディレクトリ以外が変更されたか**で判定する。
- **Verification Method**: unit-test
- **テストケース一覧**（`tests/test_spec_inspect.py`）:
  - `test_SDD_FR_153_workspace_without_evidence_dir_is_unchanged` — 無検査の維持（IF 節1）
  - `test_SDD_FR_153_valid_evidence_is_listed_and_passes` — 正常証跡の一覧化（WHEN 節1）
  - `test_SDD_FR_153_unreadable_evidence_fails` / `test_SDD_FR_153_unknown_schema_fails`
    — 読取不能・schema 不正の FAIL（IF 節2）
  - `test_SDD_FR_153_missing_required_key_fails` — 欠落キー名つき FAIL（IF 節3）
  - `test_SDD_FR_153_nonzero_exit_code_fails` — 失敗実行の FAIL（IF 節4）
  - `test_SDD_FR_153_failed_counts_fail` — 終了コード 0 でも failed 件数があれば FAIL（IF 節5）
  - `test_SDD_FR_153_dangling_requirement_reference_fails` — 参照切れの FAIL（IF 節6）
  - `test_SDD_FR_153_empty_requirements_fails` — 検証対象が空の証跡の FAIL
  - `test_SDD_FR_153_unresolvable_commit_is_warn_not_fail` /
    `test_SDD_FR_153_dirty_evidence_is_warn_not_fail`
    — 解決不能な commit・暫定証跡の WARN 化（IF 節7）
  - `test_SDD_FR_153_evidence_from_earlier_commit_is_current_when_only_evidence_changed`
    — 証跡をコミットしただけでは古い扱いにしない（WHEN 節2）
  - `test_SDD_FR_153_evidence_is_stale_when_source_changed_after_recording`
    — 記録後にソースが変わったら WARN（IF 節7）
  - `test_SDD_FR_153_verified_without_evidence_is_warn_not_fail` — 証跡欠落の WARN 化（IF 節8）
  - `test_SDD_FR_153_manual_check_requirement_needs_no_evidence` — manual-check の除外（IF 節8の例外）

## テスト仕様: SDD-FR-154 統合レポートへの検証証跡集計

- **対象要件**: SDD-FR-154
- **導出元種別**: Event-Driven（WHEN 節2つ）+ Unwanted Behavior（IF 節2つ）
- **Verification Method**: unit-test
- **テストケース一覧**（`tests/test_sdd_report.py`）:
  - `test_SDD_FR_154_section_absent_without_evidence_dir` — 証跡不在時に節を出さない（IF 節1）
  - `test_SDD_FR_154_evidence_rows_are_reported` — ファイル名・commit・終了コード・対象要件（WHEN 節1）
  - `test_SDD_FR_154_counts_covered_requirements_and_failures` — 覆う要件数と失敗件数（WHEN 節2）
  - `test_SDD_FR_154_failed_evidence_turns_health_red` — 失敗証跡による総合ヘルス RED（IF 節2）
  - `test_SDD_FR_154_unreadable_evidence_is_counted_as_failure` — 読取不能も失敗として数える（IF 節2）

## 変更前実装に対する negative control

新規 20 件（SDD-FR-153 の 15 件 + SDD-FR-154 の 5 件）を変更前の `spec_inspect.py` /
`sdd_report.py` に対して実行し、**18 件が FAIL** することを確認した。
残る 2 件（`workspace_without_evidence_dir_is_unchanged` /
`section_absent_without_evidence_dir`）は「加法的導入で既存挙動を変えない」ことの確認であり、
変更前後どちらでも green になるのが正しい。

`spec_verify.py` は新規スクリプトのため、変更前には存在せず negative control の対象外。
`tests/test_cli_contract.py` が動的収集で本スクリプトを自動的に契約対象へ取り込む
（未知引数の拒否と `--help` の2件が追加された）。

## 適用範囲外

- 既存 59 件の verified 要件への遡及的な証跡記録は行わない。証跡ディレクトリを持つ
  ワークスペースでは WARN として可視化されるに留まる（裁定点3）。
- 件数の解析器は pytest 形式のみ。他ツールでは `counts` が `null` になり、判定は
  終了コードだけに依存する。解析器は加算的に追加できる。
- `scripts/spec` ラッパーへの `verify` 追加は行わない。ラッパーは sdd-core の4ツールを
  必須解決する設計のため、追加すると既存キャッシュ版で全ツールが解決不能になる
  （裁定記録 `.spec/reports/decision-2026-07-29-si-sdd-016.md` の「実装上の判断」）。
