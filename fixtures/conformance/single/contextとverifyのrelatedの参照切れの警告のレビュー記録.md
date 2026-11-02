# contextとverifyのrelatedの参照切れの警告のfixtureのレビュー記録

[適合fixture仕様 §6.9](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md)の`SINGLE-168-01`〜`SINGLE-168-06`を扱う。
いずれもレビュー済みの期待値であり、Coreの挙動を観測したものではない
（[ADR-051](../../../docs/02.設計書/10_決定記録/ADR-051_適合fixtureの変更手続きを確定する.md)の追加）。
生成器と監査は`fixtures/conformance/related_advisory_fixtures.py`である。複合ワークスペースの対は
[複合ワークスペースのrelatedの参照切れの警告と横断のエッジのレビュー記録](../multi/複合ワークスペースのrelatedの参照切れの警告と横断のエッジのレビュー記録.md)に記録した。

## 追加の理由

診断レジストリの条件`RELATION-TARGET-MISSING-RELATED`（診断`SPEC-RELATION-ADVISORY-MISSING-001`、`warning`）は、返しうる操作を`context`、`check`、`verify`、
継続単位を`skip-edge`と定める。`check`はこの警告を返していたが、`context`と`verify`は関係の診断からエラーだけを残し、警告を捨てていた。
既存のfixtureは、`related`の参照切れを`check`（`SINGLE-090`）でしか固定していなかったので、この欠陥を押さえていなかった。
規範側は、`context` §10と`verify` §9に「閉包の文書が宣言する`related`の参照切れは、コンテキストまたは検証対象を失敗させず、成功・失敗のどちらの結果にも加える」と明記した
（検証対象の`diagnostics`に置く）。実装の確認事項C78に対応する。

## 根拠の規範文

- 関係・トレースモデル §3: `related`は閉包を増やさず、参照切れは診断`SPEC-RELATION-ADVISORY-MISSING-001`（重大度`warning`）とする。§6.1の7.: `related`を自動で追加しない。
- 診断レジストリ: `RELATION-TARGET-MISSING-RELATED`は`context, check, verify`、`warning`、`passed_with_warnings`、発生元`file`、継続単位`skip-edge`。
- `context` §10: 閉包の文書が宣言する`related`の参照先が存在しない場合の警告は、コンテキストを失敗させず、成功・失敗のどちらの結果にも加える。
- `verify` §9: 閉包の文書が宣言する`related`の参照切れは、検証対象を失敗させず、展開した後のどの結果にもその検証対象の`diagnostics`へ加える。
- 結果・診断・終了コード §3: `warning`だけなら`passed_with_warnings`で終了コード0、`failed`の診断があれば`failed`で終了コード1。
  §4: 関係のエッジを単位とする診断は、`evidence`に参照先を宣言どおりの文字列で持つ。
  §7: 診断は発生元のワークスペースID、`path`、`line`、`column`、`code`、`specRefs`の辞書順に並べ、すべて同じ診断は生成元の宣言に現れた順（関係の配列の順）とする。
- `verify` §8: コンテキストを構成できない検証対象は`contextDigest: null`、`bindingRefs: []`とし、テストを開始しない。

## 入力と起動

`SINGLE-168-01`〜`03`、`06`は`SINGLE-042`のcorpusを基に、`TECH-001`の`related`を`[ADR-001, ADR-099]`にする（`ADR-001`は存在し、`ADR-099`は存在しない）。
さらに、`REQ-001`と関係を持たない`TECH-002`が、存在しない`ADR-098`を`related`する。`SINGLE-168-04`と`05`は`SINGLE-020`と同じ最小の入力（`REQ-001`1件）に、
存在しない参照先の`requires`（`REQ-099`）と`related`（`TECH-099`、`ADR-099`の順）を足す。

| fixture | 操作 | 構成 | 期待 |
|---|---|---|---|
| `SINGLE-168-01` | `context REQ-001 --purpose interpret` | `SINGLE-042`のcorpus、`TECH-001`と`TECH-002`の`related` | `passed_with_warnings`／0。警告は`TECH-001`の1件だけ（閉包は`REQ-001`と`TECH-001`） |
| `SINGLE-168-02` | `context REQ-001 --purpose implement` | 同上と`TASK-001`（両方の規範文を`addresses`） | `passed_with_warnings`／0。警告は1件だけ（閉包は3文書） |
| `SINGLE-168-03` | `verify REQ-001` | `01`と同じ入力（ステージ） | `passed_with_warnings`／0。警告は検証対象の`diagnostics`に1件、コマンドは通る |
| `SINGLE-168-04` | `context REQ-001 --purpose interpret` | 最小の入力 | `failed`／1。診断3件（警告2件、強い関係1件） |
| `SINGLE-168-05` | `verify REQ-001` | 同上（ステージ） | `failed`／1。検証対象の`diagnostics`に同じ3件 |
| `SINGLE-168-06` | `check --full --base HEAD`（対照） | `01`と同じ入力（基準版あり） | `passed_with_warnings`／0。警告2件（`TECH-001`、閉包の外の`TECH-002`） |

