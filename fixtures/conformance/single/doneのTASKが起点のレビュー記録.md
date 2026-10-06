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

## 2026-10-05追記: 先行TASKが未完了または`done`のTASKを起点にした目的`verify`（`SINGLE-137`、`SINGLE-138`）

### 追加の理由（C11）

目的`verify`でTASKを起点にしたとき、`requires`で参照する先行TASKが状態`open`のままでも、Coreは`CTX-TASK-DEPENDENCY-001`を返さず、
`passed`にしていた。先行TASKの状態の検査は目的`implement`でしか行っていなかった。上の`SINGLE-068`（`done`の起点）、`SINGLE-067`
（`cancelled`の起点）は起点自身の状態を、`SINGLE-051`は目的`implement`で先行TASKが未`done`の場合を固定するが、
目的`verify`で先行TASKの状態が結果を変える場合はどのfixtureも固定していなかった（`SINGLE-068`の起点は`requires`を持たない）。
そのため、fixtureが通ったまま欠陥が残った。次の規範文が根拠である。

- [ADR-029](../../../docs/02.設計書/10_決定記録/ADR-029_TASKの先行依存の状態ガード.md)の`Decision`の1番目と2番目の項目:
  `requires`で参照する先行TASKがすべて`done`でなければ、`context`と`verify`で`CTX-TASK-DEPENDENCY-001`の`blocked`とする。
