# 複合ワークスペースのコマンドのcwdの所有領域のfixtureのレビュー記録

[適合fixture仕様 §7](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#7-最小matrix-複合ワークスペース)の
`MULTI-051-01`〜`MULTI-051-06`を扱う。いずれもレビュー済みの期待値であり、Coreの挙動を観測したものではない
（[ADR-051](../../../docs/02.設計書/10_決定記録/ADR-051_適合fixtureの変更手続きを確定する.md)の追加）。
生成器と監査は`fixtures/conformance/multi_command_cwd_fixtures.py`である。単一ワークスペースの対は[コマンドのcwdの字句と所有領域のレビュー記録](../single/コマンドのcwdの字句と所有領域のレビュー記録.md)に記録した。

## 追加の理由

複合ワークスペースでも、コマンドの`cwd`の所有は判定されていなかった。`../..`、絶対パス、所有領域の外へ解決するシンボリックリンク、
およびルートワークスペースの`cwd`がメンバーのルートの配下を指す場合に、`verify`はテストのコマンドを所有領域の外で起動していた。実装の確認事項C82・C86に対応する。

## 根拠の規範文

- 複合ワークスペース仕様 §5・§5.1: コマンドの`cwd`のシンボリックリンクは、同じ所有領域内へ解決する場合だけ許可する。ルートワークスペースの`cwd`は、
  実パスがメンバーのルートの配下にあれば所有領域の外とする。違反は診断`SPEC-MULTI-OWNERSHIP-001`とし、`verify`がテスト割当ての起動前に判定する。違反したテスト割当ては起動せず、
  独立したテスト割当てを続ける。字句の違反は設定の検査で診断`SPEC-CONFIG-SCHEMA-001`とする。
- ワークスペース・設定仕様 §6: `cwd`の字句の規則。診断レジストリの`MULTI-OWNERSHIP-CWD`（番号491、`SPEC-MULTI-OWNERSHIP-001`、`error`／`failed`、`skip-binding`）。
- `verify` §5.1: `source`は設定ファイルの`verify.commands.<名前>.cwd`。§6: `skip-binding`の診断は、複合ワークスペースではテスト割当てを所有するワークスペースへ1件だけ置き、
  影響を受ける検証対象は診断を複製せず、状態を`blocked`、`bindingRefs: []`とする。
- 結果・診断・終了コード §2・§3: 最上位と各ワークスペースの状態は最悪値の集約。`failed`は終了コード1。`multiWorkspace.id`を`null`にするのは、全体事前検査でルートの設定の構文、型などにより
  有効な同一性を構成できないときである（複合ワークスペース仕様 §9）。
- 診断の文言（ユーザー承認済み）: 所有の違反は既存の「パス<cwdの値>の解決先がワークスペース<ID>の所有領域の外です」、字句の違反は「作業ディレクトリのパスの形式が不正です」。

## 入力と起動

基本のリポジトリは、ルート`platform`（`.`）とメンバー`web`（`apps/web`）で、すべてコミットし、`--format json`で起動する。どちらもコマンド`t`（`/bin/true`と`{tests}`）を持ち、
`platform`の`REQ-001`（テスト`tests/test_platform.py`）と`web`の`REQ-101`（テスト`apps/web/tests/test_web.py`）が、それぞれ自身の所有領域のテストを`tests`で宣言する。

| fixture | 引数 | `platform`の`cwd` | `web`の`cwd` | 結果 |
|---|---|---|---|---|
| `MULTI-051-01` | `verify --all-workspaces` | `apps/web` | `.` | `failed`／1。`platform`に所有の違反、`web::t`は実行して`passed` |
| `MULTI-051-02` | `verify platform::REQ-001` | `lk`（`lk -> apps/web`） | `.` | `failed`／1。最上位に所有の違反 |
| `MULTI-051-03` | `verify --all-workspaces` | `.` | `esc`（`esc -> ../..`） | `failed`／1。`web`に所有の違反、`platform::t`は実行して`passed` |
| `MULTI-051-04` | `verify --workspace web web::REQ-101` | `.` | `esc` | `failed`／1。最上位に所有の違反 |
| `MULTI-051-05` | `verify --all-workspaces` | `/tmp` | `.` | `error`／3。`SPEC-CONFIG-SCHEMA-001`、`workspaces`は空 |
| `MULTI-051-06` | `verify --all-workspaces` | `tests` | `tests` | `passed`／0（対照） |

## 規範から決まらず、既存の慣例と仕様の該当箇所で決めた点

1. **全体の`verify`で診断を置く場所**。`skip-binding`の診断は、単独の`verify`（ワークスペースの配列を持たない）では最上位の`diagnostics`、`--all-workspaces`ではテスト割当てを所有する
   ワークスペースの`diagnostics`に置く（`verify` §6の文）。結果・診断・終了コード §2も、最上位の`diagnostics`はカタログ、ワークスペースをまたぐ関係、集約そのものの診断だけを持つとする。
   `MULTI-051-01`と`03`は、違反したワークスペースの`diagnostics`に1件置く。
2. **違反したワークスペースと検証対象の状態**。診断の結果への効果が`failed`なので、ワークスペースは`failed`（最悪値）。検証対象は、`verify` §6の「いずれの場合も、影響を受ける検証対象は診断を複製せず、
   状態を`blocked`、`bindingRefs: []`とする」の文に従い`blocked`にした。`contextDigest`は、コンテキストを解決できているので持つ。最上位は`failed`／1。
   この文は`blocked`の診断を想定して書かれており、`failed`の`skip-binding`（`MULTI-OWNERSHIP-CWD`だけ）の検証対象の状態は、文面どおりに読んだ。
3. **`cwd`の違反とテストが`cwd`の配下にないことが重なる場合**。`MULTI-051-01`と`02`の`platform`のテストは、自身の所有領域の`tests/test_platform.py`であり、`cwd`（メンバーの配下）の配下にない。
   メンバーの配下に`platform`のテストを置くと、テストの所有境界の違反（別の診断）になるため、重なりは避けられない。`cwd`自身が所有領域の外であれば、`cwd`を前提とするテストの配下の判定には進まず、
   `cwd`の違反の1件だけを返すと決めた（`cwd`の判定は、テストのパスと`cwd`の包含の判定の前提であるため）。診断レジストリの優先順位でも、`MULTI-OWNERSHIP-CWD`（491）は`VERIFY-TEST-OUTSIDE-CWD`（608）より小さく、主診断になる。
   `MULTI-051-03`と`04`のメンバーの`cwd`（`esc -> ../..`）は、リポジトリのルートへ解決し、`web`のテストの正規パスはその配下にあるので重ならない。
4. **字句の違反の`multiWorkspace.id`**。`MULTI-051-05`は、`workspace.id`を明示した有効なルートの設定でも、`cwd`の字句の違反は設定の検査（`SPEC-CONFIG-SCHEMA-001`）で止まる。同じ診断コードの
   `SINGLE-126-01`（単一）が`workspace.id: null`であること、複合ワークスペース仕様 §9の「型が不正で有効な同一性を構成できない」に倣い、`multiWorkspace`は`{id: null, path: .}`、
   `source.workspaceId`は`null`、`workspaces`は空配列にした。`revision`はコミットありなので`{commit, dirty}`（`verify`の全体事前検査の停止。`MULTI-049-01`と同じ考え方）。
5. **単独の`verify`の`workspace`**。`MULTI-051-02`は`{platform, .}`、`MULTI-051-04`は`{web, apps/web}`（結果・診断・終了コード §2。`MULTI-039-01`と同じ）。

## 期待値の導き方（Coreの出力を根拠にしない）

- 違反の有無は、準備手順の後の入力から導く参照計算（`reference_violations`）が、設定の`cwd`と`realpath`から、字句の違反、自身のルートの外、ルートワークスペースがメンバーのルートの配下を指す、の順に判定し、
  fixtureが名乗る違反と一致することを要求する。起動するテスト割当ては違反していないワークスペースのもの（全体の`verify`のとき）だけである。
- 検証対象のハッシュ値は、リテラルのA（`multi_verify_fixtures`の材料の組み立てを再利用）と、入力の木構造から導くB（`multi_crosscheck`）のバイト列の一致を要求する。コマンドの`cwd`は材料に入る。
