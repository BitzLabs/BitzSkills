---
id: ADR-030
title: verify実行bindingの正規識別子と重複排除単位の統一
status: accepted
relations:
  requires:
    - ADR-026
  related:
    - ADR-018
    - ADR-019
---

# ADR-030 verify実行bindingの正規識別子と重複排除単位の統一

## Context

`bitz verify`の実行単位について、3つの正本が異なる識別子を使っていた。

- [ADR-018](ADR-018_正本Schemaの欠落補完と診断severityの明示.md)はテストパスの重複排除を
  `argv`と`cwd`の組で行うと定めた。
- `bitz.yaml`仕様は`{tests}`を持たないコマンドを設定argvのまま1回実行すると定めた。
- [モノレポSPEC連合仕様](../../03.詳細設計/02_SPECファイル規定/12_モノレポSPEC連合仕様.md)は実行済み判定を
  `(workspace-id, command, test-path)`で行うと定めた。

同じcommand定義に複数のtest pathが属する場合、単一workspaceでは1回、連合ではpathごとに複数回と
解釈できた。逆に、command名は異なるが`argv`と`cwd`が同一の定義は、ADR-018では同一bindingへ統合され、
連合キーでは別実行になった。実行回数と結果の対応付けが実装依存になっていた。

## Decision

1. 検証コマンドbindingの正規識別子を`(workspaceId, 正規化した argv template, 正規化した cwd)`とする。
   command名は識別子へ含めない。名前が異なっても正規化後のargv templateと`cwd`が一致する定義は
   同一bindingとして扱う。`cwd`未指定はテスト所有workspaceルートを表す正規値へ揃える。
2. 同一bindingへ属するtest pathは、テスト所有workspaceルート相対pathで重複排除し、辞書順に整列する。
3. `{tests}`を持つbindingは、重複排除・整列後の全pathを1回だけ展開し、bindingを1回実行する。
   pathごとにプロセスを分けない。
4. `{tests}`を持たないbindingは、対応するtest pathの件数にかかわらずbindingを1回実行する。
5. CLIの実効timeoutは実行結果へ記録するが、bindingの同一性へ含めない。設定timeoutの変更は
   [ADR-026](ADR-026_verify実行binding・timeout・結果Schemaの確定.md) Decision 2のContext Digestが
   保護する。
6. 明示対象verify、引数なしverify、`verify --all-workspaces`は同じ規則を使用する。連合の実行済み集合は
   本識別子で連合全体に1つ保持し、横断refinementが参照する同一bindingを二重に実行しない。
   workspaceIdを識別子へ含めるため、異なるworkspaceの同一argvは従来どおり統合しない。
7. 本決定はADR-018 Decision 2の`(argv, cwd)`と、モノレポSPEC連合仕様の`(workspace-id, command, test-path)`を
   置き換える。ADR-018の他のDecisionは変更しない。

## Consequences

- 単一workspaceと連合で、同じ所有workspaceに対する実行回数が一致する。
- 別名で定義された同一コマンドがテストを二重実行しなくなる。
- 結果JSONの`commands[]`はbinding単位となり、`tests`は当該bindingで実行した全pathを保持する。
- command名は結果の可読ラベルであり、同一bindingへ複数の名前が対応し得る。結果には解決に用いた
  代表名を1つ記録する。
- 1つのbindingが多数のtest pathを持つ場合、1プロセスへ渡す引数が長くなる。実行系の引数長上限に達する
  構成は、コマンド定義の分割で対処する。

## Alternatives

1. **command名を識別子へ含める**: 同一定義の別名が二重実行となり、連合仕様の既存問題を残すため採用しない。
2. **test pathごとに1回実行する**: `{tests}`が複数pathを1回のargvへ展開する既存契約と矛盾し、
   実行時間も増えるため採用しない。
3. **実効timeoutを識別子へ含める**: CLI capは実行ごとの値であり、同じ仕様解釈に対する
   bindingの同一性を変えるべきではないため採用しない（ADR-026 Alternatives 2と同じ理由）。

## Notes

- 本ADRは2026-08-31のユースケース・フロー遷移レビューUC-FLOW-003に対する裁定である。
- 関連文書: [SPECファイル規定/02](../../03.詳細設計/02_SPECファイル規定/02_bitz.yaml仕様.md),
  [SPECファイル規定/06](../../03.詳細設計/02_SPECファイル規定/06_参照・トレース・検証仕様.md),
  [SPECファイル規定/10](../../03.詳細設計/02_SPECファイル規定/10_Context%20Resolution仕様.md),
  [SPECファイル規定/12](../../03.詳細設計/02_SPECファイル規定/12_モノレポSPEC連合仕様.md)

## Revision History

| Date | Summary | Reference |
|---|---|---|
| 2026-08-31 | 検証binding識別子、重複排除単位、実行回数を確定 | — |
