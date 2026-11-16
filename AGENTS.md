# AGENTS.md — BitzSkills 共通ルール

このファイルが全エージェント（Claude Code / Codex / Antigravity）共通ルールの唯一の正。
Claude Code は `CLAUDE.md` のインポート経由で、Codex と Antigravity は本ファイルを直接読む。
SPECの状態遷移やSDDフローなどの規範は該当する仕様書・ADRを正とし、本ファイルは上書きしない。
齟齬を見つけた場合は仕様書に従い、差異を報告する。

## リポジトリの役割

BitzSkills 2 系の開発リポジトリ。Core 1.0（CLI `bitz`: doctor / context / check / verify、
要件記述言語 EARS-AI）を、ADR と適合 fixture で仕様を先に固めてから実装している。
あわせて、Core を使うスキル（SDD、品質管理）の試作と、その評価を進めている。

- Core の計画: `docs/04.提案資料/12_Core-1.0実装計画.md`
- スキルの計画と進捗: `docs/04.提案資料/31_スキル統合残件の開発計画と進捗.md`
- 現在の論点と、1.0 と 1.1 の振り分け: `docs/04.提案資料/34_Coreと評価処理の現状整理と今後の方向性.md`
- 決定記録: `docs/02.設計書/10_決定記録/ADR-*.md`
- 用語: `docs/用語集.md`（用語の意味と日本語名の正本）、`docs/表記規則.md`（書き方の規則）
- 前バージョン（1 系: bitz-sdd / bitz-flow ほか）はブランチ `archive/v1`・tag `v1-final` に凍結している。
  参照は読み取りのみとし、1 系のルール・スクリプトをこのリポジトリへ持ち込まない

## 構成

```
docs/                # 検討資料・設計書・詳細設計・提案資料（規範の正）
fixtures/            # 適合 fixture と参照適合 harness（Core に依存しない。ADR-049）
plugins/bitz-core/   # Core 1.0 の実装（uv project、CPython 3.12 以上）
plugins/bitz-sdd/    # SDD のスキル（試作版）
plugins/bitz-quality/ # 品質管理のスキル（試作版）
tests/bitz-core/     # Core の単体試験と Gate B・Gate C 認定
tests/skills/        # スキルの評価器とスキルの接続の単体試験
evals/skills/        # スキルの評価の実行器、ケース、契約、結果
.spec/               # bitz-core 自身の要件・タスク（自己適用）
.venv/probe-*/       # 使い捨ての検証（Git で管理しない。「使い捨ての検証」の節）
```

## ガードレール

### 禁止（実行しない）

- `rm -rf` / `git push --force`（`--force-with-lease`・`+refspec`を含む） / `git reset --hard` / `git clean -f` / `sudo`
- `main` への直接コミットと直接push（変更時は必ずブランチを切る）
- リモートのブランチ・タグの削除、push済みの履歴の書換え
- 認証情報・トークン類（`~/.claude/.credentials.json`・`.env` 等）の読み取り・出力

### 事前確認が必要（ユーザーの明示承認なしに実行しない）

- リポジトリ外への書き込み・上書き・削除
- モデルを呼び出す評価の起動（`evals/skills/`の実行器のうち、モデルへ送信するもの）。対象、分母、反復、
  予算を示して承認を得る。CI が実行する監査と単体試験（下の検証コマンド）は、モデルを呼び出さないので対象外
- 承認済み（`approved`）のREQまたはTECHの意味の変更。ユーザーの明示承認を得てから、
  `docs/02.設計書/03_SDDフロー.md`に従い、変更と同じ作業で先に`draft`または`outdated`へ戻す。
  戻した状態は、再承認の前にコミットする（ADR-072）
- ADR の`proposed`から`accepted`への変更。起票は`proposed`で行い、利用者の承認を得てから変える

### Git操作の承認

次はユーザーが許可済みで、都度の確認は不要とする。上の「禁止」に当たる操作は含まない。

- 作業ブランチの作成、add / commit / merge、まだpushしていないコミットのrebase
- fetch / pull
- 作業ブランチを同じ名前のリモートへ送るpush（`git push`、`git push origin HEAD`、`git push -u origin HEAD`）

`.claude/settings.json`は、上のpushの3つの形だけを完全一致で許可し、それ以外のpushは確認を求める。
規則はコマンドの先頭の文字列で照合されるので、オプションの順序や`+refspec`による抜け道を`deny`だけでは
塞げない。`main`の保護はGitHubのブランチ保護でも強制する。

### 検証義務

- 他エージェントの「成功しました」という自己申告を信用せず、下記の検証コマンドを自分で再実行する
- Step の完了判定・Gate 判定・是正後の「解消済み」判定は、作業者と独立したコンテキストで検分する
  （自己レビューは甘く出る）

## 検証コマンド

