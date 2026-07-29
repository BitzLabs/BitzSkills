# テスト仕様書: CLI スクリプトの引数契約

sdd-test 工程で CORE-CON-011 の EARS 要件から導出した検証仕様。

- 実行日: 2026-07-29
- 対象リビジョン: base HEAD `b4d4f21` + working tree
- 最終実行コマンド: `.venv/bin/pytest -q` / `python3 scripts/release_check.py` /
  `python3 plugins/bitz-sdd/skills/sdd-core/scripts/spec_inspect.py --workspace . plugins/* --check-only`
- 最終結果: pytest **412 passed** / release_check **PASS** / spec_inspect **全7ワークスペース PASS**

## テスト仕様: CORE-CON-011 CLIスクリプトの未知引数拒否

- **対象要件**: CORE-CON-011
- **導出元種別**: Event-Driven（WHEN 節3つ）+ Optional（WHERE 節1つ）
- **Verification Method**: unit-test
- **テストケース一覧**（`tests/test_cli_contract.py`）:
  - `test_unknown_argument_is_rejected[<script>]`（14 パラメータ）
    — 収集した各 CLI スクリプトへ解釈できない引数を渡し、非ゼロ終了することを検証（WHEN 節1）
  - `test_help_flag_is_honored[<script>]`（14 パラメータ）
    — `--help` が副作用なく効き、使用方法を出力して正常終了することを検証（WHEN 節2）
  - `test_cli_scripts_are_collected`
    — 収集結果が空にならないこと。収集漏れによる素通り green を防ぐ（WHEN 節3 の担保）
  - `test_excluded_scripts_still_exist`
    — 除外宣言が実体から乖離していないこと（WHERE 節）
- **収集と除外**: `scripts/*.py`・`plugins/*/scripts/*.py`・`plugins/*/skills/*/scripts/*.py` を
  glob で収集し、`__main__` を持たないライブラリを自動除外、stdin 駆動 hook 2件を明示除外する。
  新規スクリプトは除外宣言がない限り自動的に対象へ入る。
- **安全性**: 各スクリプトは一時ディレクトリを作業ディレクトリとして起動する。
  契約違反のスクリプトが処理を続行しても副作用は一時ディレクトリ内に閉じる。
- **red 記録**: 変更前の `release_check.py` に対して実行すると、
  `test_unknown_argument_is_rejected[scripts/release_check.py]`（未知引数を黙認して PASS 終了）と
  `test_help_flag_is_honored[scripts/release_check.py]`（`--help` を解釈せず全チェックを実行）の
  2件が FAIL する（negative control 実施済み: 2 failed, 28 passed）。
- **green 記録**: `release_check.py` の argparse 化後、30 件すべて green。

## 実施範囲の対応（SI-CORE-036 の提案項目）

| 提案項目 | 対応 |
|---|---|
| 1. `bump_version.py` の argparse 化 + `--dry-run` | CORE-FR-018 として実施済み（PR #113） |
| 2. 「未知引数を受理しない」の共通契約化 | CORE-CON-011 として要件化し、動的収集の回帰テストで担保 |
| 3. `release_check.py` の厳格化 | 実施（argparse 導入） |
| 4. hook スクリプトの扱いの裁定 | 対象外と裁定。要件本文へ除外理由を明記 |
