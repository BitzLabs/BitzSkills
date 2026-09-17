# 明示起点の不在・ADR起点fixtureレビュー

2026-09-17。SINGLE-111-01〜04と112-01〜04の8件を追加する。
根拠は[CLI基盤契約 §6](../../../docs/03.詳細設計/00_共通契約/06_Core実行環境・CLI基盤契約.md#6-targetとworkspaceの不存在)、
[check仕様 §2・§9](../../../docs/03.詳細設計/03_操作仕様/02_check.md)、
[context仕様 §3](../../../docs/03.詳細設計/03_操作仕様/01_context.md#3-処理)、
[verify仕様 §3](../../../docs/03.詳細設計/03_操作仕様/03_verify.md#3-対象)、
[関係・トレースモデル §6.4](../../../docs/03.詳細設計/02_SPECモデル/04_関係・トレースモデル.md#64-targetexpansionroot-purpose)である。

## 不在起点（`target_root_fixtures.py`）

| ID | 起動 | 唯一の原因 | 期待 |
|---|---|---|---|
| SINGLE-111-01 | `check REQ-009 --base HEAD` | 文書IDがcatalogに無い | failed／1、`checkedDocumentCount: 0` |
| SINGLE-111-02 | `check REQ-001:AC-09 --base HEAD` | REQ-001は在るがAC-09が無い | failed／1、`checkedDocumentCount: 0` |
| SINGLE-111-03 | `check .spec/requirements/REQ-009.md --base HEAD` | 構文上妥当なSPEC pathが無い | failed／1、`checkedDocumentCount: 0` |
| SINGLE-111-04 | `verify REQ-009` | 文書IDがcatalogに無い | failed／1、target Diagnostic |

入力はSINGLE-042のcorpusである。Diagnosticは`CTX-ROOT-MISSING-001`／error／failedの1件だけで、sourceは
`invocation`と指定した引数そのものとする。summaryは既存の`起点<引数>が存在しません`に揃えた。

checkは基準版commitを作り`--base HEAD`を明示するclean状態で実行するため、`revision`は40桁0の代表値と
`dirty: false`になる。起点を解決できないので完全検査した文書と規範文は0件である。111-02で所有文書REQ-001の
検査へ置き換えないこと、111-01／03で終了コード4にしないことを、完全比較とは別の規則検査でも確かめる。

111-04はverifyの慣例に従い、commitせず入力をstageする（設定がindexに無いと起動前に停止するため）。
SINGLE-106-05の1起点版であり、targetは`contextDigest: null`、`statements: []`、`bindingRefs: []`、
`commands: []`、top-levelの`diagnostics: []`とする。

## ADR起点

| ID | 起動 | 期待 | 所有module |
|---|---|---|---|
| SINGLE-112-01 | `context ADR-001 --purpose interpret` | passed／0、target statementなし | `target_root_fixtures.py` |
| SINGLE-112-02 | `context ADR-001 --purpose implement` | 結果なし／4 | `cli_error_fixtures.py` |
| SINGLE-112-03 | `check ADR-001 --base HEAD` | passed／0、1文書・規範文0件 | `target_root_fixtures.py` |
| SINGLE-112-04 | `verify ADR-001` | 結果なし／4 | `cli_error_fixtures.py` |

112-01／03は最小設定とaccepted ADR-001だけのcorpusを使う。ADRを`related`で参照する文書を置くと、明示checkの
「直接逆参照」に弱い関係を含めるかという別の論点が件数へ混ざるため、参照元を置かない。
112-01の閉包はADR-001だけで、Constraint Ledgerとcoverageの全bucketは空、`documentCount: 1`である。
interpretはbindingを収録しないため、Digest材料の`verifyTimeouts`と`commands`は空である。
Digestは本moduleのliteral（reference A）と、入力treeから導出するreference Bで一致を確認した。

112-02／04はSINGLE-042のcorpusを使い、存在するADR-001を指定する。字句上は妥当で存在もするため、
引数不正の原因はpurpose（context）または操作（verify）だけである。出力契約は既存の引数不正fixtureと同じく、
標準出力なし、`bitz: <operation>: <reason>`の標準エラー1行、report 0件である。

## 準備検証

各fixtureで、manifest・完全期待JSON・副作用期待値のSchema、入力byte列、Frontmatter値のSchemaを照合し、
2回の隔離setupでGit状態（commitの有無、indexのpath集合、clean状態）とsnapshotの一致を確認する。
回帰試験は、不在起点の既知文書への置換、sourceの付替え、終了コード4への変更、binding実行、
ADR起点へのstatement追加、Digestの捏造、ADRを参照する文書の混入を拒否する。
Core実装の結果ではなく、Gate Bで実出力と副作用を比較する。