| 目的 | コマンド |
|---|---|
| 適合 fixture の監査 | `uv run fixtures/validate_conformance.py`（exit 1 と pending 1 件が正常） |
| Core の適合試験 | `uv run fixtures/run_conformance.py --core plugins/bitz-core --step N` |
| Core の単体試験 | `uv run --project plugins/bitz-core python tests/bitz-core/run_test_files.py tests/bitz-core/test_*.py` |
| Gate A 認定 | `uv run fixtures/certify_gate_a.py`（clean tree 必須） |
| Gate B 認定 | `uv run tests/bitz-core/certify_gate_b.py --step N`（clean tree 必須） |
| スキルの評価契約の監査 | `uv run evals/skills/validate.py audit` |
| スキルの単体試験 | `PYTHONPATH="$PWD/plugins/bitz-core/src" uv run --project plugins/bitz-core --with jsonschema==4.23.0 python -m unittest discover -s tests/skills -p 'test_*.py'` |

- CI（`.github/workflows/ci.yml`）は PR と main への push で監査・単体試験・適合試験を、
  main への push・週次・手動で Gate A / Gate B 認定を実行する。適合試験は4分割し、main等では独立2組の
  全件結果とParser出力を集約してGate Bを判定する（ADR-056）。適合試験の分割と集約は、digestで固定した
  CI用のコンテナで実行する（ADR-069）。CI の通過はローカル検証の代わりにならない
- fixture を変更したら Gate A を再認定する（ADR-051）
- fixture の期待値は、仕様だけを根拠に決める。Core の実装を読んで期待値を合わせない（ADR-049）
- `fixtures/conformance/diagnostic-coverage.json`は、診断レジストリなどの仕様のハッシュ値を固定している。
  これらの仕様を改めると、診断の意味の網羅のレビューをやり直すまで fixture の監査が通らない。
  仕様の改訂、fixture の変更、レビュー、Gate A の再認定は、同じ PR で行う
- fixture の監査と Gate の認定は数分かかる。既定の制限時間で打ち切られる環境では、制限時間を延ばすか、
  バックグラウンドで実行する。出力を`tail`などへパイプすると終了コードを取れないので、終了コードは別に確かめる
- 対象環境は Linux / macOS、CPython 3.12 以上（ADR-053 / ADR-055）

## 使い捨ての検証

fixture に現れない挙動を、実際の Git リポジトリで確かめるときの規則。

- 置き場は、リポジトリの中の`.venv/probe-<名前>/`とする（`.venv/`は Git で管理しない）。リポジトリの外には作らない
- 検証用のリポジトリの中でも、`git add -A`を使わず、パスを指定する
- 終わったら、自分が作った`.venv/probe-<名前>/`だけを削除する。削除は
  `python3 -c "import shutil; shutil.rmtree('.venv/probe-<名前>')"`で行う。この方法をほかのパスに使わない
- 結果を残す必要がある検証は、提案資料または ADR の`Notes`に、手順と実際の出力を書く。
  ADR-074 の実装の後は、`sandbox/<名前>/`に独立のワークスペースを作り、仕様文書と結果をコミットする

## 文書の作法

- 表記は`docs/表記規則.md`、用語は`docs/用語集.md`に従う
- 提案資料を加えたら`docs/04.提案資料/README.md`の一覧へ、ADR を加えたら
  `docs/02.設計書/10_決定記録/README.md`の一覧へ行を足す
- 既存の決定を変えるときは、新しい ADR で部分改訂する（ADR-033）。裁定済みの提案資料と ADR の本文は書き換えない
- 実行して確かめた事実と、文書やコードを読んで推測した内容を区別して書く

## 並行開発

メインの作業ツリーは共有され、worktree が同時に動く前提で作業する。

- ブランチは `origin/main` から明示的に切る: `git checkout -b <name> origin/main`
- `git add -A` と広いパス指定を使わない。自分が触れたファイルだけを個別に指定する
- コミット直前に `git diff --cached --name-only` を確認し、関心事以外のファイルを除く
- 成果物へ記録する事実（件数・hash 等）は、作業ツリーではなく確定した ref か clean な状態で測る

## コミット・PR 規約

- **コミットタイトル**: `<type>: <説明>`。type は `feat` / `fix` / `spec` / `test` / `docs` / `chore`
  （`spec` は規範文書・ADR の変更）。説明は日本語で、何をするかを文で書く
- **fixture の変更と Core の実装は別コミットにする**
- **PR の統合は rebase merge**。squash merge は上の規則を崩すため使わない。
  ただし、他のブランチの作業を取り込んだ長いブランチなど、push済みの履歴を書き換えずに rebase できない PR は、
  マージコミットで統合してよい
- **1 PR = 1 関心事**。PR 本文には目的・変更点・検証結果（上記コマンドの実出力）を含める