- [`verify`仕様 §4](../../../docs/03.詳細設計/03_操作仕様/03_verify.md#4-処理)の手順2と§9: 検証対象ごとに目的`verify`のコンテキストを完全解決し、
  `CTX-TASK-DEPENDENCY-001`を検証対象の`diagnostics`へ返し得る。その検証対象は`bindingRefs: []`、コンテキストを構成できなければ`contextDigest: null`とする。
- [本文テンプレート](../../../docs/03.詳細設計/02_仕様文書モデル/03_文書種別・本文テンプレート.md)のTASKの節: `requires`の参照先のTASKは、
  `implement`または`verify`のときにすべて`done`であること。未完了または`cancelled`なら`CTX-TASK-DEPENDENCY-001`。
- [診断レジストリ](../../../docs/03.詳細設計/00_共通契約/05_診断レジストリ.md)の`CTX-TASK-DEPENDENCY`の行: `CTX-TASK-DEPENDENCY-001`、`error`、`blocked`、
  発生元`file`、継続単位`skip-target`、発生元の操作は`context, verify`。
- [関係・トレースモデル §6.3](../../../docs/03.詳細設計/02_仕様文書モデル/04_関係・トレースモデル.md#63-verify)（2026-10-05に明記）:
  起点のTASKの`requires`の閉包は含めないが、`requires`の参照先のTASKがすべて`done`でなければ`implement`と同じく`blocked`とする。
  §6.4の4.: `requires`の参照先のTASKの`addresses`の参照先は、現在の起点の義務へ追加しない。

### 入力と起動

どちらも`verify TASK-001 --format json`。corpusは`SINGLE-068`と同じREQ-001、TECH-001、ADR-001、設定、ソース、テストに、次の2つのTASKを置く。
`SINGLE-068`との違いは、起点のTASK-001が`done`ではなく`open`で、`requires: [TASK-002]`を持つことと、先行のTASK-002を置くことである。
TASK-001は`REQ-001:AC-01`だけを`addresses`する（`AC-02`は意図して`addresses`しない。理由は上の`SINGLE-068`と同じ）。
`SINGLE-137`のTASK-002は関係を持たない。`SINGLE-138`のTASK-002は、起点のTASK-001が`addresses`しない`REQ-001:AC-02`を`addresses`する。
これにより「先行TASKの`addresses`の参照先を起点の義務へ加えない」確認（[`verify`仕様 §3](../../../docs/03.詳細設計/03_操作仕様/03_verify.md#3-検証対象)の
「`requires`先はコンテキストの材料であり、その規範文またはTASKの`addresses`先をテストの義務へ追加しない」、関係・トレースモデル §6.4の4.）が空にならない。
`AC-02`は閉包の文書（REQ-001）が所有する規範文なので、誤って`requires`先の`addresses`をたどる実装は`AC-02`を対象規範文へ加え、
`tests/test_session.py`（`AC-02`を`covers`する）をテスト割当てへ入れる。

| fixture | TASK-001 | TASK-002 | 期待 |
|---|---|---|---|
| `SINGLE-137` | `open`、`requires: [TASK-002]` | `open`、関係なし | `blocked`／2、`CTX-TASK-DEPENDENCY-001` |
| `SINGLE-138` | `open`、`requires: [TASK-002]` | `done`、`addresses: [REQ-001:AC-02]` | `passed`／0、診断なし |

### 期待値の導き方

Coreの出力は根拠にせず、上の規範文と、`SINGLE-067`、`SINGLE-068`、`SINGLE-051`の既存の期待値の形から決めた。

`SINGLE-137`（`blocked`）:

| 項目 | 期待値 | 根拠 |
|---|---|---|
| 結果の状態／終了コード | `blocked`／2 | 診断の結果への効果が`blocked`の1件だけ（診断レジストリ） |
| `targetResults[0].diagnostics` | `CTX-TASK-DEPENDENCY-001`／`error`／`blocked`の1件だけ | ADR-029、診断レジストリ。`CTX-STATE-001`は出さない（TASK-002は`open`で適用可能） |
| 発生元 | `kind: file`、`workspaceId: root`、`path: .spec/tasks/TASK-001.md`、`key: relations.requires` | 診断レジストリの発生元`file`。起点のTASKが宣言した`requires`が原因なので、`SINGLE-051`の`context`と同じキーにする |
| 診断の置き場所 | 検証対象の`diagnostics`。最上位の`diagnostics`は空 | 継続単位が`skip-target`（`SINGLE-067`と同じ） |
| `contextDigest` | `null` | `verify` §9: コンテキストを構成できない場合は`null` |
| `statements` | `[]` | 先行TASKの検査はコンテキストの構成より前で止めるため、`addresses`の参照先を展開しない。展開していない規範文を並べると、行っていない作業を主張することになる（`SINGLE-067`と同じ理由。下の「迷った点」を参照） |
| `bindingRefs`、`commands` | どちらも空。テストのコマンドを実行しない | `verify` §9、結果のフィールドの説明（実行計画の作成前に非成功となった検証対象は`bindingRefs: []`） |
| `summary` | `先行TASK-002が完了していません` | 規範文を持たない文言のため、同じ診断コードの`context`操作の`SINGLE-051`にそろえた（`SINGLE-134`で決めた方針と同じ） |

`SINGLE-138`（`passed`）:

| 項目 | 期待値 | 根拠 |
|---|---|---|
| 結果の状態／終了コード | `passed`／0 | 先行TASKがすべて`done`なので`blocked`にしない（ADR-029、関係・トレースモデル §6.3）。テストは通る（`/bin/true`） |
| 診断 | 検証対象と最上位の両方で空。`CTX-TASK-DEPENDENCY-001`と`CTX-STATE-001`を返さない | 同上。起点のTASK-001は`open`で適用可能 |
| `statements` | `REQ-001:AC-01`だけ。TASK-002の`addresses`先の`AC-02`を含めない | 関係・トレースモデル §6.4の3.（TASKを起点にしたときは、`addresses`する規範文）。`requires`先のTASK-002の`addresses`先は義務へ加えない（同4.、`verify` §3） |
| `bindingRefs`、`commands` | `root::default`の1件。`tests`は`tests/test_auth.py`、`covers`は`REQ-001:AC-01`だけ | `SINGLE-068`と同じ。`AC-02`を`covers`する`tests/test_session.py`は入れない（`statements`にないので解決しない） |
| コンテキストの文書 | REQ-001、TASK-001、TECH-001の3件。TASK-002を含めない | §6.3: 起点のTASKの`requires`の閉包は含めない。`documents[]`はコードポイント辞書順 |
| TASK-001の`strongRelations` | `addresses`→`REQ-001:AC-01`、`requires`→`TASK-002`の2件 | 正規化仕様 §3.1の`strongRelations`: `relation`、`target`の順で辞書順（`addresses` < `requires`）。宣言した強い関係なので、閉包に含めなくても材料に残る |
| `contextDigest` | `sha256:61dfad7b7a0641f6485665066ad32f5e95e21ff7006164406fc159150d9fefd4` | 参照計算A（`verify_task_root_fixtures.py`のリテラル）と参照計算B（`digest_crosscheck`が入力の木構造から導出）の正規JSONが一致することを監査で確認した。TASK-002は文書の材料に入らず、TASK-001のフロントマターと`strongRelations`はTASK-002の`addresses`に依存しないので、TASK-002へ`addresses`を足してもハッシュ値は変わらない（足す前後で同じ値を確認した） |

先行TASKの状態だけが両者の違いなので、`SINGLE-137`は先行TASKが未完了であることの、`SINGLE-138`は先行TASKが`done`であることの単一の原因を固定する。
`SINGLE-138`は、Coreを誤って「先行TASKを持つ起点を無条件に`blocked`にする」実装にしても、「先行TASKの`addresses`の参照先を対象規範文へ加える」実装にしても通らない。

参照計算Bの`digest_crosscheck.closure`は、閉包の外のTASKが閉包の文書の規範文を`addresses`するエッジを、「閉包の外の強いエッジ」として拒否する。
`SINGLE-138`のTASK-002の`addresses`（`REQ-001:AC-02`）はこれに当たるため、目的`verify`でTASKを起点にしたときだけ、
起点が`requires`する先行TASKの`addresses`のエッジを、辿らない辺として記録する（既存の、起点の`requires`の記録と同じ書き方。
関係・トレースモデル §6.3、§6.4の4.）。適用範囲は、この組合せの先行TASKの`addresses`に限る。目的`implement`の先行TASK
（起点の`requires`の閉包として閉包へ入る）、`REQ`などを起点にした`verify`／`interpret`で閉包の外のTASKが`addresses`するエッジ、
閉包の外のTASKが`requires`で閉包の文書を指すエッジ、後続のTASKが起点を`requires`するエッジは、従来どおり拒否する
（`test_conformance_audit.py`の`test_closure_accepts_only_the_verify_task_root_prerequisite_addresses`が確かめる）。
既存のfixtureの期待値は変わらない。

### 監査の回帰試験

`test_conformance_audit.py`に、次の改変を監査が拒否することを加えた。`SINGLE-137`は診断の消去、診断コードの置換、状態の`passed`化、
`contextDigest`・`statements`・`bindingRefs`・`commands`の非空化、マニフェストの期待の`passed`化。`SINGLE-138`は状態の`blocked`化、
`CTX-TASK-DEPENDENCY-001`または`CTX-STATE-001`の追加、`statements`の削除と追加、`contextDigest`と`bindingRefs`の削除、
`AC-02`のテストの混入（`tests`、`covers`、`argv`）、マニフェストの期待の`blocked`化。先行TASK-002の`addresses`を入力側で消す、
または起点と同じ`REQ-001:AC-01`へ変えた場合も拒否する。さらに、先行TASKの状態を入力側で変えた場合（`SINGLE-137`を`done`・`cancelled`、
`SINGLE-138`を`open`・`cancelled`）も拒否する。

### 限界

- 修正前のCore（`targetexpand.py`をコミット`a869bbc7`の版〔修正のコミット`751169c1`の1つ前〕へ戻したもの）では、`SINGLE-137`は`passed`／0（`contextDigest`と`bindingRefs`、`commands`が非空、診断なし）となり、
  失敗することを確認した（陰性対照）。`SINGLE-138`は修正の前後とも通る。
- 目的`verify`のTASK起点で、`requires`の先行TASKの`addresses`の参照先を対象規範文へ加える変異体のCore（作業ツリー外のコピー）では、
  `SINGLE-138`が失敗する（`AC-02`が`statements`と`covers`に入り、`tests/test_session.py`が割当てへ入る）。`SINGLE-137`は変異の前に止まるので通る。
- 先行TASKが`cancelled`の場合、先行TASKが複数ある場合、先行TASKがさらに`requires`を持つ場合は固定しない。
- 複合ワークスペースでの先行TASKの参照（修飾ID）は固定しない。

## 2026-10-06追記: TASKを起点にした目的`verify`で`refines`する状態`draft`の文書を閉包へ含めない（`SINGLE-143`）

### 追加の理由（実装の確認事項C16）

[関係・トレースモデル §6.1](../../../docs/03.詳細設計/02_仕様文書モデル/04_関係・トレースモデル.md#61-interpret)の末尾は、
「`implement`と`verify`は、`refines`する状態`draft`の文書を閉包へ含めない」と定める。Coreは、`interpret`だけの規則（6.の`advisory`）を
`verify`にも適用し、TASKを起点にした`verify`で、`draft`の文書の状態を適用可否として検査して`CTX-STATE-001`（`blocked`／2）にしていた。
また、`draft`の文書のテスト対応をテスト済みに数え、`verify`の材料の`applicability`は常に`applicable`なので、`context --purpose verify`と
ハッシュ値が食い違い得た。既存のTASK起点の`verify`のfixture（`SINGLE-068`、`137`、`138`、`110`）には、`refines`する`draft`の文書を持つものがなかった。
`SINGLE-143`は、`SINGLE-142`（目的`implement`、`context`）と対になる`verify`のfixtureである。

### 入力と起動

`verify TASK-001 --format json`（設定をステージする。`SINGLE-138`と同じ）。corpusは`corpus_draft_excluded_task()`である。

| 文書 | 状態 | 内容 |
|---|---|---|
| TASK-001 | `open` | `addresses: [REQ-001:AC-01]`。`requires`はない |
| REQ-001 | `approved` | `REQ-001:AC-01`（`MUST`）を1件持つ。`tests/test_root.py`が`REQ-001:AC-01`を`covers`する |
| TECH-005 | `draft` | `TECH-005:AC-01`（`MUST`）を1件持つ。`refines: [REQ-001]`（文書単位。`SINGLE-142`は規範文単位）。`tests/test_candidate.py`が`REQ-001:AC-01`と`TECH-005:AC-01`を`covers`する |

TECH-005のテスト対応が`REQ-001:AC-01`を`covers`するのは、`draft`の文書のテストを実行しないことを、コマンドの`argv`で判別できるようにするためである。

### 期待値の導き方（Coreの出力を根拠にしない）

| 項目 | 期待値 | 根拠 |
|---|---|---|
| 結果の状態／終了コード | `passed`／0 | `TECH-005`は閉包の外なので状態を検査しない（§6.1の末尾、§10）。TASK-001は`open`で先行TASKがない。テストは通る（`/bin/true`） |
| 診断 | 検証対象と最上位の両方で空。`CTX-STATE-001`を返さない | 同上 |
| `statements` | `REQ-001:AC-01`だけ | §6.4の3.（TASKを起点にしたときは、`addresses`する規範文と、その具体化文書の規範文）。`draft`のTECH-005は具体化文書に加えない |
| `bindingRefs`、`commands` | `root::default`の1件。`tests`は`tests/test_root.py`だけ、`argv`は`["/bin/true", "tests/test_root.py"]`、`covers`は`REQ-001:AC-01` | `verify` §3〜§9（対象規範文のテスト対応から、閉包の文書の`tests[]`だけを集める）。`tests/test_candidate.py`は閉包の外の文書のテスト対応で、実行しない |
| コンテキストの文書 | TASK-001、REQ-001の2件 | §6.3（起点のTASKの`addresses`の参照先を所有する文書を含める）。TECH-005は含めない |
| `contextDigest` | `sha256:4a6404ef2cc326225d2110810d3bb7fa1e1a285590692b09280ec7bc242f49c6` | 材料は目的`verify`、`documents[]`はREQ-001、TASK-001（コードポイント辞書順）、コマンドは`default`の1件。参照計算Aと、入力の木構造から導く参照計算Bの正規JSONの一致を監査で確認した。TECH-005の材料への混入は、`applicability`を何にしても材料の文書の集合が変わるのでハッシュ値が変わる |

参照計算Bの修正は`SINGLE-142`の節（上の`共通の対象展開と参考（advisory）の提示のレビュー記録.md`）と同じで、`implement`と`verify`で閉包へ含めない`draft`の文書の
`refines`のエッジを、辿らない辺として記録する。

### 監査の検査と限界（C16）

`check_contract`の`check_draft_excluded`が、結果のどこにもTECH-005と`test_candidate`が現れないこと、`CTX-STATE-001`がないこと、
対象規範文とコマンドが上の値であることを確かめる。回帰試験は、`tests/test_candidate.py`の混入、`blocked`化、ハッシュ値の改変、
`TECH-005:AC-01`の混入、マニフェストの期待の`blocked`化を拒否することを確かめる。

- 修正前のCore（コミット`90ba92a3`の`targetexpand.py`）では失敗する。TECH-005の状態検査で`blocked`／2（`CTX-STATE-001`）となり、`contextDigest`は`null`、
  `statements`と`bindingRefs`と`commands`は空になる（陰性対照）。
- 修正前のCoreのハッシュ値の食い違い（`verify`の材料の`applicability`が常に`applicable`）は、この`SINGLE-143`では現れない。
  `blocked`が先に起きるためである。起点がREQで`draft`の文書を`refines`される`verify`は、修正前のCoreでは状態を検査せず、`draft`のテストを実行して
  `context --purpose verify`とハッシュ値が食い違う（作業ツリー外で確認した）が、このfixtureでは固定しない。
- 起点がREQ、TECH、規範文の`verify`、`draft`の文書が複数ある場合、`draft`の文書を`addresses`するTASKがある場合は固定しない。
- TASKを起点にした`implement`で、`draft`の文書が閉包の文書を`refines`する場合は固定せず、Coreの単体試験
  （`tests/bitz-core/test_targetexpand.py`の`DraftRefinementPurposeTests`）だけで確かめる。
- 期待値はCoreを実行せずに決めた。Coreとの一致の確認は、期待値を決めた後に行い、Gate Bで判定する。