`context`は基準版のコミットを置かず（`revision: null`）、`verify`はインデックスへステージし、`check`は基準版のコミットを作る（`SINGLE-150`、`SINGLE-167`、`SINGLE-090`と同じ）。

## 期待値の導き方（Coreの出力を根拠にしない）

1. **警告の範囲**。`context` §10と`verify` §9は「閉包の文書が宣言する」警告に限る。そこで、閉包に入らない`TECH-002`の`ADR-098`は、`context`と`verify`には加えず、
   全文書を検査する`check --full`（`check` §3）にだけ加える（`SINGLE-168-06`）。`related`は閉包を増やさない（関係・トレースモデル §6.1の7.）ので、`ADR-001`（存在する）も`TECH-002`も閉包に入らない。
2. **診断の値**。`summary`は既存の承認済みの文言「関係型relatedの参照先が存在しません」（`SINGLE-090`）、強い関係は「強い関係の参照先が存在しません」（`SINGLE-020`）。
   `source`は`{file, root, 宣言した文書のパス, relations.related または relations.requires}`、`evidence`は宣言どおりの参照先。
3. **並び**。診断は`path`、`code`の辞書順。`SINGLE-168-04`と`05`では同じ`path`なので`SPEC-RELATION-ADVISORY-MISSING-001`が`SPEC-RELATION-MISSING-001`より前になる。
   同じ鍵の警告2件は`related`の宣言の順（`TECH-099`、`ADR-099`）で、辞書順（`ADR-099`、`TECH-099`）ではない。`SINGLE-168-06`は`path`の辞書順に`TECH-001`、`TECH-002`。
4. **失敗の結果**。強い関係の参照切れは完全解決を失敗させるので、`contextDigest: null`、`complete: false`、`documents`は空とする。`unresolvedStrongRelations`は強い関係の件数（1）で、
   `related`の警告は数えない。`verify`の検証対象は`failed`、`contextDigest: null`、`statements`と`bindingRefs`は空、`commands`は空。
5. **ハッシュ値**（`01`〜`03`）。独立に書いた2系統の参照計算（`digest_reference`のリテラルに、目的、`TECH-001`の`related`、目的`implement`のTASK-001だけを替えたA、
   入力の木構造から導く`digest_crosscheck`のB）のバイト列の一致を要求する。`related`は宣言のまま材料の`relations`に残り（存在しない参照先も含む）、`strongRelations`には入らない。
6. **警告の参照計算**。準備手順の後の入力から、範囲の文書（`context`と`verify`は閉包、`check`は全文書）が宣言する関係を宣言の順に読み、解決できないものを診断にする。リテラルの期待値との一致を、
   2回の準備手順のそれぞれで要求する。
7. **修正前のCoreの再現**。`context`と`verify`は警告を捨てる（警告を除き、警告が残らなければ状態を`passed`にする）。`context`と`verify`の5件は期待値と異なり、`check`の対照は同じであることを要求する。

## 規範から決まらず、既存の慣例と仕様の該当箇所で決めた点

1. **目的`implement`の入力にTASKを加える**（`SINGLE-168-02`）。`SINGLE-042`のcorpusはTASKを持たず、そのまま`implement`にすると`CTX-COVERAGE-TASK-001`が規範文ごとに返り、
   この群が固定したい警告と混ざる。そこで、両方の規範文を`addresses`する`TASK-001`を加えた（`SINGLE-054`の形）。警告の件数が規範文ごとか1件かは、この群の対象外である。
2. **失敗した検証対象の`statements`は空**（`SINGLE-168-05`）。`verify` §8は、`contextDigest`が`null`になる条件は書くが、`statements`が空になるとは明記しない。
   既存のfixture（`MULTI-038-03`、`MULTI-038-06`、`SINGLE-149`）の形に合わせた。
3. **失敗の結果の`revision`**。コミットのないリポジトリなので`null`（結果・診断・終了コード §2、`SINGLE-166-10`と同じ）。コミットを持つ場合の値は`SINGLE-166-04`が固定する。
4. **Stepの割当て**。操作が実装される最初のStepに置く。`context`と`check`の4件（`01`、`02`、`04`、`06`）はStep 3、`verify`の2件（`03`、`05`）はStep 4（実装計画 §6・§7）。
   `SINGLE-167`のように族の全件をStep 4に置く割当てもあり得る。この群は、`SINGLE-125`、`SINGLE-127`と同じく操作ごとに分けた。

## 検証の記録

- 修正後のCore（このブランチ）では、6件すべてが`passed`となる。期待値は規範から導いたもので、Coreに合わせて曲げていない。食い違いはなかった。
- 修正前のCore（`origin/main`の`plugins/bitz-core`）では、`SINGLE-168-01`〜`05`が失敗し、対照の`SINGLE-168-06`が通る。
  `01`、`02`、`03`は状態が`passed`で警告が0件、`04`と`05`は診断が1件（`SPEC-RELATION-MISSING-001`だけ）になる。
