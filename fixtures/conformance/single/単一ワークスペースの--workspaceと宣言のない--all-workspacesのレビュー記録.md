# 単一ワークスペースの--workspaceと宣言のない--all-workspacesのfixtureのレビュー記録

[適合fixture仕様 §6.14](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#614-単一ワークスペースの--workspaceと宣言のない--all-workspaces)の
`SINGLE-170-01`〜`SINGLE-170-08`を扱う。いずれもレビュー済みの期待値であり、Coreの挙動を観測したものではない
（[ADR-051](../../../docs/02.設計書/10_決定記録/ADR-051_適合fixtureの変更手続きを確定する.md)の追加）。
生成器と監査は`fixtures/conformance/workspace_selection_fixtures.py`である。

## 追加の理由

実装の確認事項C73・C64に対応する。

- **C73**: 単一ワークスペースの`--workspace`は、設定がない場合も、設定を読めずに同一性を構成できない場合も、値によらず終了コード4
  （「指定したワークスペースが見つかりません」）になり、`--workspace`を付けない場合の停止の結果を返さなかった。
  ユーザーの決定に基づき、Core実行環境・CLI基盤契約 §6は、単一ワークスペースの`--workspace`を、設定から構成した同一性と比べるものとし、設定がない場合と同一性を構成できない場合は
  値によらず比べず、`--workspace`を付けない場合と同じ停止の結果を返す（複合ワークスペース仕様 §3の5の、全体事前検査が非成功の場合と同じ扱い）と明記した。
  同一性を構成できる場合（既定値`root`、明示のID、スキーマまたはEARS-AIの版の非対応）は、従来どおり一致しない値を終了コード4とする。
- **C64**: `multiWorkspace`を宣言しない単一ワークスペースでも、`--all-workspaces`が成功していた。入れ子の`.spec`があれば、未登録の診断で`blocked`になった。
  複合ワークスペース仕様 §8は、構文、型、必須フィールド、IDの検査を通過したルートの設定（版の非対応の設定を含む）が`multiWorkspace`を宣言しなければ、`--all-workspaces`は複合ワークスペースを
  発見できない引数不正（終了コード4）とし、ルートの設定を読めない場合は、候補を発見した後の不適合として、全体事前検査の停止の結果を返すと明記した。

既存のfixtureは、`--workspace`では`SINGLE-127-14`（同一性を構成できる設定で、カタログにない値を`doctor`が拒否する）と`SINGLE-127-07`（空の値）だけで、
同一性を構成できない場合も、宣言のない`--all-workspaces`も押さえていなかった。複合ワークスペース側の`--all-workspaces`の停止の結果は、`MULTI-040-10`（`doctor`、アンカー）、
`MULTI-049-01`（`check`、上限の超過）、`MULTI-043`などが、宣言したルートの設定で固定している。

## 根拠の規範文

- Core実行環境・CLI基盤契約 §6: `--workspace`は、CLIが解決の基準とする値そのものなので、構文上は正しくてもカタログに存在しない値は終了コード4とし、操作の結果を作らない。
  単一ワークスペースでは、設定から構成したワークスペースの同一性と比べる。設定がない場合と、設定を読めずに同一性を構成できない場合は、値によらず比べず、`--workspace`を付けない場合と同じ停止の結果を返す。
- 結果・診断・終了コード §2: ワークスペースの同一性を構成する前に止まる原因は、設定を読めないこと（上限の超過、読取りの失敗、文字コードの不正）、設定の構文、型、必須の不正である。
  `workspace.id`は`null`で、`path`は候補のパス。版の非対応はこの列挙に含まれないので、同一性を構成できる（既定値`root`または明示のID）と読む。
- 診断レジストリ: `CONFIG-YAML-SYNTAX`・`CONFIG-FIELD-TYPE`は`SPEC-CONFIG-SCHEMA-001`（`error`／`error`）、`WORKSPACE-CONFIG-MISSING`は`SPEC-WORKSPACE-MISSING-001`
  （`context`・`check`・`verify`。`error`／`blocked`、発生元は環境）。結果の状態が`error`なら終了コード3、`blocked`なら2（結果・診断・終了コード §3）。
- 複合ワークスペース仕様 §8: `--all-workspaces`の受付と、宣言のないルートの設定、読めないルートの設定の扱い。同 §3の5: 全体事前検査が非成功なら停止の結果を返す。同 §3: `multiWorkspace`の宣言は、トップレベルのキーの有無で判定する（`MULTI-043-17`）。
- 結果・診断・終了コード §2・§3（`revision`）と`verify` §2（`scope`）: コミットのある単一ワークスペースの`verify`は`revision`に`commit`と`dirty`を持ち、引数ありは`scope: selected`。`check`は`--base`の指定がなければ`HEAD`を基準版とする。
- 引数不正は終了コード4で、結果もレポートも作らず、標準出力は空、標準エラー出力は1行（`bitz: <操作>: <理由>`）。理由の文字列は固定しない（`cli_error_fixtures.py`と同じ）。
- `doctor` §3: `SINGLE-170-02`の結果は`SINGLE-092`と同じ検査項目（`core`、`workspace`、`config`、`git`）を返す。`--workspace`の値は結果に現れない。

## 入力と起動

基本の入力は、既定値`root`の最小の設定（`schemaVersion`、`language: ja`、`earsAi`だけ。`workspace.id`も`multiWorkspace`もない）と`REQ-001`（`SINGLE-094`・`SINGLE-152`の系列の文書）で、
基準版のコミットを置く（`doctor`の`SINGLE-170-02`だけ、`SINGLE-092`と同じ準備手順でコミットを置かない）。`--format json`で起動する。

| fixture | 操作 | 入力 | 結果 |
|---|---|---|---|
| `SINGLE-170-01` | `check --workspace app --full --base HEAD` | 設定に`workspace: [`（閉じられていないフロー配列。YAMLの構文の不正） | `error`／3。`SPEC-CONFIG-SCHEMA-001`。`source`は`{file, null, .spec/bitz.yaml}`。`workspace`は`{null, .}` |
| `SINGLE-170-02` | `doctor --workspace app` | 設定の`language: 42`（`SINGLE-092`と同じ） | `error`／3。`SINGLE-092`と同じ結果 |
| `SINGLE-170-03` | `context REQ-001 --workspace app` | 基本の入力（対照） | 終了コード4 |
| `SINGLE-170-04` | `verify --workspace app REQ-001` | 設定がない（`REQ-001`だけ） | `blocked`／2。`SPEC-WORKSPACE-MISSING-001`の1件。`scope: selected`、`targetResults`と`commands`は空 |
| `SINGLE-170-05` | `check --all-workspaces --base HEAD` | 基本の入力 | 終了コード4 |
| `SINGLE-170-06` | `doctor --all-workspaces` | 基本の入力に、入れ子の`services/api/.spec/bitz.yaml`（`workspace.id: api`） | 終了コード4 |
| `SINGLE-170-07` | `verify --all-workspaces` | 基本の入力で`schemaVersion: "2.0"` | 終了コード4 |
| `SINGLE-170-08` | `check --all-workspaces --base HEAD` | `SINGLE-170-01`と同じ入力（対照） | `error`／3。全体事前検査の停止の結果。`multiWorkspace`は`{null, .}`、`workspaces`は空 |

`SINGLE-170-01`の`--workspace`の値は`app`にした。構成できる同一性（既定値`root`）とも一致しないので、修正前のCoreが終了コード4にすることを検出できる。
`SINGLE-170-01`と`08`は同じ入力で、`--workspace`の有無で停止の結果が変わらないこと（診断は同一）を固定する。

## 期待値の導き方（Coreの出力を根拠にしない）

1. **参照計算**。`reference_outcome`が、引数列と設定の本文から次を導く。
   - `--workspace`: `identity`が同一性を導く。設定がない、または同一性を構成する前に止まる不備（上限、文字コード、構文、禁止された構文、型）があれば`null`で、値を比べず停止の結果（`stop_kind`が設定の本文から
     停止の種類を導く）。構成できれば、既定値`root`または明示のIDと比べ、不一致は引数不正。
   - `--all-workspaces`: 設定を読めなければ停止の結果。構文、型、必須フィールド、IDの検査を通過した設定（版の非対応を含む）が`multiWorkspace`を宣言しなければ引数不正。設定がなければ発見できず引数不正。
   リテラルの期待値が、この結果の種類、診断のコード、状態、`summary`、`source`、`workspace`または`multiWorkspace`と一致することを、準備手順を2回適用したそれぞれで要求する。
2. **欠陥を検出できる入力であること**。`defective_outcome`が、修正前のCoreの読み方（`--workspace`は設定の有無・同一性の構成の可否にかかわらず比べる。`--all-workspaces`は宣言を見ない）を再現する。
   `01`・`02`・`04`〜`07`は修正前の結果が期待値と異なり、`03`と`08`は同じ（対照）であることを、`validate`が要求する。
3. **入力の構成**。`check_conditions`が、準備手順の後の入力から、設定の不備が意図した1か所だけであること、既定値`root`のケースが`workspace`も`multiWorkspace`も持たないこと、
   `--workspace`の値が構成した同一性と一致しないこと、入れ子の`.spec`の有無と、作業ツリーがコミット済みと同じであることを確かめる。
4. **副作用なし**。リポジトリ、`git status`、`HOME`、キャッシュ、`TMPDIR`の読取り専用の実行前後を固定し、準備手順を2回適用して固定したスナップショットと照合する。
5. **終了コード4の形**。`cli_error_fixtures.py`と同じ`cli-output.json`（終了コード4、標準出力は空、標準エラー出力は`bitz: <操作>: `で始まる1行）と、結果の状態を持たないマニフェスト
   （`expect`は終了コード、`stdout: none`、`reportFileCount: 0`だけ）を使い、共通のヘルパー`check_cli_error_output`で契約を動かして確かめる。

## 診断の文言

既存の承認済みのものだけを使った。

| 診断 | 文言 | 出典 |
|---|---|---|
| YAMLの構文の不正 | 設定YAMLの構文が不正です | `MULTI-057-02`（[Coreの出力文言のレビュー記録](../Coreの出力文言のレビュー記録.md)に承認済み） |
| 型の不正 | 設定キーlanguageは文字列で指定してください | `SINGLE-004-01`、`SINGLE-092` |
| 設定がない | .spec/bitz.yamlがありません | `SINGLE-094`、`SINGLE-152` |

## 規範から決まらず、既存の慣例と仕様の該当箇所で決めた点

1. **`SINGLE-170-01`に`--base HEAD`を付ける**。基準版のコミットがある`check`のfixtureは、明示の`--base`を持つ必要がある（`validate_conformance.py`のmatrix検査。`SINGLE-094`・`SINGLE-004-01`と同じ）。
   `--base`の既定は`HEAD`なので、挙動は`--base`なしと同じである。
2. **`SINGLE-170-02`はコミットを置かず、`SINGLE-092`と同じ準備手順にする**。`doctor`は`revision`を持たず、結果は`SINGLE-092`と同一にそろえるため。
3. **`SINGLE-170-03`の操作は`context`**。`--workspace`の対照を`doctor`（`SINGLE-127-14`）以外の操作でも置き、4操作が同じ判定を使うことを見るためである。起点は`REQ-001`だけで、目的は既定の`interpret`。
   終了コード4なので結果の内容は固定しない。
4. **`SINGLE-170-04`の`verify`は引数ありの`scope: selected`**。設定がなく検証対象を解決できなくても、`scope`は指定の有無で決まる（`SINGLE-167-01`の`verify REQ-001`の早期に返す結果と同じ）。
   `revision`はコミットがあるので`commit`と`dirty: false`（`SINGLE-165`の早期に返す結果と同じ）。診断は`SINGLE-152`（`context`）と同じ1件。
5. **`SINGLE-170-08`の`check --all-workspaces`の`multiWorkspace`は`{null, .}`**。ルートの設定の構文の不正で同一性を構成できないので、`id`は`null`（結果・診断・終了コード §2、`MULTI-049-01`と同じ形）。
   設定を読めない場合に`--all-workspaces`が受け付けられる根拠は、複合ワークスペース仕様 §8の「候補を発見した後の不適合」である。この設定は`multiWorkspace`を宣言していたかどうかも読めないため、
   引数不正にも宣言のない設定にもならない。
6. **設定を読めない場合を、構文の不正と型の不正の2つで固定する**。上限の超過、文字コードの不正、読取りの失敗、必須フィールドの不正は、`--workspace`で比べない規範が同じなので置かない
   （単体試験`tests/bitz-core/test_single_workspace_selection.py`が固定する）。
7. **Stepの割当て**。操作が実装される最初のStepに置く。`check`の設定の停止の`01`と`doctor`の`02`はStep 1、`context`の`03`はStep 3、`verify`の`04`はStep 4（`SINGLE-168`・`SINGLE-169`と同じく操作ごとに分けた）。
   `--all-workspaces`の`05`〜`08`は、複合ワークスペースの機能なのでStep 5に置いた。Step 5の完了条件には、`MULTI-001`〜`057`に加えて`SINGLE-170-05`〜`08`を足した。
8. **`SINGLE-170-05`〜`07`の入力に`REQ-001`を置く**。`SINGLE-127-14`が`SINGLE-042`の一式を使うのと同じ考え方で、引数不正の判定が文書の有無に依存しないことを示す。

- Gitがない場合、`_locate_root`は現在のディレクトリの設定を候補にするので、複合ワークスペースのメンバーの中からの`--all-workspaces`は、メンバーの設定
  （`multiWorkspace`がない）を候補にして、修正前は`SPEC-MULTI-GIT-001`の`blocked`／2（`multiWorkspace.id`はメンバーのID）を返していた。修正後は宣言がないので終了コード4になる。
  複合ワークスペース仕様 §3（Gitがなく最も近い設定が宣言しなければ単一ワークスペース）と§8（発見できなければ終了コード4）から導ける変化で、独立レビューの実測で確かめた。
  この群はGitのない入力を置かないので、fixtureでは固定しない。

## 検証の記録

- 修正後のCore（このブランチ）では、8件すべてが`passed`となる。期待値は規範から導いたもので、Coreに合わせて曲げていない。食い違いはなかった。
- 修正前のCore（`origin/main`のコミット`c4ff9233`の`plugins/bitz-core`）では、欠陥の`01`・`02`・`04`が終了コード4で結果を作らず、`05`が`root`だけを処理して`passed`／0で成功し、
  `06`が`SPEC-MULTI-UNREGISTERED-001`の`blocked`／2、`07`がスキーマの版の非対応の`blocked`／2を返して失敗する。対照の`03`と`08`は通る。
