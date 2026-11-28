# Gitの読取りの既知の問題とSHA-256のレビュー記録

## 2026-11-28: ADR-084のfixture（ADR-051の追加）

[ADR-084](../../../docs/02.設計書/10_決定記録/ADR-084_Gitの読取りの既知の問題を解消し、SHA-256のリポジトリに対応する.md)の決定1〜5について、
仕様だけから期待値を決められる部分のfixtureを加えた。決められない部分は、下の「置いていないもの」に挙げ、司令塔の判断を待つ。

### 準備の入力

- `setup.objectFormat`（`sha1`、`sha256`。既定は`sha1`）を、harness、マニフェストのスキーマ、監査の自己試験に加えた（適合fixture仕様 §3.1）。
  harnessは`git init --object-format`へ渡し、サブモジュールのリポジトリも親と同じ形式で作る。2回の準備で同じコミットIDになること、
  `sha256`で64桁、既定と`sha1`で40桁になることを自己試験で確かめる。
- `setup.git: false`で`objectFormat`を持つマニフェストは、スキーマとharnessで拒否する（Gitのリポジトリを作らないので形式を指定できない。§3.1は明記していない。解釈）。

### 加えたfixture

| ID | 入力 | 期待 | 根拠 |
|---|---|---|---|
| SINGLE-191-01 | `SINGLE-001`の入力を`objectFormat: sha256`のリポジトリにコミットする。`doctor` | `SINGLE-001`と同じ（`passed`／0） | Core実行環境・CLI基盤契約 §4、`doctor` §6（コミットのあるリポジトリでGitの読取りが成功する）、ADR-084の決定5 |
| MULTI-073-01 | `MULTI-026-01`の入力を`objectFormat: sha256`のリポジトリにコミットする。`doctor --all-workspaces`（`apps/web`で実行） | `MULTI-026-01`と同じ（`passed`／0） | 同上 |

監査は`object_format_fixtures.py`が行い、入力と期待結果が基のfixtureと同じこと、リポジトリが`sha256`でコミットIDが64桁であることを確かめる。

### 既存のfixtureの見直し

- 結果のJSON Schemaの`revision`のコミットIDは40桁または64桁を受け付けるように広がった。既存の期待結果はどれも40桁の`0`なので、引き続き適合する（監査の公開JSONの検査）。
- `doctor`の検査項目`git`がGitの読取りも確かめるようになったが、既存の`doctor`のfixtureはどれもGitの読取りが成功する状態か、Git不在、コミットのないリポジトリ、
  リポジトリの外であり、失敗としない（`doctor` §6）。期待値は変わらない（推測を含む。Gitの読取りの失敗は準備の処理で作れないので、既存のfixtureにも現れない）。

### Coreの単体試験で確かめるもの（fixtureを置かない）

- `context`と`verify`で、リポジトリのルート、`HEAD`、作業ツリーの状態をGitから読めない場合の`revision: null`（決定3）。
- `doctor`の`DOCTOR-GIT-READ`（単一ワークスペースの`SPEC-DOCTOR-GIT-001`）と、複合ワークスペースの`SPEC-MULTI-GIT-001`（決定4）。
- どれもGitの読取りの失敗を準備の処理（適合fixture仕様 §3.2の閉じた集合）で作れないためである（ADR-082、ADR-083と同じ扱い）。

### 置いていないもの（司令塔の判断を待つ）

1. **`revision`を持つ操作のSHA-256のfixture**（`check`、`check --base`、途中のコミットを読む保護、`context`、`verify`、複合ワークスペース）:
   適合fixture仕様 §4の共通正規化器は、`revision.base`と`revision.commit`を「40桁の小文字16進」であることだけを検査する。64桁のコミットIDの扱い
   （桁数を検査するか、期待値に何を置くか）が決まっていないので、期待値を書けない。
2. **UTF-8でないパスの名前**（決定1、`CHECK-PATH-NOT-UTF8`）: 未追跡のパスの名前をUTF-8でないバイト列にする準備の入力がない。`setup.materialize`の`to`はJSONの文字列で、
   UTF-8でないバイトを表せない（JSONの`\u`エスケープはUnicodeの文字だけを表す）。準備の入力の拡張が要る（ADR-048の部分改訂）。
3. **比べるリビジョンの壊れたルートの設定**（決定2、`MULTI-REVISION-ROOT-CONFIG-INVALID`）: 準備の処理では作れる（基準版または`HEAD`のコミットに構文の不正な設定、
   またはシンボリックリンクを置き、作業ツリーで直す）。しかし診断の`source`（`workspaceId`を現在版のルートのIDとするか`null`とするか、`path`、`key`の有無）を、仕様が定めていないので、期待値を書けない。

## 2026-11-28の追加（ADR-085。ADR-051の追加）

前の節で判断を待つとした3点を、[ADR-085](../../../docs/02.設計書/10_決定記録/ADR-085_適合harnessでUTF-8でない名前とSHA-256のコミットIDを扱い、壊れたリビジョンの設定の診断の形を定める.md)が決めた
（`setup.materialize`の`toBytes`、`setup.objectFormat`に応じたコミットIDの桁数の正規化、壊れたリビジョンの設定の診断の`source`）。前の節の「置いていないもの」の1〜3は、この節で解消した
（`--all-workspaces`のUTF-8でないパスの名前を除く。下の最後の項目）。

