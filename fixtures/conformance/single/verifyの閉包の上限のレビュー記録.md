# `verify`の完全な閉包の上限のfixtureのレビュー記録

[適合fixture仕様 §6.19](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#619-verifyの完全な閉包の上限)の
`SINGLE-176-01`〜`SINGLE-176-06`と、[§7](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#7-最小matrix-複合ワークスペース)の
`MULTI-064-01`〜`MULTI-064-06`（置き場は`fixtures/conformance/multi/`）を扱う。いずれもレビュー済みの期待値であり、Coreの挙動を観測したものではない
（[ADR-051](../../../docs/02.設計書/10_決定記録/ADR-051_適合fixtureの変更手続きを確定する.md)の追加）。
生成器と監査は`fixtures/conformance/verify_closure_limit_fixtures.py`である。

## 追加の理由

実装の確認事項C95に対応する。`context`は完全な閉包が上限（文書数、標準の提示のバイト数）を超えると`CTX-LIMIT-001`（`blocked`）で止まる（`SINGLE-048-01`・`02`、`SINGLE-166-06`）が、
`verify`は同じ上限を判定せず、同じ入力を通過にしてテストを起動した。診断レジストリの`CTX-CLOSURE-LIMIT`は`operations`に`verify`を含み、`verify` §9も`CTX-LIMIT-001`を返し得ると書いていたが、
Coreが判定していなかった（`SINGLE-166-06`の入力で、`context REQ-001 --purpose verify`は`blocked`、`verify REQ-001`は`passed`）。

- ユーザーの決定により、規範を明記した（コミット`a0ff8725`）。Coreは、同じ作業の別のコミットで直した。単体試験は`tests/bitz-core/test_verify_closure_limit.py`が押さえる。
- 既存のfixtureが押さえていたのは、`context`の上限（`SINGLE-048-01`・`02`、`SINGLE-166-06`）だけである。`verify`が上限を判定することは、押さえていなかった。

## 根拠の規範文

- `verify` §4の1.: 検証対象ごとに目的`verify`のコンテキストを完全解決する。完全な閉包が上限（`context` §8と同じ規則。起点を所有するワークスペースの`context.maxDocuments`と`context.maxBytes`を使い、
  バイト数は詳細度`standard`の提示で測る）を超えた検証対象は、診断`CTX-LIMIT-001`（`blocked`）とし、`contextDigest: null`、`bindingRefs: []`として、テストを起動しない。独立した検証対象は続ける。
- `verify` §8: コンテキストを構成できない検証対象は、`contextDigest: null`、`statements`は空の配列。
- `verify` §9: `related`の参照切れの警告（`SPEC-RELATION-ADVISORY-MISSING-001`）は、上限（`CTX-LIMIT-001`）で止まる結果を除くすべてで加える（`context` §10と同じ）。
- `context` §8: 上限の既定値は20文書と128 KiB、バイト数は指定した`--detail`にかかわらず詳細度`standard`で測る。
- 診断レジストリ: `CTX-CLOSURE-LIMIT`（`CTX-LIMIT-001`、`error`／`blocked`、`file`、`skip-target`、`context`と`verify`）。

## 入力と起動

| fixture | 入力 | 結果 | 修正前のCore |
|---|---|---|---|
| `SINGLE-176-01` | `SINGLE-042`のcorpus（閉包2文書）、`context.maxDocuments: 1`。`verify REQ-001` | `blocked`／2。`CTX-LIMIT-001`（文書数）。`contextDigest: null`、`commands`は空 | `passed`／0 |
| `SINGLE-176-02` | `SINGLE-048-02`の入力（本文を詰め物で増やす）、`context.maxBytes: 4096` | `blocked`／2。`CTX-LIMIT-001`（バイト数） | `passed`／0 |
| `SINGLE-176-03` | `SINGLE-168-03`の入力（`related`の参照切れ）、`context.maxDocuments: 1` | `blocked`／2。`CTX-LIMIT-001`だけ（警告を加えない） | `passed_with_warnings`／0 |
| `SINGLE-176-04` | `REQ-001`の閉包3文書、`REQ-002`の閉包2文書、`context.maxDocuments: 2`。`verify REQ-001 REQ-002` | `blocked`／2。`REQ-001`は`CTX-LIMIT-001`、`REQ-002`は`passed`で起動する | `passed`／0（`REQ-001`のテストも起動） |
| `SINGLE-176-05` | `SINGLE-176-03`と同じ入力、`context.maxDocuments: 2`（対照） | `passed_with_warnings`／0。警告1件 | `passed_with_warnings`／0 |
| `SINGLE-176-06` | `SINGLE-042`のcorpus、`context.maxBytes: 4096`（対照） | `passed`／0 | `passed`／0 |
| `MULTI-064-01` | `web`の閉包2文書、`web`の`context.maxDocuments: 1`。`verify web::REQ-101` | `blocked`／2。`CTX-LIMIT-001`（`web`） | `passed`／0 |
| `MULTI-064-02` | 同じ文書、ルートの`context.maxDocuments: 1`（対照） | `passed`／0 | `passed`／0 |
| `MULTI-064-03` | ルートのREQ-001の閉包3文書（`web`の2文書を含む）、ルートの`context.maxDocuments: 2`。`verify REQ-001` | `blocked`／2。`CTX-LIMIT-001`（`platform`） | `passed`／0 |
| `MULTI-064-04` | 同じ文書、ルートの`context.maxDocuments: 3`、`web`は1（対照） | `passed`／0 | `passed`／0 |
| `MULTI-064-05` | `web`は閉包2文書で`maxDocuments: 1`、`api`は閉包1文書で既定。`verify --all-workspaces` | `blocked`／2。`web::REQ-101`は`CTX-LIMIT-001`、`api::REQ-201`は`passed`で起動 | `passed_with_warnings`／0 |
| `MULTI-064-06` | `MULTI-064-01`と同じ文書、`TECH-101`が存在しない`ADR-099`を`related`する | `blocked`／2。`CTX-LIMIT-001`だけ（警告を加えない） | `passed_with_warnings`／0 |

- 単一のケースは`SINGLE-042`のcorpusを基に、`SINGLE-168-03`、`SINGLE-175`と同じくインデックスへステージして`verify`を実行する。複合のケースは、ルート`platform`、メンバー`web`、`api`
  （`MULTI-062`と同じ構成）を基準版のコミットへ入れる。
- **起点を所有するワークスペースの上限を使う**ことを、入力で鑑別する。`MULTI-064-01`は`web`だけが1文書、`MULTI-064-02`はルートだけが1文書、`MULTI-064-03`はルートだけが2文書、
  `MULTI-064-04`は`web`だけが1文書で、起点を所有しないワークスペース（または既定）の設定で判定する実装は、結果が変わる。監査が、この鑑別力を入力から要求する。
- **1つの原因だけを持つ**。上限で止まる検証対象は、テスト対応もカバレッジも満たす（`REQ-001`の`MUST`は自身または`TECH-001`のテストが`covers`する）ので、上限がなければ通過する。
  上限が閉包の文書数を超えるのは、文書数の上限のケースだけ、バイト数の上限のケースは文書数の内側で、標準の提示のバイト数だけが上限を超える。
- 上限の境界（ちょうど）は`SINGLE-176-05`（2文書で上限2文書）と`MULTI-064-04`（3文書で上限3文書）が押さえる。バイト数の境界（ちょうど）は、適合fixtureでは押さえず、単体試験の`ByteBoundaryTests`が押さえる（下の6.）。

## 診断の文言

承認済みの文言だけを使い、新しい文言はない。

| 対象 | 文言 | 出典 |
|---|---|---|
| 文書数の上限 | コンテキストの完全な閉包が文書数上限を超過しました | 承認済み（出力文言のレビュー記録の#3。`SINGLE-048-01`が使う） |
| バイト数の上限 | コンテキストの完全な閉包がバイト数上限を超過しました | 承認済み（同#4。`SINGLE-048-02`が使う） |
| `related`の参照切れ（対照の`SINGLE-176-05`） | 関係型relatedの参照先が存在しません | 承認済み（`SINGLE-168`が使う） |

## 期待値の導き方（Coreの出力を根拠にしない）

1. **上限の判定の参照計算**。`reference_outcome`が、入力の木構造から、閉包の文書数（`multi_binding_missing_fixtures.verify_closure`）、標準の提示のバイト数
   （閉包の文書の正規化した本文のUTF-8の長さの和。バイト数のケースの閉包は、起点とそれを直接具体化する文書の2文書で、すべて提示形式`full`）、起点を所有するワークスペースの上限（`context`の設定、
   既定は20文書と131072バイト）を求め、超えたか否か、超えた種類（文書数を先に判定する）が期待と一致することを要求する。Coreの`context`の計算（`closure_limit_summary`など）は使わない。
2. **設定の鑑別力**。起点を所有するワークスペース以外の設定（または既定）で判定すると結果が変わることを、入力から要求する（単純な対照`SINGLE-176-04`の`REQ-002`、`SINGLE-176-05`・`06`、
   `MULTI-064-05`の`api::REQ-201`を除く）。
3. **上限で止まる検証対象の形**。`contextDigest: null`、`statements`と`bindingRefs`は空、診断は`CTX-LIMIT-001`の1件だけで、summaryは超えた上限の種類に合う。起動するテストは、
   上限の内側の検証対象が使うテスト対応のパスだけ（`verify_test_check_fixtures.used_entries`）で、期待結果の`commands[].tests`と一致する。
4. **`related`の警告**。入力に実在する参照切れ（`TECH-001`の`ADR-099`。閉包の外の`TECH-002`の`ADR-098`は警告にならない）を確かめ、上限で止まる検証対象には警告がなく、
   上限の内側の検証対象には警告があることを要求する。
5. **ハッシュ値**。通過する検証対象の`contextDigest`は、リテラルの参照計算A（既存のレビュー済みの材料に`settings.context`だけを替える。複合は文書のリテラルの記述から導く）と、入力の木構造から導く参照計算B
   （単一は`digest_crosscheck.build`、複合は`multi_binding_missing_fixtures.derived_material`。いずれも設定の`context`を読む）の両方で照合する。ハッシュ値の`settings.context`は、
   起点を所有するワークスペースの設定（既定との差を含む）である。
6. **副作用なし**。リポジトリ、`git status`、`HOME`、キャッシュ、`TMPDIR`の読取り専用の実行前後を固定し、準備手順を2回適用して固定したスナップショットと照合する。

## 規範から決まらず、既存の形と仕様の該当箇所で決めた点

1. **上限で止まる検証対象の`statements`**。`verify` §8の「コンテキストを構成できない検証対象は空の配列」に従い、空とした（`CTX-STATE-001`などの既存のfixtureと同じ形）。
2. **診断の発生元**。`context`と同じく、起点を所有するワークスペースと起点の文書（`SINGLE-048-01`・`02`、`SINGLE-166-06`）。複合ワークスペースの`workspaceId`は、起点を所有するワークスペースのID
   （`MULTI-064-03`は`platform`、閉包に`web`の文書を含んでも`web`にしない）。
3. **関係の診断との順**。上限は、強い関係の診断（関係の診断）の後、カバレッジの前に判定する（`context`の判定順に合わせた）。適合fixtureは関係の診断を持たない入力で、順の差を押さえていない（単体試験が押さえる。下の7.）。
4. **`workspace`、`scope`、`revision`**。`verify`の最上位の形は既存のfixture（`SINGLE-168-03`、`SINGLE-175`、`MULTI-062`）に合わせた。単一はインデックスにステージだけでコミットがないので`revision`は`null`、
   複合は基準版のコミットを置く。
5. **Stepの割当て**。同じ操作・同じ診断の既存のfixtureに合わせた。単一の`verify`は`SINGLE-175`と同じStep 4、複合は`MULTI-062`と同じStep 5。実装計画の完了条件の2箇所に足した。
6. **規範が列挙するが、適合fixtureで押さえなかったもの**。
   - バイト数の上限の境界（ちょうど）。`context`の既存のfixture（`SINGLE-048-02`）と単体試験（`test_context.py`の`test_full_refinement_counts_toward_byte_limit`）は、上限を**超える**場合だけを押さえ、境界は押さえていない
     （独立レビューで、`>`を`>=`にする変異が、`context`の適合fixture 123件、既存の単体試験、この群の12件をすべて通過することを確かめた）。境界は、`tests/bitz-core/test_verify_closure_limit.py`の
     `ByteBoundaryTests`が押さえる。`test_boundary_is_derived_from_normalized_bodies`は、`context --purpose verify`の判定から求めた境界Tが、入力から別に導く正規化した本文のUTF-8の長さの和と一致し、
     正規化の前後でバイト数が変わる入力であることを確かめる。`test_verify_boundary_at_T_minus_1_T_and_T_plus_1`は、`verify`がT-1で`CTX-LIMIT-001`（バイト数）、TとT+1で通過することを確かめる。
     `test_verify_matches_context_at_boundary`は、T-1・T・T+1で`verify`の診断が`context`の診断と一致することを確かめる（本文の正規化を外した実装は、ここで`context`と判定が分かれる）。
     適合fixtureとしては足していない（境界の入力が、全角文字・行末の空白・CRLFを含む長い本文になるため、単体試験に置いた）。
   - 提示形式`normative`・`reference`の文書をバイト数に数えない（詳細度`standard`の測り方）。数えない側の境界は、適合fixtureにも単体試験にもない（`full`の文書を数える側は、`test_full_refinement_counts_toward_byte_limit`が押さえる）。
   - 複合ワークスペースのバイト数の上限。
   - `verify`の単独の操作で起点を所有するワークスペースが作業ワークスペースと異なる場合（引数のエラーになるため到達しない）。
7. **検査の順**。関係の診断（強い関係の参照切れ）と状態の診断は、上限より先に判定する（`context`と同じ）。適合fixtureは、関係の診断を持たない入力で、順の差を押さえない。
   単体試験の`CheckOrderTests`が、強い関係の参照切れと状態の診断が上限の超過と同時に起きるとき、`verify`が`context`と同じ診断だけを返し、`CTX-LIMIT-001`を返さないことを押さえる。

## 検証の記録

- 修正後のCore（このブランチ）では、12件すべてが`passed`となる。期待値は規範から導いたもので、Coreに合わせて曲げていない。食い違いはなかった。
- 修正前のCore（`origin/main`の`plugins/bitz-core`）では、欠陥の8件（`SINGLE-176-01`〜`04`、`MULTI-064-01`・`03`・`05`・`06`）が失敗し、対照の4件（`SINGLE-176-05`・`06`、`MULTI-064-02`・`04`）は通る。
  失敗の内訳は上の表のとおり（状態と終了コード、`commands`の件数、警告の有無）。
- 既存の適合fixtureは、修正後のCoreですべて通過し、期待値は変わらない。

## 独立レビュー（PR-f）への対応

条件付きの判定を受け、試験と記録だけを足した（Coreは変えていない）。
- 指摘1（バイト数の境界）、指摘2（測り方の一致）: `ByteBoundaryTests`（上の6.）。変異（`>=`、`closure_limit_summary`の本文の正規化の除去）で失敗する。
- 指摘3（判定の順）: `CheckOrderTests`（上の7.）。変異（上限を関係のエラーの前、`expansion.errors`の前へ移す）で失敗する。
- 指摘4（監査の`check_related`）: `test_conformance_audit.py`の`test_verify_closure_limit_check_related_rejects_vacuous_inputs`。`related`の参照切れを入力から消した入力は、`check_related`だけが拒否する。
