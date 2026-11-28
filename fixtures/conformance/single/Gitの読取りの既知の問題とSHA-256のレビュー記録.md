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
