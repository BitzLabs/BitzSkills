# 明示起点の不在とADRの起点のfixtureのレビュー記録

2026-09-17。SINGLE-111-01〜04と112-01〜04の8件を追加する。
根拠は[CLI基盤契約 §6](../../../docs/03.詳細設計/00_共通契約/06_Core実行環境・CLI基盤契約.md#6-対象とワークスペースの不在)、
[`check`仕様 §2・§9](../../../docs/03.詳細設計/03_操作仕様/02_check.md)、
[`context`仕様 §3](../../../docs/03.詳細設計/03_操作仕様/01_context.md#3-処理)、
[`verify`仕様 §3](../../../docs/03.詳細設計/03_操作仕様/03_verify.md#3-検証対象)、
[関係・トレースモデル §6.4](../../../docs/03.詳細設計/02_仕様文書モデル/04_関係・トレースモデル.md#64-targetexpansionroot-purpose)である。

## 不在の起点（`target_root_fixtures.py`）

| ID | 起動 | 唯一の原因 | 期待 |
|---|---|---|---|
| SINGLE-111-01 | `check REQ-009 --base HEAD` | 文書IDがカタログに無い | `failed`／1、`checkedDocumentCount: 0` |
| SINGLE-111-02 | `check REQ-001:AC-09 --base HEAD` | REQ-001は在るがAC-09が無い | `failed`／1、`checkedDocumentCount: 0` |
| SINGLE-111-03 | `check .spec/requirements/REQ-009.md --base HEAD` | 構文上妥当な仕様文書のパスが無い | `failed`／1、`checkedDocumentCount: 0` |
| SINGLE-111-04 | `verify REQ-009` | 文書IDがカタログに無い | `failed`／1、検証対象の診断 |

入力はSINGLE-042のcorpusである。返す診断は、`CTX-ROOT-MISSING-001`（重大度`error`、結果への効果`failed`）の1件だけで、発生元は
`invocation`と指定した引数そのものとする。`summary`は既存の`起点<引数>が存在しません`に揃えた。

`check`は、基準版コミットを作り`--base HEAD`を明示するクリーンな状態で実行するため、`revision`は40桁0の代表値と
`dirty: false`になる。起点を解決できないので、完全検査した文書と規範文は0件である。111-02で所有文書REQ-001の
検査へ置き換えないこと、111-01／03で終了コード4にしないことを、完全な比較とは別の規則の検査でも確かめる。

111-04は`verify`の慣例に従い、コミットせず入力をステージする（設定がインデックスに無いと起動前に停止するため）。
SINGLE-106-05の1起点版であり、検証対象は`contextDigest: null`、`statements: []`、`bindingRefs: []`、
`commands: []`、最上位の`diagnostics: []`とする。

## ADRの起点

| ID | 起動 | 期待 | 所有するモジュール |
|---|---|---|---|
| SINGLE-112-01 | `context ADR-001 --purpose interpret` | `passed`／0、対象規範文なし | `target_root_fixtures.py` |
| SINGLE-112-02 | `context ADR-001 --purpose implement` | 結果なし／4 | `cli_error_fixtures.py` |
| SINGLE-112-03 | `check ADR-001 --base HEAD` | `passed`／0、1文書・規範文0件 | `target_root_fixtures.py` |
| SINGLE-112-04 | `verify ADR-001` | 結果なし／4 | `cli_error_fixtures.py` |

112-01／03は、最小設定と`accepted`のADR-001だけのcorpusを使う。ADRを`related`で参照する文書を置くと、明示した`check`の
「直接逆参照」に弱い関係を含めるかという別の論点が件数へ混ざるため、参照元を置かない。
112-01の閉包はADR-001だけで、制約台帳とカバレッジのすべての区分は空、`documentCount: 1`である。
目的`interpret`はテスト割当てを収録しないため、ハッシュ値の材料の`verifyTimeouts`と`commands`は空である。
ハッシュ値は、本モジュールのリテラル（参照計算A）と、入力の木構造から導出する参照計算Bで一致を確認した。

112-02／04はSINGLE-042のcorpusを使い、存在するADR-001を指定する。字句上は妥当で存在もするため、
引数不正の原因は、`context`では目的、`verify`では操作だけである。出力契約は既存の引数不正のfixtureと同じく、
標準出力なし、`bitz: <operation>: <reason>`の標準エラー出力1行、レポート0件である。

## 準備検証

各fixtureで、マニフェスト、完全な期待JSON、副作用の期待値のスキーマ、入力のバイト列、フロントマターの値のスキーマを照合し、
隔離した2回の準備手順でGitの状態（コミットの有無、インデックスのパスの集合、クリーンな状態）とスナップショットの一致を確認する。
回帰試験は、不在の起点の既知の文書への置換、発生元の付替え、終了コード4への変更、テスト割当ての実行、
ADRの起点への規範文の追加、ハッシュ値の捏造、ADRを参照する文書の混入を拒否する。
Core実装の結果ではなく、Gate Bで実出力と副作用を比較する。