### 準備の入力と正規化器

- harnessとマニフェストのスキーマに`toBytes`（付け替えた後のパスのバイト列の小文字の16進。`2f`はセグメントの区切り。`to`と排他）を加えた。harnessはバイト列を
  ファイルシステムの名前へ変え、`to`と同じく安全なパスの規則（`.`、`..`、`.git`、NUL）を当てる。自己試験で、UTF-8でない名前を作り、2回の準備で同じスナップショットになることを確かめる。
- 参照harnessの共通正規化器（`runner.py`）は、`setup.objectFormat`に応じた40桁または64桁の小文字16進であることだけを検査し、同じ桁数の`0`へ置き換える（適合fixture仕様 §4）。
  桁数が合わなければ置き換えずに差分として報告する。自己試験（`test_runner.py`）を加えた。
- UTF-8でない名前は、副作用の期待値のスナップショットにファイルシステムの符号化（surrogateescape）の文字として現れるので、その`side-effects.json`はASCIIのエスケープで書く。

### 加えたfixture

| ID | 入力 | 操作 | 期待 |
|---|---|---|---|
| SINGLE-191-02 | `SINGLE-041`を`sha256`で | 引数なしの`check --base HEAD` | `SINGLE-041`と同じで、`revision`は64桁の`0` |
| SINGLE-191-03 | `SINGLE-031`を`sha256`で | `check --full --base HEAD` | `SINGLE-031`と同じ（`failed`）で、64桁の`0` |
| SINGLE-191-04 | `SINGLE-187-01`を`sha256`で | `check --full --base base` | `SINGLE-187-01`と同じ（途中のコミットを読む） |
| SINGLE-191-05 | `SINGLE-105-01`を`sha256`で | `context REQ-001 --purpose verify` | `SINGLE-105-01`と同じで、`revision.commit`は64桁の`0` |
| SINGLE-191-06 | `SINGLE-055`の入力を`sha256`のリポジトリにコミット | `verify REQ-001` | `revision`は`{commit: 64桁の0, dirty: false}`、ほかは`SINGLE-055`と同じ |
| MULTI-073-02 | `MULTI-001`を`sha256`で | `check --all-workspaces --base HEAD` | `MULTI-001`と同じで、64桁の`0` |
| SINGLE-192-01 | 未追跡の`notes/<0xff>.txt`（`toBytes`）。基準版のコミットは`.spec/`だけ | 引数なしの`check --base HEAD` | `failed`／1。`SPEC-PATH-INVALID-001`（「パスnotes/\xff.txtの名前をUTF-8として読めません」、`source.path`は`notes/\xff.txt`）。`selection`は1・0・1 |
| MULTI-074-01 | 基準版のルートの設定のYAMLの構文が不正、作業ツリーで直す | `check --all-workspaces --base HEAD` | `failed`／1。`SPEC-MULTI-CONFIG-001`（「比べるリビジョンのルートワークスペースの設定が不正です」、`source`は`{file, platform, .spec/bitz.yaml}`で`key`なし）。`workspaces: []` |
| MULTI-074-02 | 同じ入力 | `doctor --all-workspaces` | `MULTI-048-02`と同じ形（検査項目`catalog`が`failed`）で、診断は同じ1件 |
| MULTI-074-03 | 基準版のルートの設定がシンボリックリンク、作業ツリーで通常のファイルにする | `check --all-workspaces --base HEAD` | `MULTI-074-01`と同じ |

- 期待値の根拠: SHA-256は適合fixture仕様 §4と結果・診断・終了コード §2（ほかの規則はオブジェクトの形式によらず同じ。ADR-084の決定5）。`SINGLE-191-06`は、基の`SINGLE-055`が
  コミットのないリポジトリ（`revision: null`）なので、入力をコミットして`revision`を`{commit, dirty: false}`にした（`SINGLE-055`の`stage`はコミットに含まれる。§2）。
  UTF-8でないパスは安全な入出力・互換性 §6と`check` §5・§9。壊れたリビジョンの設定は複合ワークスペース仕様 §2・§8（`check`は基準版、`doctor`は`HEAD`のスナップショット）と
  ADR-085の決定3。停止の結果の形は、全体事前検査の`SPEC-MULTI-CONFIG-001`で止まる既存の`MULTI-037-15`（`check`）と`MULTI-048-02`（`doctor`）に倣った。
- 監査は`object_format_fixtures.py`（SHA-256。基のfixtureの入力、期待値、`git status`と照合する）と`git_read_fixtures.py`（UTF-8でない名前と壊れたリビジョンの設定）が行う。

### 置いていないもの（判断を待つ）

- **`--all-workspaces`のUTF-8でないパスの名前**: 全体事前検査で読むGitのパスの一覧にUTF-8でないパスがある場合の診断を、結果のどこに置くか（最上位の`diagnostics`か、
  そのパスを所有するワークスペースの`diagnostics`か）、`source.workspaceId`と`source.path`の基準（リポジトリのルートからか、ワークスペースのルートからか）、
  `failed`の診断が全体事前検査を非成功にしてワークスペースの処理を止めるか（継続単位は`continue`だが、§8は全体事前検査が非成功なら処理を始めない）を、仕様が定めていない。
