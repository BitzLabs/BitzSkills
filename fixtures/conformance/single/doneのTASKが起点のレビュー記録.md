# `done`のTASKが起点のfixtureのレビュー記録

[適合fixture仕様 §6.6](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#66-verify)の最後の行である
`SINGLE-068`を扱う。これで`verify`の節は完了する。
レビュー済みの期待値であり、Coreの挙動を観測したものではない。

## 先に契約を確定した

このfixtureは、期待値が未確定の論点に依存していたため、それまでの2回の作業では保留していた。起点のTASKが
`addresses`する参照先を所有する文書が、目的**`verify`**のコンテキストに含まれるかという論点である。
[適合fixture仕様 §3.3](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#33-実成果物との対応)は、
契約より先にfixtureを追加することを禁じているため、先に契約を確定した。

[関係・トレースモデル §6.3](../../../docs/03.詳細設計/02_仕様文書モデル/04_関係・トレースモデル.md#63-verify)は現在、
これを直接述べている。起点のTASKは、`addresses`する参照先とそれを所有する文書を`contextDocuments`へ含め、
その文書から、目的`interpret`の閉包の規則を適用する。目的`implement`と異なり、起点のTASKの`requires`の閉包は含め**ない**。

新しい決定はしていない。[`verify`仕様 §3](../../../docs/03.詳細設計/03_操作仕様/03_verify.md#3-検証対象)は、検証対象のTASKが
`addresses`する参照先を検証することを既に求めており、その文書がコンテキストの外にあれば実行できない。§6.3がそれを
書いていなかっただけである。変更ではなく欠落の補完であることは、次の2点で独立に確認した。

1. 対象展開の参照計算は、target vectorを最初にレビューした時点から、この読みを実装しており、この編集で**25ケースの期待集合は
   変わらない**。（2026-09-17訂正: 参照計算は、`verify`の起点のTASKでも`requires`をたどっていた。§6.3を正として、
   `TASK-REQUIRES-NOT-TARGET`の期待集合と参照計算を修正した。経緯は
   [診断の意味の網羅のレビュー](../診断の意味の網羅のレビュー.md)を参照。）
2. 診断の条件は追加しない。`addresses`は強い関係なので、解決できない参照先は既存の
   `SPEC-RELATION-MISSING-001`になる。診断レジストリの119条件は変わらない。

監査は、この編集を自分で検出した。診断の網羅表と`targets/cases.json`が、この文書のハッシュ値を固定しており、
固定した期待値をレビューし直すまで通過しなかった。再レビューの結果を[診断の意味の網羅のレビュー](../診断の意味の網羅のレビュー.md)
に記録し、その後でハッシュ値を更新した。

## fixture

`TASK-001`は`done`で、`REQ-001:AC-01`だけを`addresses`する。起点が`cancelled`で`blocked`になる
`SINGLE-067`の、成功する側の対である。

| | `SINGLE-067` `cancelled` | `SINGLE-068` `done` |
|---|---|---|
| 結果の状態／終了コード | `blocked`／2 | `passed`／0 |
| `contextDigest` | `null` | 固有の値 |
| `statements` | `[]` | `["REQ-001:AC-01"]` |
| `bindingRefs` | `[]` | `["root::default"]` |

コンテキストは3文書を持つ。起点のTASK、`addresses`する規範文を所有する`REQ-001`、`REQ-001`を具体化しテスト対応を持つ
`TECH-001`である。したがって、ハッシュ値の材料の`documents[]`は、コードポイント辞書順に`REQ-001, TASK-001, TECH-001`となる。

**`AC-02`は意図して`addresses`しない。** 同じREQの規範文だが、起点のTASKの対象規範文は、所有する文書の全規範文ではなく、
TASK自身の`addresses`から決まる。そのため、`AC-02`は対象規範文にならず、それを対象にするテストも、テスト割当てへ入らない。
`tests`は`tests/test_auth.py`だけ、`covers`は`REQ-001:AC-01`だけを持つ。どちらかが混入した結果を監査は拒否する。
これが、`SINGLE-055`（REQが起点）と、このfixture（TASKが起点）とを区別する点である。

## 限界

- Coreは実行していない。Coreとの一致はGate Bで判定する。
- このfixtureは、`addresses`する参照先を解決できる、起点のTASKを固定する。追記した文が定める、もう一方の非成功の分岐
  （解決できない`addresses`の参照先は、対象を空にせず失敗させる）は、matrixにfixtureがなく、既存の、
  関係の参照切れの行だけで扱う。
- この起点のTASKは`requires`を宣言しないため、目的`verify`で`requires`の閉包を含めない規定は、このfixtureでは判別しない
  （後に`SINGLE-110`で判別した）。

## 2026-10-05追記: 先行TASKが`done`のTASKを起点にした目的`implement`（`SINGLE-134`）

### 追加の理由（C8）

目的`implement`でTASKを起点にしたとき、`requires`で参照する先行TASKが状態`done`であるだけで、Coreが`CTX-STATE-001`（`blocked`）を
返していた。上の`SINGLE-068`（`verify`）と`SINGLE-067`（`cancelled`）は起点のTASKの状態を、`SINGLE-051`は先行TASKが未`done`の
場合（`CTX-TASK-DEPENDENCY-001`）を固定するが、「先行TASKがすべて`done`の、`open`のTASKを`implement`の起点にする」正常な場合は
どのfixtureも固定していなかったため、fixtureが通ったまま欠陥が残った。次の規範文が根拠である。

- [文書・フロントマター・状態仕様 §7](../../../docs/03.詳細設計/02_仕様文書モデル/02_文書・フロントマター・状態仕様.md#7-適用可能性):
  「`done`のTASKは、……目的が`implement`で**起点にした場合**は`blocked`とする」。`blocked`にするのは起点にした`done`のTASKだけで、
  別のTASKが`requires`する先行TASKは対象外である。
- [関係・トレースモデル §6.2](../../../docs/03.詳細設計/02_仕様文書モデル/04_関係・トレースモデル.md#62-implement):
  「起点のTASKの`requires`の参照先のTASKがすべて状態`done`でなければ`blocked`とする」。すべて`done`であれば`blocked`にしない。
- 同 §6.2は、起点のTASKの`addresses`と`requires`の閉包を含めると定める。先行TASKは閉包に含めた文書として、コンテキストへ現れる。

### 入力と起動

`context TASK-001 --purpose implement --format json`。corpusは`corpus_done_prerequisite()`である。

| 文書 | 状態 | 内容 |
|---|---|---|
| REQ-001 | `approved` | `REQ-001:AC-01`（`MUST`）を1件持つ。`tests`は宣言しない |
| TASK-001 | `open` | `requires: [TASK-002]`、`addresses: [REQ-001:AC-01]` |
| TASK-002 | `done` | 関係を持たない |

先行TASKに`addresses`を持たせないのは、`SINGLE-110`のように先行TASKの対象のREQが閉包へ入るかどうかという別の論点を、
このfixtureへ混ぜないためである。テスト対応も置かない。置くと未テストの警告が消え、目的`implement`の`MUST`の未テストが
警告であることを固定できない。

### 期待値の導き方

Coreの出力は根拠にせず、次の規範文と参照計算から決めた。

| 項目 | 期待値 | 根拠 |
|---|---|---|
| 状態／終了コード | `passed_with_warnings`／0 | 診断は警告1件だけで、`blocked`の診断がない（状態仕様 §7、関係・トレースモデル §6.2・§8） |
| `contextDocuments`の順 | TASK-001、REQ-001、TASK-002 | 起点を距離0、`requires`と`addresses`を距離1とし、距離が同じなら種別REQ、TECH、ADR、TASKの順（関係・トレースモデル §7の6.）。参照計算`target_vectors.reference`も同じ順を返す |
| 役割 | TASK-001は`root`、REQ-001は`requirement`、TASK-002は`work` | 関係・トレースモデル §7の役割の表（起点以外のTASKは`work`、`addresses`で到達したREQは`requirement`） |
| 提示形式 | すべて`full` | `context`仕様 §5（`root`、`work`、`requirement`は`full`） |
| `reachedBy` | `root`、`addresses:TASK-001`、`requires:TASK-001` | `context`仕様 §5（到達したエッジを`<relation>:<宣言した文書のID>`で表す） |
| 対象規範文 | `REQ-001:AC-01`だけ | 関係・トレースモデル §6.4の3.（TASKを起点にしたときは、`addresses`する規範文） |
| 隣接規範文 | 空 | 規範文を起点にしていないため（§6.4） |
| カバレッジ | `must`の`total`と`addressed`が`REQ-001:AC-01`、`tested`は空、`untested`が`REQ-001:AC-01`。`unaddressed`は空 | §8（閉包にある起点のTASK-001が`addresses`するので対応済み。閉包に`tests[].covers`がないので未テスト） |
| 診断 | `CTX-COVERAGE-TEST-001`／`warning`／`passed_with_warnings`が1件。`source`は`REQ-001.md` | 診断レジストリの`CTX-COVERAGE-TEST-MUST-IMPLEMENT`（目的`implement`の対象規範文の`MUST`が未テストは警告）。未対応の警告`CTX-COVERAGE-TASK-001`は出ない |
| `CTX-STATE-001`、`CTX-TASK-DEPENDENCY-001` | 出ない | 状態仕様 §7、関係・トレースモデル §6.2 |
| コンテキストのハッシュ値 | `sha256:e09309f88d6d61b6225d1de6594f638e040d1887f4b1a96c8336a120667af47b` | 参照計算A（`expansion_fixtures.py`のリテラル）と参照計算B（`digest_crosscheck`が入力の木構造から導出）の正規JSONが一致することを監査で確認した。目的`implement`のため`settings.verifyTimeouts`と`settings.commands`は空 |

### 診断の`summary`

`summary`は「人に向けた短い説明」（結果・診断・終了コードの仕様 §4）であり、規範文を持たない。ユーザーの決定（2026-10-05）により、
Coreの`context`操作の文言「MUST REQ-001:AC-01がtestされていません」にそろえた。同じ診断コード`CTX-COVERAGE-TEST-001`について、
`verify`は「対象MUST …にtest対応がありません」を返し（`SINGLE-060`、`SINGLE-064`）、操作ごとに文言が割れている。
この点はCoreの出力文言の別計画で扱う。

### 限界

- 修正前のCore（`targetexpand.py`の1つ前のコミット）では、このfixtureは`blocked`／2、`CTX-STATE-001`（`TASK-002`が現在のpurposeに
  適用できない）となり、失敗することを確認した（陰性対照）。
- 先行TASKが`done`であるときの別の経路（先行TASKが`requires`をさらに持つ、先行TASKが`addresses`を持つ）は固定しない。
