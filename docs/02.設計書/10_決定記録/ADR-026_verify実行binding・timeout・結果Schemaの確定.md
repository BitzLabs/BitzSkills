---
id: ADR-026
title: verify実行binding・timeout・結果Schemaの確定
status: accepted
relations:
  related:
    - ADR-019
    - ADR-023
---

# ADR-026 verify実行binding・timeout・結果Schemaの確定

## Context

設定仕様はCLIによるtimeout短縮を許可していたが、`bitz verify`の公開文法に該当引数がなかった。
Context Digestは検証コマンド名だけを含み、同じ名前の`argv`や`cwd`が変更されても以前の検証bindingと
同じdigestになり得た。起動失敗とtimeout時のcommand結果Schema、Diagnosticコードも未定義だった。
またTASKが規範文を持たないTECHを`addresses`できる既存契約が、明示verifyの対象選択へ接続されていなかった。

## Decision

1. 明示verifyと`verify --all-workspaces`へ`--timeout <seconds>`を追加する。1以上3600以下の整数とし、
   各workspaceの実効timeoutは`min(CLI指定値, verify.timeoutSeconds)`とする。未指定時は設定値を使う。
2. Context Digestは、検証コマンド名に加えて正規化した`argv` template、`cwd`、設定timeoutを含める。
   CLI timeoutは実行ごとのcapでありContext Digestへ含めず、verify結果へ実効値を記録する。
3. `commands[]`は`status`、`termination`、`exitCode`、`durationMs`、`timeoutSeconds`を持つ。
   `termination`は`exit`、`timeout`、`spawn_error`、`signal`のいずれかとし、通常終了以外の`exitCode`は`null`とする。
4. 終了コード0は`passed`、0以外は`failed`、起動失敗・signal・timeoutは`error`とする。
5. 起動失敗またはsignal終了は`SPEC-VERIFY-COMMAND-001`／error／`error`、timeoutは
   `SPEC-VERIFY-TIMEOUT-001`／error／`error`とする。テストの非0終了はcommand結果を根拠とし、同義Diagnosticを必須にしない。
6. timeoutの実効値と終了理由は単一workspace、連合、標準出力、保存レポートで同じSchemaを使う。
7. TASKが規範文を持たないTECH IDを`addresses`する場合、そのTECHの文書単位`tests`をTASK verifyの
   実行対象へ含める。target statementは増やさず、句単位coverageと文書単位bindingを区別する。

## Consequences

- CLIのtimeout短縮を公開契約どおり実装できる。
- コマンド定義変更でContext Digestが変わり、古い検証bindingを現在のものと誤認しない。
- timeout、起動不能、テスト失敗を機械利用側が区別できる。
- モノレポではworkspaceごとの設定値を保ったまま、単一のCLI capを適用できる。
- 規範文なしTECHを対象とするTASKでも宣言済みテストを実行できる。

## Alternatives

1. **CLI timeoutを削除する**: 実効設定が許す安全な短縮用途を失うため採用しない。
2. **CLI timeoutをContext Digestへ含める**: 同じ仕様解釈に対する実行ごとのcapでdigestが変わるため採用しない。
3. **timeoutを非0終了として扱う**: テストが結果を返した場合と、完了しなかった場合を区別できないため採用しない。

## Notes

- 本ADRは2026-08-31のP2残存契約レビュー「verify実行契約」に対する裁定である。
- Decision 2が定めるContext Digestの構成要素は有効である。実行bindingの正規識別子と重複排除単位は
  [ADR-030](ADR-030_verify実行bindingの正規識別子と重複排除単位の統一.md)を正とする。
- Decision 2の公開Digest構成と実行bindingの同一性は、
  [ADR-039](ADR-039_Core-1.0仕様構造の再編とscope縮小.md)が`contextDigest`だけの公開とcommand名単位へ変更した。
  timeout、終了理由、結果Schema、TECH文書単位bindingに関する他のDecisionは有効である。
- target、Context Digest、binding、command結果の対応とbinding ID fieldは、後続の
  [ADR-041](ADR-041_verify対象別証跡とreport明示保存の分離.md)が補完した。
- 2026-09-01の実装前異常ケースレビュー`EDGE-003`で、timeout時にCoreが停止と回収を保証する対象を
  直接起動したprocessまでと明確化した。子孫processのOS横断管理はCore 1.0へ追加せず、command側の責務とする。
  stdoutとstderrは各64 KiBまで保持し、出力全文を結果Schemaへ追加しない。

## Revision History

| Date | Summary | Reference |
|---|---|---|
| 2026-08-31 | verify timeout、binding digest、command結果Schemaを確定 | — |
| 2026-08-31 | 実行binding識別子の正本が`ADR-030`であることを注記 | `ADR-030` |
| 2026-09-01 | timeout保証範囲と出力保持上限を明確化 | `EDGE-003` |
| 2026-09-01 | Decision 2の一部が`ADR-039`で変更されたことを注記 | `ADR-039` |
| 2026-09-02 | target別証跡とbinding参照を後続決定へ接続 | `ADR-041` |
