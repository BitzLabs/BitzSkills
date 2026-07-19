---
name: sdd-doctor
description: bitz-sdd を導入したプロジェクト環境の健全性を読み取り専用で診断する。依存プラグイン bitz-flow>=0.2 の有効性・semver 制約充足、scripts/spec ラッパーによる installed_plugins.json からのバージョン非依存解決（SI-CORE-022 方式）、.spec/ ワークスペースがある場合の spec_status.py 実行可否をチェックし、問題があれば導入手順つきの修正案を報告する。「bitz-sdd の診断」「sdd-doctor」「環境診断」「SDD 環境の健全性チェック」「依存プラグインが揃っているか確認して」と言われたとき、または bitz-sdd 導入直後や依存関係を変更した後に使用する。
metadata:
  version: "1.0.0"
  author: br7.hide
  created: "2026-07-19"
  updated: "2026-07-19"
---

# sdd-doctor

## 目的

bitz-sdd は「単体インストール時に依存プラグイン（bitz-flow）が欠けていると
コミット規約・PR フローの実行手順が失われる」という不整合を起こしうる
（SI-CORE-010 の確認観点）。また `scripts/spec` ラッパー方式（SI-CORE-022）を
導入したプロジェクトでは、`installed_plugins.json` からの版解決が壊れていると
`spec inspect/scaffold/status/update` のすべてが実行不能になる。
本スキルはこれらを**読み取り専用**で診断し、問題があれば修正案を**提案する**
（修正の実施はユーザー承認後、本スキルの範囲外）。

## してはいけないこと

- 対象プロジェクト・配置先への書き込みを一切行わない（診断のみ）
- `spec_inspect.py` の実行（レポートファイルを書き込むため doctor からは使わない。
  `.spec/` の照会には読み取り専用の `spec_status.py` を使う）
- ユーザー承認なしの修正実施

## 診断項目

### 1. 依存プラグイン bitz-flow の有効性・semver 制約充足

| 検査 | 方法 |
| --- | --- |
| bitz-sdd の `metadata.dependencies` に宣言された制約（例: `bitz-flow>=0.2`）を確認 | `.claude-plugin/plugin.json`（または `plugin.json`）の `metadata.dependencies` を読む |
| 宣言された依存プラグインが導入先環境で有効か | インストール済みプラグイン一覧（取得可能なら `installed_plugins.json` や `/plugin` 相当の情報、不可ならユーザーに確認）と突き合わせ |
| 有効な場合、そのバージョンが semver 制約を満たすか | 検出したバージョンと制約（`>=0.2` 等）を比較 |

- 欠如または制約不満足の場合は **FAIL** とし、導入手順つきの修正案を示す
  （例: `/plugin install bitz-flow@bitzskills` で導入、または
  `python3 scripts/bump_version.py bitz-flow minor` 等でのバージョン更新を促す）。
- 確認手段が利用できず有効性を確定できない場合は **WARN** とし、
  「確認不能である」旨と、確認可能な環境（本体環境）での再確認を促す文言を明記する。

### 2. scripts/spec ラッパーのバージョン非依存解決（SI-CORE-022 方式）

対象プロジェクトに `scripts/spec` が存在する場合のみ診断する。

| 検査 | 方法 |
| --- | --- |
| `scripts/spec` が存在するか | 対象リポジトリ直下の `scripts/spec` を確認 |
| `installed_plugins.json` から固定版が解決できるか | `$BITZSKILLS_PLUGINS_DIR`（既定 `~/.claude/plugins`）配下の `installed_plugins.json` を読み、`bitz-sdd@bitzskills` エントリの `projectPath` が対象リポジトリルートに一致する `installPath` を探す |
| 固定版が無い場合、プラグインキャッシュからの semver 最大版フォールバックが成立するか | `plugins_dir()/cache/*/bitz-sdd/*/skills/sdd-core/scripts/` にツール一式（`spec_inspect.py` / `spec_scaffold.py` / `spec_status.py` / `spec_update.py`）が揃っているか確認 |
| 解決先スクリプトが実在するか | 上記いずれかで解決したパスの実ファイル存在を確認（`scripts/spec status <repo-root> --json` 相当を非破壊的に一度実行して終了コードを見てもよい） |

- 解決不能（固定版もキャッシュも見つからない、またはスクリプト欠落）の場合は **FAIL** とし、
  「`bitz-sdd` プラグインの再インストール」または `BITZSKILLS_PLUGINS_DIR` の見直しを
  修正案として示す。
- `scripts/spec` が存在しないプロジェクトでは本項目を「対象外（N/A）」として報告する
  （ラッパー方式を採用していないプロジェクトでは不要な診断のため）。

### 3. `.spec/` ワークスペースがある場合の spec_status.py 実行可否

対象プロジェクトに `.spec/` が存在する場合のみ診断する。

| 検査 | 方法 |
| --- | --- |
| `.spec/` ワークスペースの有無 | 対象リポジトリ直下（および委譲先ワークスペース）の `.spec/` を確認 |
| `spec_status.py` が読み取り専用で実行可能か | `scripts/spec status <workspace> --json`（`scripts/spec` が無い環境では解決したスクリプトを直接）を実行し、正常終了（非破壊的な状況照会のみで完了）することを確認する |

- 実行できない場合は **FAIL** とし、原因（スクリプト不在・実行権限・Python 環境）と
  修正案を示す。
- `.spec/` が存在しないプロジェクトでは本項目を「対象外（N/A）」として報告する。

## 出力形式

チェックリスト形式で報告する:

```
# sdd-doctor 診断結果

## 依存プラグイン
- [PASS] bitz-flow: 有効（v0.3.0、制約 >=0.2 を充足）

## scripts/spec ラッパー
- [PASS] installed_plugins.json から固定版 (bitz-sdd@2.0.0) を解決できた

## .spec/ ワークスペース
- [PASS] spec_status.py が読み取り専用で実行可能

## 総合: OK — 全項目で問題なし
```

問題がある場合は該当行を `[FAIL]` / `[WARN]` とし、その直後に修正案を1〜2行で添える。

```
## 依存プラグイン
- [FAIL] bitz-flow: 未検出（bitz-sdd は bitz-flow>=0.2 を要求）
  → 修正案: `/plugin install bitz-flow@bitzskills` で導入するか、
    Antigravity/Codex では `agy plugin install <repo>/plugins/bitz-flow` /
    `codex plugin add bitz-flow@bitzskills` を実行する

## 総合: 1 FAIL — 修正を実施しますか？
```

## 全て OK の場合の報告

すべての診断項目が PASS（または対象外）の場合は、OK 判定と各項目の根拠を
簡潔に報告する（上記の出力形式サンプル参照）。
