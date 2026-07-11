---
name: env-register
description: bitz-env の協調アダプタ（外部エージェント連携プラグイン）を検出してプロジェクトのレジストリ（.claude/bitz-env.local.md）へ登録し、CLAUDE.md の委譲マトリクスを更新する。「アダプタを登録して」「協調プラグインを追加した」「委譲先を増やしたい」「レジストリを更新して」「env-register」と言われたとき、または契約準拠プラグインの導入後に使用する。契約の仕様は env-orchestration の collab-contract.md が正。
metadata:
  version: "0.1.0"
  author: br7.hide
  created: "2026-07-11"
  updated: "2026-07-11"
---

# env-register

## 目的

契約準拠の協調アダプタをプロジェクトのレジストリへ登録し、
env-orchestration と CLAUDE.md の委譲マトリクスから参照できるようにする。

## ワークフロー

### 1. アダプタの検出

次の順で試み、取得できた手段を使う（すべて失敗したら手動登録へフォールバック）:

1. インストール済みプラグインの列挙（`claude plugin list` / `agy plugin list` 等が
   使える環境ならその出力）
2. ユーザーへの質問: 「導入した協調アダプタのプラグイン名（またはパス）は？」

検出した各候補について、能力宣言（マニフェスト `metadata.collab` または
ルートの `collab.json`）を読み、契約準拠か確認する:
- `collab.agent` があること
- `delegate` スキルを持つこと（review / status は任意）

非準拠なら理由を報告し、登録しない。

### 2. レジストリへの登録（ユーザー確認付き）

`.claude/bitz-env.local.md` を作成・更新する（YAML frontmatter + 本文）:

```markdown
---
adapters:
  - name: bitz-collab-example
    agent: agy
    skills: [delegate, review, status]
    strengths: [量産, 長文読解, web検索]
    break-even: 3ファイル以上の一括生成
    registered: "YYYY-MM-DD"
---

# bitz-env レジストリ

このファイルは env-register が管理する。手動編集も可（次回実行時に検証される）。
```

既登録のアダプタは重複追加せず、能力宣言に変化があれば更新する。
アンインストールされたアダプタは、ユーザー確認のうえエントリを削除する。

### 3. 委譲マトリクスの更新

CLAUDE.md の `<!-- bitz-env:begin -->` 〜 `<!-- bitz-env:end -->` 区間内にある
「今回の割り当て」表の**協調アダプタ行だけ**をレジストリの内容で再生成する。
マーカー区間が無い場合は env-init の実行を先に案内する。

### 4. 報告

登録・更新・削除したアダプタと、委譲マトリクスの変更内容を報告する。
動作確認として、アダプタの `status`（あれば）を1回呼んで疎通を見るのが望ましい。

## してはいけないこと

- 非準拠プラグインの黙認登録（契約チェックを省略しない）
- マーカー区間外の CLAUDE.md 変更
- レジストリ以外の場所への状態の記録
