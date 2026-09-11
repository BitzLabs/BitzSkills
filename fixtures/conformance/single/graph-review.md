# 文書ID重複・循環fixtureレビュー

2026-09-11。SINGLE-015、022-01/02/03の4件について入力・完全期待JSON・副作用期待値を固定する。
Coreの重複検出やgraph探索の実装結果ではない。

## 単一原因と期待値

最小設定と規範文なしのapproved TECHを使用する。TECHの必須Frontmatter、H1、説明本文は正常で、
code、test、command、REQ、TASKは置かない。全入力を固定metadataでcommitし、
`check --full --base HEAD --format json`で同じbase/currentを検査する計画とする。

| ID | 入力 | Diagnostic / status / exit | 完全検査文書 / 規範文 |
|---|---|---|---|
| SINGLE-015 | TECH-001-a.mdとTECH-001-b.mdが同じTECH-001を定義 | SPEC-ID-DUPLICATE-001 / failed / 1 | 0 / 0 |
| SINGLE-022-01 | TECH-001が自身をrequires | CTX-CYCLE-001 / failed / 1 | 1 / 0 |
| SINGLE-022-02 | TECH-001が自身をrefines | CTX-CYCLE-001 / failed / 1 | 1 / 0 |
| SINGLE-022-03 | TECH-001が自身をrelated | なし / passed / 0 | 1 / 0 |

015は正規file名のslug違いを使い、file名IDとFrontmatter IDを一致させる。
規範文なしTECHなので文書ID以外のstatement重複を混ぜない。現在集合で同じ文書IDへ解決する2 fileを
どちらもskip-documentとし、先に読んだ一方を正常文書として数えない。

022系はrelation名以外を同一byte列とする。TECH→TECHの型、approved状態、参照先の実在は正常である。
自己参照は長さ1の閉路であり、requiresとrefinesでは禁止循環、relatedでは許可される。
複数文書・複数経路の循環や探索順序全般の網羅を、この最小fixtureで証明するものではない。
registryのskip-targetは循環を含むContext展開を遮断するが、checkの独立した本文検査を
skip-documentにはしない。このため022系の完全検査文書数は1とする。

## Diagnosticの固定

- 015は1つのID衝突を1つのraw原因とし、同義のDiagnosticを2 fileへ重ねない。
  sourceはpath辞書順で先頭の`.spec/technical/TECH-001-a.md`、keyは`id`に固定する。
  これはこのfixtureの診断代表位置の選択であり、勝者を選ぶ規則ではない。両文書を不適合として扱う。
- 022-01/02は1つの自己edgeを原因とし、sourceを`.spec/technical/TECH-001.md`、
  keyをそれぞれ`relations.requires`、`relations.refines`とする。参照切れや型違反を重ねない。
- source kindはfile、workspaceIdはroot。非成功のseverityはerror、resultStatusはfailed。
- summaryは各expected/check.jsonの日本語文字列で固定する。line/column、specRefs、evidence、
  suggestedAction、idCollisionsは付加しない。新IDや書換え箇所を提案しない。
- 022-03はDiagnosticを空配列とし、warningも出さない。
- Git IDとdurationだけ既存normalizerの代表値を使い、その他のfieldや件数を比較から除外しない。

診断の代表pathと任意field・文字列は今回選択した受入期待値である。
既存正本は一般の重複集合・複雑な循環の代表source選択までは規定していないため、
この4件から一般の代表選択algorithmを規範化しない。
根拠は[文書IDとfile名](../../../docs/03.詳細設計/02_SPECモデル/02_文書・Frontmatter・状態仕様.md)、
[関係モデル §4・§5・§7](../../../docs/03.詳細設計/02_SPECモデル/04_関係・トレースモデル.md)、
[Diagnostic registry](../../../docs/03.詳細設計/00_共通契約/05_Diagnostic-registry.md)、
[check仕様 §4・§9](../../../docs/03.詳細設計/03_操作仕様/02_check.md)、
[適合matrix](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md)である。

## 準備検証

graph_fixtures.pyは固定入力byte列とFrontmatterのレビュー済み値、manifest、完全期待JSON、
read-only副作用Schemaを確認する。汎用Parserやgraph探索は実装しない。
各fixtureを独立した2つのGit repositoryへsetupし、repository・Git status/index・HOME・cache・TMPDIRを
固定before snapshotと照合する。afterはbeforeと一致する期待値であり、Core実行後の観測値ではない。

回帰試験は片側重複の削除、重複文書の成功件数加算、二重診断、改番提案、参照先不在への変更、
refinesからrelatedへの変更、診断code/keyの取り違え、relatedの誤失敗、cache書込み期待を拒否する。
実際のCoreによる検出、停止・継続、結果と副作用はGate Bで受け入れる。

[Git基準版の5件](git-review.md)と[保護対象外変更の5件](exempt-review.md)を追加し、50/311件を準備済み、実fixture残261件とする。golden Digest、残fixtureの副作用期待値、
fresh checkoutからの全Gate A検証は未完了であり、Gate AはBlockedを維持する。
