# 複合ワークスペースの単独のverifyの上限のfixtureのレビュー記録

[適合fixture仕様 §7](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#7-最小matrix-複合ワークスペース)の
`MULTI-041-01`〜`MULTI-041-04`を扱う。いずれもレビュー済みの期待値であり、Coreの挙動を観測したものではない
（[ADR-051](../../../docs/02.設計書/10_決定記録/ADR-051_適合fixtureの変更手続きを確定する.md)の追加）。
生成器は`fixtures/conformance/multi_generator.py`の`single_verify_plan`、参照計算と監査は
`fixtures/conformance/multi_single_verify_limit_fixtures.py`である。

## 追加の理由（実装の確認事項C40）

複合ワークスペース仕様 §10は、`verify`では`commandDefinitionCount`の判定を実行計画を確定した後に行い、`verifyBindingCount`も超過していれば
`verifyBindingCount`を報告すると定める。`verify --all-workspaces`はこのとおりに動くが、単独の`verify`は全体事前検査で`commandDefinitionCount`を
先に判定しており、両方が超過しても`commandDefinitionCount`を報告していた（[ADR-063](../../../docs/02.設計書/10_決定記録/ADR-063_複合ワークスペースの単独操作の全体事前検査を確定する.md)の決定8）。
[ADR-066](../../../docs/02.設計書/10_決定記録/ADR-066_単独のverifyの上限を実行計画の確定後に判定する.md)が、単独の`verify`も`--all-workspaces`と同じく
実行計画の確定後に判定すると改訂したので、その扱いを固定する4件を追加する。既存の462件の入力と期待値は変えない。

## 根拠の規範文

- 複合ワークスペース仕様 §7: 単独の`verify`は、`--all-workspaces`と同じく、`commandDefinitionCount`を全体事前検査では判定せず、§10のとおり
  実行計画を確定した後に`verifyBindingCount`と合わせて判定する。
- 複合ワークスペース仕様 §10: `verifyBindingCount`は「1回の`verify`実行計画にあるテスト割当ての数」、`commandDefinitionCount`は「全ワークスペースのコマンド定義数」。
  `verify`では`commandDefinitionCount`の判定を実行計画を確定した後に行い、同時に`verifyBindingCount`も超過していれば`verifyBindingCount`を報告し、
  `commandDefinitionCount`だけが超過していればそれを報告する。上限超過は`SPEC-MULTI-LIMIT-001`（`blocked`）とし、部分的な結果やコマンドの実行へ進まない。
  `evidence`は`dimension`、`limit`、早期に停止したときの`observedAtLeast`を持つ。上限は10,000で、超過は10,000を超える（10,000は通る）。
- ADR-066の決定2・3と Consequences: 優先の範囲は`commandDefinitionCount`と`verifyBindingCount`の組。`commandDefinitionCount`だけが超過し、`--workspace`のIDがカタログにない場合は、
  全体事前検査が成功するので引数不正（終了コード4）になる（ADR-063の決定3は、全体事前検査が成功した場合には当てはまらない）。
- `verify` §3・§4: テスト割当ては`(workspaceId, commandName)`の組で、全検証対象の`bindingRefs`を和集合にして重複を排除する。1回の`verify`で高々1回実行する。
  `verify` §8: 検証対象ごとの結果（`targetResults[]`）とコマンドの実体（`commands[]`）、`bindingRefs`は重複なし辞書順。
- 結果・診断・終了コード §2: 複合ワークスペース内の単独の`verify`は`workspace`、`scope`、`targetResults`、`commands`、`revision`を持つ。明示対象の`scope`は`selected`（`verify` §2）。
- 診断の文言は、`Coreの出力文言のレビュー記録.md`の承認済みの文字列（「テスト割当て数が上限10,000を超過しました」、「コマンド定義数が上限10,000を超過しました」）である。

## 入力と起動

入力は、`MULTI-020-*`・`MULTI-021-*`と同じく、バージョン管理できない大きさになるため、
[ADR-048](../../../docs/02.設計書/10_決定記録/ADR-048_適合fixtureの生成入力とGit構造の準備の処理を確定する.md)に従いデータセットのマニフェストから生成する。
データセットのマニフェストは`profile`（`kind: single-verify-plan`、`bindings`、`commands`）を持ち、既存の`dimension`と`value`の生成計画（`plan`）と区別する。

既存の`plan`の`verifyBindingCount`は、割当てを全ワークスペースへ散らし、各ワークスペースの文書が自分の規範文を`covers`する。
ルートからの単独の`verify`は、ルートワークスペースの文書だけを対象にし、他のメンバーの文書は、ルートの対象を`refines`する具体化文書として
閉包に入るときだけ到達する（関係・トレースモデル §6.1・§6.4）。このため、既存の入力では、ルートからの1回の単独の`verify`はルートの分（高々800件）にしか届かない。

新しい生成計画`single_verify_plan`は、次の形にする。

- ルート`platform`は、検証対象のREQ（`approved`、`MUST`の規範文1件、関係なし）だけを持ち、コマンドを定義しない。
- メンバーは13件（`m001`〜`m013`）。1ワークスペースあたりのコマンド定義は800件までに分け（設定の64 KiB上限）、テスト割当てとコマンド定義の件数は均等に分ける。
- 各メンバーは、TECHを250件のテスト対応ごとに1件置く。TECHは`approved`、規範文なしで、ルートのREQ1件を`refines`し、すべてのテスト対応がそのREQの規範文を`covers`する。
  別のワークスペースの規範文を`covers`できるのは、宣言する文書がその規範文を所有する文書を直接`refines`する場合に限る（関係・トレースモデル §9）。
- テスト割当て1件は、メンバーの別々のコマンド名（`c00001`〜）と別々のテストのパス（`tests/test_NNNNN.py`）を持つ。コマンド定義がテスト割当てより多い分は、使わない名前として足す。
- 起動は、ルートで`verify`にルートのREQを全件並べる（`platform::REQ-001`〜）。実行計画は検証対象52件のテスト割当ての和集合（`verify` §3）である。

検証対象を1件にしない理由は、1件のREQが10,000件超のテスト割当てを閉包に持つと、閉包が上限（既定20文書・128 KiB、絶対上限100文書・1 MiB。コンテキスト仕様 §8）を超え、
当該の検証対象が`CTX-LIMIT-001`（`blocked`）になって実行計画に入らないためである。各検証対象の閉包は、REQ1件とTECH1件（約22 KB）に保つ。
監査の試験は、この閉包の文書数とバイト数、TECHのフロントマター（32 KiB）、設定（64 KiB）の上限を、実寸の生成計画で確かめる。

| fixture | 起動 | 実行計画のテスト割当て | コマンド定義 | 期待 |
|---|---|---:|---:|---|
| `MULTI-041-01` | `verify`＋ルートのREQ全件 | 10,001 | 10,001 | `blocked`／2。`dimension=verifyBindingCount`、`limit=10000`、`observedAtLeast=10001` |
| `MULTI-041-02` | `verify`＋ルートのREQ全件 | 10,000 | 10,001 | `blocked`／2。`dimension=commandDefinitionCount`、`limit=10000`、`observedAtLeast=10001` |
| `MULTI-041-03` | `verify`＋ルートのREQ全件 | 10,000 | 10,000 | `passed`／0。検証対象52件とコマンド10,000件がすべて`passed` |
| `MULTI-041-04` | `verify --workspace nope` | 1 | 10,001 | 終了コード4。結果なし、標準出力は空、標準エラー出力は1行 |

`MULTI-041-01`は、ADR-066で変わった優先そのもの（両方が超過）を固定する。`MULTI-041-02`は、実行計画が上限内で`commandDefinitionCount`だけが超過するときに、
その判定が実行計画の確定後にも残ることを固定する（`commandDefinitionCount`の判定を落とす実装を拒否する）。`MULTI-041-01`との差は、実行計画が上限内であることだけである
（`verifyBindingCount`の値が10,001と10,000、コマンド定義数が10,001で同じ）。`MULTI-041-03`は境界値を遮断しない対照で、`MULTI-020-16`の単独版である。
`MULTI-041-04`は、ADR-066の Consequences が定める行動の変更（以前は全体事前検査の停止で`blocked`／2）を固定する。

## 期待結果の組立て

- `MULTI-041-01`・`-02`: 結果は`status: blocked`、`scope: selected`、`workspace: {platform, .}`、`targetResults: []`、`commands: []`、`revision: {commit, dirty: false}`、診断1件。
  診断は`MULTI-021-07`・`MULTI-021-08`と同じ（`source`はルートの`.spec/bitz.yaml`、`resultStatus: blocked`）。`resultDigest`で固定する。
- `MULTI-041-03`: 検証対象52件は、ルートの各REQで、`statements`は`platform::REQ-NNN:AC-01`、`bindingRefs`は具体化するTECHのテスト割当て（重複なし辞書順）、`contextDigest`は
  入力の木構造から導出する参照計算B（`multi_crosscheck`）の値である。`commands`は10,000件で、ワークスペースの処理順とコマンド名の辞書順、
  `bindingId`は`<メンバー>::<コマンド名>`、`covers`は`platform::REQ-NNN:AC-01`（修飾ID）。これを`resultDigest`で固定する。
- `MULTI-041-04`: `cli-output.json`（終了コード4、`bitz: verify: `で始まる1行）。`MULTI-005`の形である。

## 規範から導けなかった点・固定の程度

起案の時点で、規範の文が1つに定めていない次の点は、既存のfixtureの扱いに合わせて固定した。規範の文が変わる場合は、この記録を直す。

- 実行計画の確定後に上限を超過した単独の`verify`の結果の形。複合ワークスペース仕様 §10の「部分的な結果やコマンドの実行へ進まない」と、結果・診断・終了コード §2の
  「処理を始める前に停止した場合、派生する配列は空」から、`targetResults`と`commands`を空にした。検証対象のコンテキストの解決は済んでいるが、結果へは出さない。
  `--all-workspaces`の`MULTI-021-08`が`workspaces: []`であることと合わせた読みである。
- 診断の`source`。`MULTI-021-*`と同じく、ルートの`.spec/bitz.yaml`（`workspaceId: platform`）とした。診断レジストリは`MULTI-LIMIT`の発生元を`file`とだけ定める。
- `observedAtLeast`は、超過する次元がちょうど上限+1なので、早期停止でも全件を数えても10,001になる。値が10,001を超える入力は扱わない。
- 検証対象を複数並べる起動の形（上の理由）。ルートの単独の`verify`は引数なしでも、ルートの`approved`のREQ全件が対象になり、同じ実行計画になる
  （`verify` §7。修正前のCoreに`MULTI-041-03`の入力で引数なしの`verify`を実行し、検証対象52件・コマンド10,000件・`scope: all`を確かめた）が、
  このfixtureは明示対象（`scope: selected`）を使う（指示の「修飾ID」に合わせた）。
- `MULTI-041-04`の標準エラー出力の1行の文言は固定しない（`cli-output.json`は接頭辞と行数だけを固定する。他の引数不正のfixtureと同じ）。

## 陰性対照（修正前のCore）

修正前のCore（`cb94f4dd`の`plugins/bitz-core`を`git archive`で展開したもの）に対して`uv run fixtures/run_conformance.py --core <展開先> --step 5`を実行した
（2026-10-22。Step 1〜5の累積466件、全体で452.4秒）。

| 結果 | 件数 | fixture |
|---|---:|---|
| `passed` | 464 | 既存の462件（`MULTI-020-16`、`MULTI-021-07`、`MULTI-021-08`を含む）と、`MULTI-041-02`、`MULTI-041-03` |
| `failed` | 2 | `MULTI-041-01`、`MULTI-041-04` |
| `error` | 0 | |

- `MULTI-041-01`: `resultDigest`の不一致。修正前のCoreの結果のハッシュ値（`sha256:2740917318cb…`）は`MULTI-041-02`の期待値と同じで、両方が超過しても
  `commandDefinitionCount`を報告する（優先の誤り）ことを示す。
- `MULTI-041-04`: 終了コードの期待4に対して実際は2（全体事前検査の停止で`blocked`の結果をJSONで出力する）。
- `MULTI-041-02`と`MULTI-041-03`は修正前のCoreでも通る。`-02`は修正後に`commandDefinitionCount`の判定を実行計画の確定後へ移すとき、判定を落とさないことの対照、
  `-03`は境界値を遮断しないことの対照である。`-03`が通ったことは、検証対象52件・コマンド10,000件の期待結果（`contextDigest`を含む）が、
  独立に書いた既存のCoreの実装と一致することの確認にもなる。
- 既存の462件がすべて通ったので、既存のfixtureの入力と期待値は変わっていない。

## 大きさと所要時間

| fixture | 生成するファイル数 | 設定と仕様文書のバイト数 | 修正前のCoreの所要時間（局所、秒） |
|---|---:|---:|---:|
| `MULTI-041-01` | 10,119 | 1,532,205 | 4.35 |
| `MULTI-041-02` | 10,118 | 1,532,117 | 3.98 |
| `MULTI-041-03` | 10,118 | 1,532,055 | 23.04 |
| `MULTI-041-04` | 17 | 622,523 | 1.07 |

所要時間は`selection.py`の暫定値の換算に使った値である。修正後のCoreは実行計画を確定してから止まるため、独立レビューの局所の実測で`041-01`と`041-02`が
約3割遅い（5.63秒、5.28秒）。暫定値はCIの実測を得たら置き換える。

リポジトリへコミットするのは、4件の`dataset.json`、`manifest.json`、`side-effects.json`（と`MULTI-041-04`の`cli-output.json`）だけで、合計約10 KBである（`MULTI-021-08`は10,027ファイルを生成する）。
既定の監査は縮小した生成計画だけを生成し、監査の所要時間はほとんど変わらない。実寸の生成の照合（`uv run fixtures/validate_scale.py`）は4件で約12秒増える。
CIの所要時間の予測（`conformance/selection.py`）は、4件を`scale`に含め、CIの実測がまだないため、上の局所の所要時間を類似fixture（`MULTI-021-08`、`MULTI-020-16`）のCI実測の比で換算した
暫定値（9.55、8.74、33.49、2.35秒）を使う。4分割の予測は、各分割で約3分39秒から3分53秒になる。CIの実測を得たら置き換える。
