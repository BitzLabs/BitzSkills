# 複合ワークスペース全体の`doctor`のfixtureのレビュー記録

## 1. 目的

`doctor --all-workspaces`の全体事前検査が成功した後に、ルートワークスペースと全メンバーの、ワークスペースに固有の検査を実行し、
メンバーの非成功を正しい所有位置へ置いて、全体へ集約する公開契約を固定する。

## 2. ケース

| fixture | 独立した原因 | 必須確認 |
|---|---|---|
| `MULTI-026-01` | なし | ルートワークスペースを先頭、`api`、`web`のID順で3つのワークスペースを返し、ワークスペースに依存しない検査をメンバーへ複製しない |
| `MULTI-026-02` | メンバー`api`のテストコマンドで、実行ファイルが存在しない | `api`だけを`blocked`にし、後続の`web`を診断して、最上位を状態`blocked`、終了コード2へ集約する |

両ケースは、メンバーの配下を探索の開始位置とし、同じリポジトリのルートとルートワークスペースを発見できることも固定する。
`MULTI-026-02`は既定のテキスト出力を使い、最上位と全メンバーの検査項目の合計21件、メンバーの診断1件を、要約へ含める。

## 3. 入力と副作用

入力は、ルートワークスペースのカタログと、`api`、`web`の設定3件だけとし、仕様文書を置かない。`MULTI-026-02`だけが、
`api`の`verify.commands.backend.argv`へ、存在しない相対パスの実行ファイルを指定する。`doctor`はコマンドを実行せず、
両ケースとも、リポジトリ、Gitのインデックス、ホームディレクトリ、キャッシュ、一時ディレクトリを変更しない。

## 4. 期待値の根拠

