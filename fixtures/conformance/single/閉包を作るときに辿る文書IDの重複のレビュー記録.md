# 閉包を作るときに辿る文書IDの重複と、IDを読めない現在版のファイルのfixtureのレビュー記録

[適合fixture仕様 §6.20](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#620-閉包を作るときに辿る文書idの重複とidを読めない現在版のファイル)の
`SINGLE-177-01`〜`SINGLE-177-13`と、[§7](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#7-最小matrix-複合ワークスペース)の
`MULTI-065-01`〜`MULTI-065-08`（置き場は`fixtures/conformance/multi/`）を扱う。いずれもレビュー済みの期待値であり、Coreの挙動を観測したものではない
（[ADR-051](../../../docs/02.設計書/10_決定記録/ADR-051_適合fixtureの変更手続きを確定する.md)の追加）。
生成器と監査は`fixtures/conformance/duplicate_closure_fixtures.py`である。

## 追加の理由

実装の確認事項C96とC105に対応する。ユーザーの決定により、規範を明記した（コミット`5173c4b6`）。Coreは、同じ作業の別のコミットで直した。単体試験は
`tests/bitz-core/test_duplicate_closure_ids.py`と`tests/bitz-core/test_check_unreadable_id_base_path.py`が押さえる。

- C96: 文書IDが重複したファイルは、どちらも索引に入らない。閉包を作るときに重複したIDを黙って辿らず、逆参照の`refines`で閉包に入る`TECH-002`が2つあっても、
  `context REQ-001 --purpose verify`と`verify REQ-001`は`passed`を返した（`check REQ-001`は`failed`）。起点が重複すると`CTX-ROOT-MISSING-001`だけを返した。
  複合ワークスペースの`check`は、他のメンバーが所有する重複を返さなかった。
- C105: 現在版でフロントマターが不正になりIDを読めないファイルは索引に入らないため、引数なしの`check`は基準版の文書を削除として`SPEC-STATE-TRANSITION-001`で返し、
  依存元へ`SPEC-IMPACT-OUTDATED-001`を返し、そのファイル自身の`SPEC-FM-SCHEMA-001`を返さなかった。
- 既存のfixtureは、重複（`SINGLE-015`、`MULTI-056-04`・`05`）と削除（`SINGLE-029`、`SINGLE-158`、`MULTI-018-01`・`02`、`MULTI-030-01`、`MULTI-048-07`・`09`）を押さえるが、
  閉包を作るときに辿る重複と、同じパスの破損は押さえていなかった。期待値は変えていない。

## 根拠の規範文

- 関係・トレースモデル §5.1: 文書IDの重複は、`context`、`verify`、`check`のどれでも、閉包を作るときに辿るID（起点、`requires`、`refines`、`addresses`、置換の参照先、
  逆参照で閉包に入る文書のID。`related`の参照先は含めない）が重複していれば、その結果（`verify`は当該の検証対象）へ返す。起点のIDが重複している場合は`CTX-ROOT-MISSING-001`に併記する。
  閉包と無関係な重複は、`check`の完全検査の対象にだけ返す。診断の文言と発生元は`check`の完全検査と同じ（複合ワークスペースでは所有ワークスペース）。
- `check` §5、文書・フロントマター・状態仕様 §9: 基準版の文書と同じパスに、現在版でIDを読めないファイルが存在する場合は削除とせず、その文書の状態遷移、承認済み要求の保護、
  影響候補の比較も行わない。そのファイル自身の診断は、引数なしの`check`でも変更されたパスの診断として返す。IDでもパスでも対応しない場合（パスの変更と破損が同時の場合を含む）は削除とする。
- 結果・診断・終了コード §7: 診断は発生元のワークスペースID、`path`、`code`の辞書順（文字コード順）。重複した文書の発生元は、パスの辞書順で最初の写し（`<ID>-copy.md`は`<ID>.md`より前）。
- 診断レジストリ: `DOC-ID-DUPLICATE`（`SPEC-ID-DUPLICATE-001`）、`FM-YAML-SYNTAX`（`SPEC-FM-SCHEMA-001`）、`SPEC-STATE-TRANSITION-001`、`SPEC-IMPACT-OUTDATED-001`。

## 入力と起動

| fixture | 入力 | 結果 | 修正前のCore |
|---|---|---|---|
| `SINGLE-177-01` | `TECH-001`を`refines`する`TECH-002`が2ファイル。`context REQ-001 --purpose verify` | `failed`／1。重複の1件 | `passed`／0 |
| `SINGLE-177-02` | 同上。`verify REQ-001` | `failed`／1。検証対象に重複の1件 | `passed`／0 |
| `SINGLE-177-03` | 同上。`check REQ-001`（対照） | `failed`／1。重複の1件 | 同じ |
| `SINGLE-177-04` | 起点`REQ-001`が2ファイル。`context` | `failed`／1。`CTX-ROOT-MISSING-001`と重複 | 前者だけ |
| `SINGLE-177-05` | 同上。`verify REQ-001` | `failed`／1。検証対象に前者と重複 | 前者だけ |
| `SINGLE-177-06` | `REQ-001`が`requires`する`TECH-003`が2ファイル。`context` | `failed`／1。`SPEC-RELATION-MISSING-001`と重複 | 前者だけ |
| `SINGLE-177-07` | `REQ-001`を`related`で指すだけの`TECH-009`が2ファイル。`verify`（対照） | `passed`／0 | 同じ |
| `SINGLE-177-08` | `SINGLE-168-03`の入力に、`related`の参照先`ADR-099`が2ファイル。`verify`（対照） | `passed_with_warnings`／0。参照切れの警告だけ | 同じ |
| `SINGLE-177-09` | `SINGLE-042`の入力に、無関係な`TECH-008`が2ファイル。`context`（対照） | `SINGLE-042`と同じ | 同じ |
| `SINGLE-177-10` | `REQ-001`の`title`が不正なYAML（基準版は`approved`）。`check` | `failed`／1。`SPEC-FM-SCHEMA-001`の1件だけ | 削除と影響候補。自身の診断なし |
| `SINGLE-177-11` | 同上。`check --full` | `failed`／1。`SPEC-FM-SCHEMA-001`と`SPEC-RELATION-MISSING-001` | 削除も返す |
| `SINGLE-177-12` | `REQ-001.md`を削除し、`REQ-001-moved.md`に不正な文書。`check` | `failed`／1。自身の診断、削除、影響候補 | 自身の診断なし |
| `SINGLE-177-13` | `REQ-001`を`outdated`へ（読める変更）。`check`（対照） | `passed_with_warnings`／0。影響候補 | 同じ |
| `MULTI-065-01` | `platform::REQ-001`を`refines`する`web::TECH-005`が2ファイル。`context REQ-001` | `failed`／1。`web`が所有する重複 | `passed`／0 |
| `MULTI-065-02` | 同上。`verify REQ-001` | `failed`／1。検証対象に重複 | `passed`／0 |
| `MULTI-065-03` | 同上。`check REQ-001` | `failed`／1。重複 | `passed`／0 |
| `MULTI-065-04` | 同上。`verify --all-workspaces` | `failed`／1。`platform`の検証対象に重複 | `passed_with_warnings`／0 |
| `MULTI-065-05` | `platform::REQ-001`が2ファイル。`context web::TECH-010` | `failed`／1。`platform`が所有する重複と`SPEC-RELATION-MISSING-001` | 後者だけ |
| `MULTI-065-06` | `REQ-001`が`related`で指す`web::TECH-007`が2ファイル。`check REQ-001`（対照） | `passed_with_warnings`／0。重複を返さない | 同じ |
| `MULTI-065-07` | 無関係な`web::TECH-008`が2ファイル。`check REQ-001`（対照） | `passed`／0 | 同じ |
| `MULTI-065-08` | `web::TECH-001`の`title`が不正（基準版は有効）。`check --all-workspaces` | `failed`／1。`web`に`SPEC-FM-SCHEMA-001`だけ | 削除も返す |

欠陥の14件は修正前のCoreが失敗し、対照の7件は通る。修正前のCoreは、`git archive origin/main`の`plugins/bitz-core`で確かめた。

- **1つの原因だけを持つ**。重複のケースは、重複した文書の内容が同じ2ファイルで、閉包に入る経路は1つ（逆参照、起点、`requires`、`refines`のいずれか）だけである。
  対照は、重複した文書を置いたまま、辿る関係の種類（`related`）か、閉包との距離（無関係）だけを替える。
- **発生元は所有ワークスペースの相対パス**。複合ワークスペースでは、`summary`の文書IDを所有ワークスペースで修飾する（`web::TECH-005`）。`MULTI-065-05`は、重複を所有する`platform`が
  作業ワークスペース`web`と異なる。
- **範囲外の挙動は固定しない**。閉包と無関係な重複を、単一ワークスペースの`check`の明示対象と引数なしに常に返す今の挙動（`_ALWAYS_KEEP_CATALOG_CODES`）、`addresses`の参照先の重複、置換の参照先は、
  fixtureでは押さえず、単体試験が押さえる。
- 同じパスの破損のケースは、`SINGLE-177-12`だけが削除を期待する。パスの変更と破損が同時に起きた場合は、IDでもパスでも対応しないので削除（`check` §5）である。

## 診断の文言

承認済みの文言だけを使い、新しい文言はない。

| 対象 | 文言 | 出典 |
|---|---|---|
| 文書IDの重複 | 文書ID ＜ID＞が重複しています（複合ワークスペースでは`ws::ID`） | 承認済み（`SINGLE-015`、`MULTI-056-04`が使う） |
| 起点の不在 | 起点＜起点＞が存在しません | 承認済み（`SINGLE-111`などが使う） |
| 強い関係の参照先の不在 | 強い関係の参照先が存在しません | 承認済み（`SINGLE-075-02`が使う） |
| `related`の参照切れ | 関係型relatedの参照先が存在しません | 承認済み（`SINGLE-168`が使う） |
| フロントマターのYAMLの構文の不正 | フロントマターのYAMLの構文が不正です | 承認済み（`SINGLE-086`が使う） |
| 削除 | 管理済みの仕様文書が削除されています | 承認済み（`SINGLE-029`が使う） |
| 影響候補 | ＜依存元＞が強く依存する＜変更＞が変更されています。再確認してください | 承認済み（`SINGLE-033`が使う） |

## 監査

- `duplicate_closure_fixtures.py`の`reference_duplicates`は、入力の木構造だけから、起点の閉包を作るときに辿る重複したID（起点、`requires`の推移、`refines`の参照先、起点から推移的な逆参照、
  置換の後継。`related`は辿らない。写しのどれか1つでも辿れば辿る）を求め、期待する重複の診断の集合と一致することを要求する。`reference_base_comparison`は、基準版と現在版の入力から、
  削除とみなす文書のパスとIDを読めないファイルのパスを求め、期待する削除と`SPEC-FM-SCHEMA-001`の診断と一致することを要求する。どちらもCoreを呼ばない。
- 回帰試験（`fixtures/test_conformance_audit.py`）は、リテラルの期待、参照計算の規則、期待結果・起動条件・入力・副作用の改変と、修正前のCoreの出力への取り違えの拒否を押さえる。
- 総数の期待値（696件から717件）の更新は別のコミットにする。Gate AとGate Bの再認定は、この作業の外である。
