# 複合ワークスペースのrelatedの参照切れの警告と横断のエッジのfixtureのレビュー記録

[適合fixture仕様 §7](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#7-最小matrix-複合ワークスペース)の
`MULTI-054-01`〜`MULTI-054-04`を扱う。いずれもレビュー済みの期待値であり、Coreの挙動を観測したものではない
（[ADR-051](../../../docs/02.設計書/10_決定記録/ADR-051_適合fixtureの変更手続きを確定する.md)の追加）。
生成器と監査は`fixtures/conformance/multi_related_advisory_fixtures.py`である。単一ワークスペースの対は
[contextとverifyのrelatedの参照切れの警告のレビュー記録](../single/contextとverifyのrelatedの参照切れの警告のレビュー記録.md)に記録した。

## 追加の理由

- C78: `related`の参照切れの警告は、`check`が返していたが、`context`と`verify`は捨てていた。複合ワークスペースの`context`と`verify`も同じである。
  既存のfixtureは複合ワークスペースの`related`の参照切れを使っていなかったので、この欠陥を押さえていなかった。
- C79: 複合ワークスペース仕様 §6と`context`のフィールド表は、`resolution.crossWorkspaceEdges`の`relation`に`related`を含めていたが、Coreは元から`related`を収録せず、
  `related`は閉包を増やさない（関係・トレースモデル §3）。ユーザーの決定で、`related`は解決できても横断のエッジに収録しないと規範に書き、結果のスキーマの列挙値からも外した。
  参照計算B（`multi_crosscheck`、`multi_closure_alias_fixtures`）も強い関係だけにした。

## 根拠の規範文

- 関係・トレースモデル §3、診断レジストリの`RELATION-TARGET-MISSING-RELATED`、`context` §10、`verify` §9: 単一ワークスペースの記録と同じ。
  参照先が別のワークスペースの文書（`platform::REQ-099`）でも、宣言する文書が起点ワークスペースの文書なら同じ警告を返す。
- 複合ワークスペース仕様 §6: `resolution.crossWorkspaceEdges`は`source`、`relation`、`target`の辞書順で、`related`は閉包を増やさないので、解決できても収録しない。
  参照先を解決できないエッジは収録しない。`relation`の列挙値は`requires`、`refines`、`addresses`、`supersedes`。
- 結果・診断・終了コード §4: `evidence`は参照先を宣言どおりの文字列で持つ（`platform::REQ-099`）。§7: 診断は`path`、`code`の辞書順。
- `MULTI-038-08`（`context`）と`MULTI-038-09`（`verify`）: 複合ワークスペースの強い関係の参照切れの形。起点を所有するワークスペース（`web`）が`workspace`になり、
  失敗の`context`は`resolution.workspaces`を起点ワークスペースの1件、`crossWorkspaceEdges`を空にする。

## 入力と起動

ルート`platform`（`.`）、メンバー`web`（`apps/web`）、`api`（`services/api`）を、この順で宣言する。3文書（`platform::REQ-001`、`web::REQ-101`、`api::REQ-201`）はいずれも
`approved`で規範文`AC-01`を1件持つ。`web`の`REQ-101`だけがテスト対応（コマンド`t`）を持つ。`REQ-101`は`platform::REQ-001`を`requires`し（横断の強い関係）、
`api::REQ-201`を`related`する（解決できる横断の`related`。`api::REQ-201`は閉包に入らない）。すべてコミットし、`.`で`--format json`を指定して起動する。

| fixture | 引数 | `REQ-101`の関係の宣言 | 期待 |
|---|---|---|---|
| `MULTI-054-01` | `context web::REQ-101 --purpose verify --detail compact` | `requires: [platform::REQ-001]`、`related: [api::REQ-201, platform::REQ-099]` | `passed_with_warnings`／0。警告1件、横断のエッジは`requires`の1件だけ |
| `MULTI-054-02` | `verify web::REQ-101` | 同上 | `passed_with_warnings`／0。検証対象の`diagnostics`に警告1件、コマンド`t`は通る |
| `MULTI-054-03` | `context web::REQ-101 --purpose verify --detail compact`（対照） | `requires: [platform::REQ-001]`、`related: [api::REQ-201]` | `passed`／0。診断0件、横断のエッジは`requires`の1件だけ |
| `MULTI-054-04` | `context web::REQ-101 --purpose verify --detail compact` | `requires: [platform::REQ-001, platform::REQ-098]`、`related: [api::REQ-201, platform::REQ-099]` | `failed`／1。診断2件（警告、強い関係の順） |

## 期待値の導き方（Coreの出力を根拠にしない）

1. **閉包**。`web::REQ-101`と、`requires`で到達する`platform::REQ-001`の2文書（`documentCount`は2）。`related`は閉包を増やさないので`api::REQ-201`は入らない。
   `platform::REQ-001`は`requires`の参照先の文書で、役割`requirement`、`reachedBy`は`requires:web::REQ-101`（`MULTI-042-01`と同じ形）。
2. **横断のエッジ**。参照計算は、閉包の文書が宣言する強い関係のうち、別のワークスペースへ向かい、解決できるものだけを列挙する。`MULTI-054-01`と`03`は
   `{requires, web::REQ-101, platform::REQ-001}`の1件で、同じ文書の解決できる横断の`related`（`api::REQ-201`）は含まない。失敗の`MULTI-054-04`は空（`MULTI-038-08`と同じ）。
3. **警告**。起点ワークスペース（`web`）の閉包の文書が宣言する関係を宣言の順に読み、解決できないものを診断にする。`source`は`{file, web, .spec/requirements/REQ-101.md, relations.related}`、
   `evidence`は`platform::REQ-099`。強い関係の診断は`relations.requires`、`evidence`は`platform::REQ-098`。リテラルの期待値との一致を要求する。
4. **ハッシュ値**（`01`〜`03`）。独立に書いた2系統の参照計算（リテラルのA、`multi_crosscheck`の木構造からの導出B）のバイト列の一致を要求する。
   材料の`crossWorkspaceEdges`は`requires`の1件、`relations.related`は宣言のまま（`01`と`02`は`api::REQ-201`と`platform::REQ-099`、`03`は`api::REQ-201`）。到達ワークスペースは`web`、`platform`
   （起点ワークスペースが先頭）。`platform`と`web`の2つの設定だけを持ち、`api`は到達しないので入らない。
5. **修正前のCoreの再現**。`context`と`verify`は警告を捨てる。警告を持つ3件（`01`、`02`、`04`）は期待値と異なり、対照の`03`は同じであることを要求する。

## 規範から決まらず、既存の慣例と仕様の該当箇所で決めた点

1. **他のワークスペースの閉包の文書が宣言する`related`の参照切れ**は、この群で固定しない。関係・トレースモデル §6.3と`context` §3は、他のワークスペースの文書の「参照先の不在など」を検査しないと定めるが、
   これは強い関係の判定の範囲として書かれており、`related`の警告にも及ぶかは明記されていない。この群の警告は、起点ワークスペース（`web`）の文書が宣言するものだけにした。
   この群の参照計算は、他のワークスペースの文書の宣言を読まない。
2. **目的`verify`と`--detail compact`の使用**。参照計算Bの`multi_crosscheck`はテスト割当てのコマンドを目的によらず材料に入れるので、目的`interpret`の材料を導けない。
   目的`verify`に固定した。`--detail compact`は文書を参照の提示形式にし、本文とフロントマターの再掲を避ける（`MULTI-042-01`と同じ。提示はハッシュ値に影響しない）。
3. **失敗した検証対象の`statements`は空**と、失敗した`context`の`resolution.workspaces`の形は、既存のfixture（`MULTI-038-08`、`MULTI-038-09`）に合わせた。
4. **Stepの割当て**。4件ともStep 5（複合ワークスペース）。

## 検証の記録

- 修正後のCore（このブランチ）では、4件すべてが`passed`となる。期待値は規範から導いたもので、Coreに合わせて曲げていない。食い違いはなかった。
- 修正前のCore（`origin/main`の`plugins/bitz-core`）では、`MULTI-054-01`、`02`、`04`が失敗し、対照の`MULTI-054-03`が通る。
  `01`と`02`は状態が`passed`で警告が0件、`04`は診断が1件（`SPEC-RELATION-MISSING-001`だけ）になる。
