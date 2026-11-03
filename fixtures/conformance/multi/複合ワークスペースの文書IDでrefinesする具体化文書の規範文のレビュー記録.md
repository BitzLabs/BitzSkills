# 複合ワークスペースの文書IDでrefinesする具体化文書の規範文のfixtureのレビュー記録

[適合fixture仕様 §7](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#7-最小matrix-複合ワークスペース)の
`MULTI-055-01`〜`MULTI-055-04`を扱う。いずれもレビュー済みの期待値であり、Coreの挙動を観測したものではない
（[ADR-051](../../../docs/02.設計書/10_決定記録/ADR-051_適合fixtureの変更手続きを確定する.md)の追加）。
生成器と監査は`fixtures/conformance/multi_document_refines_fixtures.py`である。単一ワークスペースの対は
[文書IDでrefinesする具体化文書の規範文のレビュー記録](../single/文書IDでrefinesする具体化文書の規範文のレビュー記録.md)に記録した。

## 追加の理由

確認事項C54（単一ワークスペースの記録と同じ）。複合ワークスペースでは、別のワークスペースの文書が起点の文書を修飾した文書ID（`platform::REQ-001`）で`refines`する構成が自然に起きる。
修正前のCoreは、その文書の規範文を対象規範文に含めず、`verify`はその文書の未テストの`MUST`を通し、そのテスト割当ても実行しなかった。既存のfixture（`MULTI-044-03`、`MULTI-047-03`）は、
規範文IDで`refines`する構成だけを使い、この欠陥を押さえていなかった。

## 根拠の規範文

- 関係・トレースモデル §6.4の規則1・2と具体化文書の段落（見つけた具体化文書は規範文IDと文書IDの両方の`refines`で辿り、起点の文書自身から文書IDで辿るのは規則1だけ）、
  §6.1の4.・末尾、`context` §4・§10、`verify` §8: 単一ワークスペースの記録と同じ。
- 複合ワークスペース仕様 §4・§6: 他のワークスペースの文書も、修飾した文書IDで`refines`できる。機械可読な結果の文書`id`、規範文ID、`roots`は修飾IDで返す。
  `resolution.crossWorkspaceEdges`は`refines`を含み、`source`は修飾した文書ID、`target`は修飾した文書IDまたは規範文ID。`resolution.workspaces`は起点ワークスペースを先頭、以降はID辞書順。
- `verify` §7（確認事項C62）: テスト割当ての実行は、ルートワークスペースを先頭に、以降をワークスペースIDの辞書順とし、`commands[]`と`bindingRefs`も同じ順に並べる。
- 診断の`source.workspaceId`は規範文を所有するワークスペース、`path`はそのワークスペースのルートからの相対パス（`MULTI-047-03`）。`summary`のIDは修飾する（ADR-062、確認事項C47・C65）。

## 入力と起動

ルート`platform`（`.`、コマンド`p`）、メンバー`web`（`apps/web`、コマンド`t`）。`platform`の`REQ-001`（`approved`、規範文`AC-01`の`MUST`1件、コマンド`p`のテスト対応）を、
`web`の`TECH-010`（`approved`、規範文`C-01`の`MUST`1件）が`relations.refines: [platform::REQ-001]`（修飾した文書ID）で具体化する。すべてコミットし、`.`で`--format json`を指定して起動する。

| fixture | 引数 | `web::TECH-010`のテスト対応 | 期待 |
|---|---|---|---|
| `MULTI-055-01` | `context platform::REQ-001 --purpose verify --detail compact` | あり（コマンド`t`） | `passed`／0。制約台帳とカバレッジに2件。横断のエッジは`refines`の1件 |
| `MULTI-055-02` | `verify platform::REQ-001` | なし | `blocked`／2。`statements`は2件、`CTX-COVERAGE-TEST-001`（`web`）、テストを開始しない |
| `MULTI-055-03` | `verify platform::REQ-001:AC-01`（対照） | なし | `passed`／0。`statements`は1件、`platform::p`が通る |
| `MULTI-055-04` | `verify platform::REQ-001` | あり | `passed`／0。`statements`は2件、`platform::p`、`web::t`の順に通る |

## 期待値の導き方（Coreの出力を根拠にしない）

1. **閉包**。`platform::REQ-001`と、それを文書IDで`refines`する`web::TECH-010`の2文書（`documentCount`は2）。`web::TECH-010`は役割`refinement`、`reachedBy`は`refines:web::TECH-010`。
2. **対象規範文**。規則1から、文書を起点にした`01`、`02`、`04`は`platform::REQ-001:AC-01`、`web::TECH-010:C-01`。規則2から、規範文を起点にした`03`は前者だけ
   （起点の所有文書`platform::REQ-001`を文書IDで`refines`する`web::TECH-010`は、辿る起点にしないので含めない）。
   参照計算は、`multi_crosscheck`の関係の修飾（`relations`）を使って、§6.4の規則による計算と、文書IDの`refines`を使わない（修正前の）計算を別に書き、欠陥のケースでは後者が前者の真部分集合に、対照では同じになることを要求する。
   この群の入力は、見つけた具体化文書の先を持たないので、途中のCoreの再現（`SINGLE-169-07`〜`09`が固定する）は必要としない。
3. **横断のエッジ**。`01`は`{refines, web::TECH-010, platform::REQ-001}`の1件。参照計算は`multi_related_advisory_fixtures.reference_edges`（閉包の文書が宣言する、別のワークスペースへ向かい解決できる強い関係）で導く。
4. **カバレッジと診断**。`01`は目的`verify`で、2件の`MUST`がどちらもテスト済みなので診断は0件。`unaddressed`は目的`verify`の形（`MULTI-054-01`と同じく`addressed`は空）。
   `02`は`web::TECH-010:C-01`の未テストの`MUST`で`CTX-COVERAGE-TEST-001`（`blocked`、`source`は`{file, web, .spec/technical/TECH-010.md}`）。
5. **コマンド**。`04`は`platform::p`（`tests/p.py`、`covers`は`platform::REQ-001:AC-01`）を先頭に、`web::t`（`tests/t.py`、`covers`は`web::TECH-010:C-01`）の順（C62）。
6. **ハッシュ値**。独立に書いた2系統の参照計算（リテラルのA、`multi_crosscheck`の木構造からの導出B）のバイト列の一致を要求する。到達ワークスペースは`platform`、`web`（起点ワークスペースが先頭）。
   対象規範文は材料に入らないので、修正前のCoreと同じ値になる（実際に差分はなかった）。`web`のコマンド`t`は、`web::TECH-010`のテスト対応があるとき（`01`、`04`）だけ材料に入る。

## 規範から決まらず、既存の慣例と仕様の該当箇所で決めた点

1. **`01`を目的`verify`とし、`web::TECH-010`をテスト済みにする**。目的`verify`で`MUST`が未テストなら`context`は`blocked`になる。この群は`blocked`の経路を`verify`の`02`で固定し、`context`の`01`は
   ハッシュ値と制約台帳の形を診断なしで固定する。参照計算Bの`multi_crosscheck`は目的によらずテスト割当てを材料に入れるので、目的`implement`の材料を導けない（`MULTI-054`と同じ）。
   `--detail compact`は文書を参照の提示形式にし、本文の再掲を避ける（`MULTI-042-01`と同じ。提示はハッシュ値に影響しない）。
2. **`blocked`の検証対象も`contextDigest`を持つ**（`02`）。`SINGLE-060`と同じ。
3. **規範文を起点にした場合の閉包に`web::TECH-010`が入り、`contextDigest`の材料になる**（`03`）。単一ワークスペースの記録の3.と同じ根拠（§6.1の4.と規則2）。
4. **ルートの設定にコマンド`p`を足す**。`platform::REQ-001`のテスト対応を持たせ、`02`の`blocked`が`web::TECH-010:C-01`だけに由来するようにした。
5. **Stepの割当て**。4件ともStep 5（複合ワークスペース）。

## 検証の記録

- 修正後のCore（このブランチ）では、4件すべてが`passed`となる。期待値は規範から導いたもので、Coreに合わせて曲げていない。食い違いはなかった。
- 修正前のCore（`origin/main`の`plugins/bitz-core`）では、`MULTI-055-01`、`02`、`04`が失敗し、対照の`MULTI-055-03`が通る。
  `01`は制約台帳とカバレッジが1件だけ、`02`は`statements`が1件だけで`passed`／0、`04`は`statements`と`commands`が1件だけ（`web::t`を実行しない）になる。
