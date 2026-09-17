# 複合workspace golden Digest fixture review

[適合fixture仕様 §7](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#7-最小matrix-複合workspace)の
`MULTI-002-01`と`MULTI-002-02`を扱う。いずれもreview済みの期待値であり、Coreの挙動を観測したものではない。

## corpusは1つで、3つの論点を同時に固定する

root workspace `platform`はcatalogと共通要求`REQ-001`だけを持ち、member `web`（`apps/web`）と
`api`（`services/api`）がそれぞれ`TECH-010`で1つずつ規範文を具体化する。この最小構成で次を同時に固定できる。

- **横断`refines`**: `web::TECH-010`が`platform::REQ-001:AC-01`を、`api::TECH-010`が`:AC-02`を具体化する。
- **横断coverage**: 各memberの`tests[].covers`が、直接`refines`している別workspaceの規範文を指す。
  [複合workspace仕様 §5](../../../docs/03.詳細設計/02_SPECモデル/05_複合workspace仕様.md#5-所有境界)が許すのは
  この直接refinementの場合だけであり、推移的なrefinementを根拠にしていない。
- **同じlocal ID**: 2つのmemberがどちらも`TECH-010`を名乗る。修飾IDにしなければ衝突する入力である。

catalogの列挙順は`web`、`api`とした。結果と材料のworkspace順は常にrequest workspaceが先頭でID辞書順
（`platform`、`api`、`web`）になるため、列挙順をそのまま出力へ写していれば監査が落ちる。

## goldenは2系統の参照計算で照合する

単一workspaceの`SINGLE-042`と同じ方法を使う。`multi_reference`はreview済みのDigest材料をliteralで持ち、
`multi_crosscheck`は同じbyte列を入力treeから導出する。後者はroot設定のcatalogを読み、workspaceごとに文書を読み、
修飾ID、横断edge、到達workspaceだけの設定射影を自分で組み立てる。文書1件の読取りとRFC 8785 serializerは
単一workspace側と共有し、複合workspace固有の解決だけを別に書いた。両者が一致しなければ監査は失敗する。

材料は[Context Digest正規化仕様 §3](../../../docs/03.詳細設計/00_共通契約/03_Context-Digest正規化仕様.md#3-digest-input)に従い、
`requestWorkspaceId`、到達workspaceの`id`と`path`、修飾起点、修飾edge、到達workspaceだけの設定を持つ。
`multiWorkspace.maxMembers`、catalogの列挙順、未到達workspaceの設定は材料へ入れない。監査試験は、
材料に`maxMembers`が現れないこと、workspaceと文書の並びが規定順であることを別に検査する。

golden値は`sha256:72661dba40f08eb57cc1a57fe36d9a60f67df24826b4ebfdbbd8afb77c6f1fd3`である。

## `MULTI-002-02`は同じ材料をverifyの側から固定する

`verify platform::REQ-001`は同じ`purpose=verify` Contextを再解決するので、`targetResults[0].contextDigest`は
goldenと同じ値になる。監査は、2つのfixtureのDigest材料がbyte一致することを要求する。bindingは
`api::backend`と`web::frontend`の2件であり、command実体は所有memberへ1件ずつ置く。root workspaceは
commandを定義せず、bindingも持たない。

## commit済みのcleanな状態を使う

複合workspaceのcheckとverifyはGit境界の確定を事前検査条件にするため、`revision`をnullにできない
（[結果・Diagnostic・終了コード §2](../../../docs/03.詳細設計/00_共通契約/01_結果・Diagnostic・終了コード.md#2-共通結果)）。
そのため両fixtureは`baseCommit`を持つcleanなcommit済み状態とし、期待値のcommit IDは共通normalizerが
40桁16進としてだけ検査する固定の0埋め値を置く。単一workspaceのgolden（unborn、`revision: null`）とは
この点だけが異なる。

## 限界

- Coreは実行していない。実際の解決処理が同じ材料を作るかはGate Bで判定する。
- `purpose`は`verify`だけを固定した。`interpret`と`implement`の複合workspace Digestは、
  単一workspace側の群と同じく別のfixtureが必要である。
- memberは2件である。member数の境界は`MULTI-020`と`MULTI-021`が扱う。