- [`bitz doctor`仕様 §3](../../../docs/03.詳細設計/03_操作仕様/04_doctor.md#3-検査順序)
- [`bitz doctor`仕様 §7](../../../docs/03.詳細設計/03_操作仕様/04_doctor.md#7-結果)
- [複合ワークスペース仕様 §8](../../../docs/03.詳細設計/02_仕様文書モデル/05_複合ワークスペース仕様.md#8-全体操作の共通規則)
- [結果・診断・終了コード §2.3](../../../docs/03.詳細設計/00_共通契約/01_結果・診断・終了コード.md#23-doctorの全体結果)

## 5. 2026-10-11追記: プラグインの要求の判定（`MULTI-032`）

実装の確認事項C6（[ADR-061](../../../docs/02.設計書/10_決定記録/ADR-061_doctorのプラグイン要求の字句と判定を確定する.md)）に伴い、
`doctor --all-workspaces`にプラグインの要求を渡す場合を固定する。単一ワークスペースの12件は
[`doctor`のプラグインの要求のレビュー記録](../single/doctorのプラグインの要求のレビュー記録.md)に記録した。

| fixture | 独立した原因 | 必須確認 |
|---|---|---|
| `MULTI-032` | `--require-core-api ^2.0`（Core APIは`1.0`で、メジャーバージョンが異なる） | 最上位の`checks[]`は`core`、`plugin`（`blocked`）、`capability`（`passed`）、`git`、`catalog`の順で、`plugin`と`capability`は1回だけ。診断は最上位の`SPEC-DOCTOR-API-001`の1件で、メンバーの`checks[]`と`diagnostics[]`へ複製しない。状態は`blocked`、終了コード2 |

入力は`MULTI-026-01`と同じ（ルートワークスペース`platform`、メンバー`api`、`web`の設定3件だけ）で、`apps/web`で実行する。呼出しは
`doctor --all-workspaces --plugin bitz-sdd --plugin-version 1.2.0 --require-core-api ^2.0 --require-capability context.v1 --require-capability check.v1 --format json`である。

期待値の導き方（Coreの出力を根拠にしない）は次のとおりである。

1. `doctor`仕様 §3は、全体操作ではCore、プラグイン、対応機能、Git、カタログを最上位で1回検査し、同じ環境の診断をメンバーごとに複製しないと定める。
   ADR-061 Decision 4は、`plugin`と`capability`を最上位の`checks[]`に1回だけ置き、メンバーへ複製しないと定める。
2. 検査項目の並びは、`doctor`仕様 §4.1の「`core`の直後」に`plugin`、`capability`を置き、既存の`MULTI-026-01`の`git`、`catalog`の順を保つ。
3. `^2.0`は`>=2.0 <3.0`で、Core API `1.0`を満たさないので`SPEC-DOCTOR-API-001`（`blocked`）。`coreApi`は`1.0`、`required`は指定した`^2.0`。対応機能は満たすので`capability`は`passed`。
   発生元は`{kind: environment, component: "plugin", identifier: "bitz-sdd"}`。
4. 最上位の状態は`blocked`、終了コード2。**メンバーの結果は変わらない**: `doctor`仕様 §3は、Core、プラグイン、対応機能、Gitを「先行する検査項目の出力を必要としない」検査項目として
   可能な範囲で継続すると定め、全体事前検査を止める条件（カタログ、ID、パス、Gitの境界、非対応のメジャーバージョン、リソースの上限）にプラグインの要求を含めない。
   したがって`platform`、`api`、`web`の3つのワークスペースは`MULTI-026-01`と同じく`passed`で、診断を持たない。この読みは、継続の規則（§3）からの導出であり、メンバーの扱いを個別に明示した規範文はない。
5. `summary`の文字列は規範文が定めず、Coreの`messages.py`の文言を使った。規範文から導いた値ではない（単一ワークスペースの記録の5と同じ）。

固定しない範囲は、単一ワークスペースの記録の7と同じに加えて、全体事前検査が非成功（カタログの不正など）のときのプラグインの検査項目の有無、
要求の組合せが不完全な場合の全体結果、`--workspace`との併用である。

陰性対照として、修正前のCore（コミット`5927890b`）のコピーでは、`plugin`と`capability`の欠落、診断の欠落、状態`passed`で失敗した。

## 2026-10-12: Coreの出力文言の書換えに伴う期待値の訂正

Coreの出力文言の英語の一般語を表記規則 §3.5に沿って日本語にしたため、次のfixtureの期待値（診断の`summary`、manifestの説明、テキスト出力、
`resultDigest`のいずれか）を訂正した（ADR-062の期待値の訂正。管理者が対応表を承認）。入力、状態、終了コード、診断コード、発生元は変えていない。
承認済みの対応表と根拠は[Coreの出力文言のレビュー記録](../Coreの出力文言のレビュー記録.md)にまとめた。

- 対象: `MULTI-026-02`

## 2026-10-12: doctorの修復手順（`suggestedAction`）の追加に伴う期待値の訂正

`doctor`の診断に`suggestedAction`を付けたため（実装の確認事項C29。管理者が文言を承認）、次のfixtureの期待値を訂正した（ADR-062の期待値の訂正）。
入力、状態、終了コード、診断コード、重大度、発生元は変えていない。
承認済みの文言と根拠は[Coreの出力文言のレビュー記録](../Coreの出力文言のレビュー記録.md)の「PR-4（doctorの修復手順）」の節にまとめた。

- 対象: `MULTI-026-02`（メンバー`api`の`SPEC-DOCTOR-COMMAND-001`。`{name}`は`backend`。テキストの期待値に`  -> `の継続行を足した）、`MULTI-032`（最上位の`SPEC-DOCTOR-API-001`。`{required}`は`^2.0`）

## 2026-10-12: ルートのEARS-AIのメジャーバージョンの非互換で全体事前検査が止まる場合（`MULTI-033`）

### 追加の理由

実装の確認事項C31。`doctor --all-workspaces`は、ルートの設定の`earsAi`のメジャーバージョンが非互換のとき、全体事前検査（`multiws.precheck`）が
`check`用の`SPEC-EARS-VERSION-001`を最上位に返し、修復手順も付けていなかった。診断レジストリは、`doctor`のEARS-AIのメジャーバージョンの非互換を
別の条件`DOCTOR-EARS-VERSION`（`SPEC-DOCTOR-EARS-001`、`error`、`blocked`、発生元`file`、継続`skip-check`）として`EARS-SCHEMA-MAJOR`（操作は`context`、`check`、`verify`）と分けている。
このfixtureは、`doctor`が`doctor`のコードを返し、メンバーの診断を始めないことを固定する（ADR-051の追加。Coreの修正はコミット`5946271c`と、カタログの検査項目を`blocked`で置く`a7b8e9a5`）。
単一ワークスペースの`doctor`の`SPEC-DOCTOR-EARS-001`は、[Coreの出力文言のレビュー記録](../Coreの出力文言のレビュー記録.md)の PR-4 の節が「fixtureがなく単体試験で押さえる」とした範囲で、
このfixtureは全体操作の経路だけを固定する。

| fixture | 独立した原因 | 必須確認 |
|---|---|---|
| `MULTI-033` | ルートの設定の`earsAi`が`2.0`（Coreが対応するメジャーバージョンは1） | 診断は`SPEC-DOCTOR-EARS-001`の1件で、`SPEC-EARS-VERSION-001`を含まない。メンバーの診断を開始せず`workspaces`は空。最上位の`checks[]`は`core`、`git`（ともに`passed`）と`catalog`（`blocked`）。状態は`blocked`、終了コード2 |

### 入力

ルートワークスペース`platform`の設定（`earsAi: "2.0"`、`multiWorkspace.members`は`web`の1件）と、正しいメンバー`web`（`earsAi: "1.0"`）の2ファイルだけで、
仕様文書は置かない。`earsAi`以外はカタログとして正しい（`multi_reference.root_config`の最小のカタログと`earsAi`の値だけが異なる）。
Gitでコミット済み（`baseCommit`は全体）で、リポジトリのルートで`doctor --all-workspaces --format json`を実行する。

### 期待値の導き方（Coreの出力を根拠にしない）

1. 状態と終了コード: 診断レジストリの`DOCTOR-EARS-VERSION`は結果への効果が`blocked`、結果・診断・終了コード §3は`blocked`を終了コード2とする。診断はこの1件だけなので最上位も`blocked`。
2. 診断コード: `doctor`の条件は`SPEC-DOCTOR-EARS-001`（`doctor`仕様 §8、診断レジストリ §6）。`SPEC-EARS-VERSION-001`は`EARS-SCHEMA-MAJOR`（`context`、`check`、`verify`）のコードで、`doctor`の結果には含まれない。
3. メンバーの診断: `doctor`仕様 §3は、非対応のメジャーバージョンの全体事前検査が非成功ならメンバーの診断を開始しないと定める。複合ワークスペース仕様 §8は、非成功なら`workspaces: []`で結果を返すと定める。
   したがって`workspaces`は空配列で、`web`の結果も置かない。
4. 最上位の`checks[]`: `doctor`仕様 §3は、全体操作でCore、プラグイン、対応機能、Git、カタログを最上位で1回検査すると定める。プラグインの要求を渡さないので`plugin`と`capability`は置かない（§4.1）。
   `core`は`passed`。Gitは利用でき、リポジトリの境界を確定できるので`git`は`passed`。`doctor`仕様 §3は、ルートワークスペースの設定のスキーマまたはEARS-AIの
   メジャーバージョンが非対応で全体事前検査が止まった場合は、メンバーの非対応のメジャーバージョンと同じく、最上位に検査項目`catalog`を`blocked`で置くと定める
   （2026-10-12に明記。独立レビューで、当初の「`catalog`を置かない」の根拠が規範文から一意に導けないと指摘され、ユーザーが`blocked`で置く読みに決めた）。
   したがって`checks[]`は`core`（`passed`）、`git`（`passed`）、`catalog`（`blocked`）の順である。
5. `multiWorkspace`: 結果・診断・終了コード §2.3は、`id`を`null`にするのはルートの設定の構文、型、ID不正でIDを構成できない場合だけと定める。
   メジャーバージョンの非互換はこれに当たらないので、`id`は`platform`、`path`は`.`である。
6. 発生元: 診断レジストリの発生元は`file`。`{kind: "file", workspaceId: "platform", path: ".spec/bitz.yaml", key: "earsAi"}`。`key`は、単一ワークスペースの同種の診断（`SINGLE-095`の
   `SPEC-EARS-VERSION-001`）が設定キー`earsAi`を指すのと同じ形である。`workspaceId`はルートワークスペースの`platform`。
7. `summary`と`suggestedAction`: 管理者が承認した文言である。規範文から導いた値ではなく、Coreの出力を写した値でもない。
   `summary`は「未対応のEARS-AIのメジャーバージョンです」（[Coreの出力文言のレビュー記録](../Coreの出力文言のレビュー記録.md)の表の45番）、
   `suggestedAction`は「設定キーearsAiをCoreが対応するメジャーバージョン1に合わせてください」（同記録の PR-4 の承認済みの表）。

`multi_doctor_fixtures.py`は、ルートの設定の`earsAi`のメジャーバージョンだけから診断を導く参照計算（`reference_ears_precheck`）を持ち、リテラルの期待値との一致を要求する。
互換な値（`1.0`、`1.9`）では診断を導かない陰性対照を、監査の回帰試験に置いた。

### 固定しない範囲

- `schemaVersion`のメジャーバージョンの非互換（`SPEC-CONFIG-SCHEMA-001`）、メンバー側の非互換（`SPEC-MULTI-VERSION-001`）、`earsAi`が不正な形の場合。
- `HEAD`のスナップショットのルートの設定だけが非互換の場合と、`apps/web`など配下から実行した場合。
- `--workspace`を指定した`doctor`の`SPEC-DOCTOR-EARS-001`（単一ワークスペースの経路は単体試験で押さえる）。
- 診断の`summary`と`suggestedAction`の文字列を規範文で1つに定めること（ADR-062 Decision 4）。

### 陰性対照

修正前のCore（コミット`f5de9a43`）のコピーでは、診断が`SPEC-EARS-VERSION-001`（`suggestedAction`なし）で失敗する（検証の結果は報告に記す）。
カタログの検査項目を置く修正の直前のCore（コミット`bff2f546`の`multiws.py`）のコピーでは、`$/checks: 期待=length=3 実際=length=2`で失敗する。

## 2026-10-13追記: 複合ワークスペース内の`doctor --workspace`と`workspace.path`（`MULTI-035-01`〜`03`）

### 追加の理由（実装の確認事項C38）

複合ワークスペース仕様 §3の5.は、`--workspace <id>`がカタログ内のルートまたはメンバーのIDで作業ワークスペースを置き換えると定める。結果・診断・終了コード §2は、複合ワークスペース内のワークスペース単独操作が
実際のワークスペースIDとリポジトリのルートからの相対パスを返すと定める。既存の`doctor`のfixtureは、全体操作（`--all-workspaces`、`MULTI-019`、`MULTI-026-01`〜`02`、`MULTI-032`、`MULTI-033`）と、
単一ワークスペース（`SINGLE-*`）だけで、複合ワークスペース内の単独の`doctor`（`--workspace`の有無にかかわらず）を押さえていなかった。そこで、次の3件を加える。

| fixture | 実行ディレクトリ | 引数 | `workspace` |
|---|---|---|---|
| `MULTI-035-01` | `apps/web` | `doctor --workspace platform` | `platform`、パスは`.`（メンバーの中からルートへ切り替える） |
| `MULTI-035-02` | `.` | `doctor --workspace web` | `web`、パスは`apps/web` |
| `MULTI-035-03` | `apps/web` | `doctor` | `web`、パスは`apps/web`（`--workspace`なしは最寄りの設定のメンバー） |

### 根拠の規範文

- 複合ワークスペース仕様 §3: 最寄りの設定のワークスペースが作業ワークスペースになる（2・3）。`--workspace <id>`は作業ワークスペースを置き換える（5）。
- `doctor` §2・§3: `--workspace`は指定したワークスペースを診断する。検査順序の表は、検査6を「複合ワークスペースのカタログ、メンバー、パスの所有」とする。
  複合ワークスペースの中の単独の`doctor`は、全体事前検査が成功したときに、`config`の後、`schema`の前に検査項目`catalog`を置く（ユーザーの決定D4。単一ワークスペースの`doctor`は置かない）。
- `doctor` §7: 単独結果の`workspace`は`id`と`path`を持つ。結果・診断・終了コード §2: 複合ワークスペース内のワークスペース単独操作は、実際のワークスペースIDとリポジトリのルートからの相対パスを返す。
  ルートワークスペースのパスは`.`。

### 入力と期待値の導き方（Coreの出力を根拠にしない）

入力は3件で共通である。ルート`platform`のカタログ（メンバー`web`（`apps/web`）、`api`（`services/api`））と、メンバー2件の設定の3ファイルだけで、仕様文書とコマンドは置かない。Gitでコミット済み（`baseCommit`は全体）。

1. `workspace`: `01`は`--workspace platform`が最寄りの設定の`web`を置き換えて`{id: platform, path: .}`、`02`は`--workspace web`がルートの最寄りの設定を置き換えて`{id: web, path: apps/web}`、
   `03`は`--workspace`なしの最寄りの設定の`web`で`{id: web, path: apps/web}`。`path`はカタログのパス（リポジトリのルートからの相対）で、実行ディレクトリの相対パスや`.`ではない。
2. 検査項目: すべて通る構成（Python 3.12以上、設定が存在して適合、カタログとメンバーのパスが正しい、スキーマとEARS-AIのメジャーバージョンが1、Gitが利用でき、コマンドがない）なので、
   `core`、`workspace`、`config`、`catalog`、`schema`、`ears`、`git`、`command`は`passed`、影響候補の件数の`impact`は`info`（`doctor` §3）。順序は`doctor` §3の検査順序の表の順（9項目）。
   単一ワークスペースの`SINGLE-001`は`catalog`を置かない8項目である。診断は0件、状態は`passed`、終了コード0。
3. `core`は`version: 1.0.0`、`apiVersion: 1.0`、5つの対応機能（`doctor` §4、`SINGLE-001`と同じ）。

`multi_active_workspace_fixtures.reference_doctor`は、入力の木構造から作業ワークスペース（`select_workspace`）、そのパス、検査項目の状態（設定のメジャーバージョン、コマンドの実行ファイルの解決）を導き、
リテラルの期待値と照合する。`--workspace`が最寄りの設定と異なる（`01`、`02`）ことは`check_conditions`が確かめる。

### 固定しない範囲

- コマンドの実行ファイルまたは`cwd`の不在（`SPEC-DOCTOR-COMMAND-001`）、設定やバージョンの不適合は扱わない。診断を返さない構成だけで、作業ワークスペースの同一性（`id`と`path`）を固定する。
- 全体事前検査が失敗する複合ワークスペースでの単独の`doctor`（実装の確認事項C27）、`--workspace`が未知のIDの場合（`MULTI-005`の終了コード4）、`--workspace`と`--all-workspaces`の併用は扱わない。
- ルートの中から`--workspace platform`（最寄りの設定と同じ）と、メンバーからメンバー（`web`から`api`）の指定は扱わない。
- 修正前のCore（コミット`0cf697eb`の`plugins/bitz-core`を作業ツリーの外へ取り出した写し）は、`MULTI-035-01`と`02`は`--workspace`を受け付けず標準出力がJSONではなく、`MULTI-035-03`は`workspace.path`が`.`で失敗する（陰性対照）。
  修正後のCoreは3件とも通る。Coreの出力は期待値を決めた後に、一致を確かめるためだけに使った。
