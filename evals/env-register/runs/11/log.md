# run 11 — TC-06（発動判定）

- ケースID: TC-06
- モード: 発動判定（SKILL.md の frontmatter `description` のみを読み、本文は読まない）
- 実行日時: 2026-07-12
- ファイル操作: なし（cases.md の指示どおり、sandbox は構築していない）

## 読んだ description（全文）

> bitz-env の協調アダプタ（外部エージェント連携プラグイン）を検出してプロジェクトのレジストリ
> （.claude/bitz-env.local.md）へ登録し、CLAUDE.md の委譲マトリクスを更新する。「アダプタを登録して」
> 「協調プラグインを追加した」「委譲先を増やしたい」「レジストリを更新して」「env-register」と
> 言われたとき、または契約準拠プラグインの導入後に使用する。契約（v2）の仕様は env-orchestration の
> collab-contract.md が正。

## 判定

### (a) 「gemini 連携のプラグインを入れたから委譲先に追加して」

- **判定: このスキルを使う**
- 理由: 「委譲先に追加して」は description が明示するトリガー文言「委譲先を増やしたい」に
  意味的にほぼ一致する。「gemini 連携のプラグインを入れた」も「協調プラグインを追加した」
  「契約準拠プラグインの導入後」に相当する状況であり、bitz-env の協調アダプタ登録の文脈と
  一致する。よって env-register を発動すべきと判定した。

### (b) 「このプラグインの marketplace.json に登録して」

- **判定: このスキルを使わない**
- 理由: description が扱うのは「プロジェクトのレジストリ（.claude/bitz-env.local.md）」への
  協調アダプタ登録であり、`marketplace.json`（BitzSkills リポジトリのプラグイン一覧マニフェスト）
  への登録とは対象が異なる。`marketplace.json` はリポジトリ自身へのプラグイン追加時に
  `.claude-plugin/marketplace.json` の `plugins[]` へエントリを追加する作業であり、
  AGENTS.md の記載どおり add-plugin（プラグイン追加コマンド）の管轄。env-register の
  description にはリポジトリのプラグイン登録・マーケットプレイス登録に関する言及が一切無いため、
  「使わない」と判定した。

## アサーション結果

- [x] ✅ (a) は「このスキルを使う」と判定する
- [x] ✅ (b) はリポジトリのプラグイン登録（add-plugin の管轄）として「使わない」と判定する

## 気づき

- description の記載だけで (a)(b) とも迷いなく判定できた。特に (b) の
  「marketplace.json への登録」と「.claude/bitz-env.local.md への登録」の区別は、
  description 内に対象ファイルパス（`.claude/bitz-env.local.md`）が明記されているおかげで
  誤発動を防げている。この書き方は他スキルの description 設計でも参考になる。
- 一方で "登録して" という動詞だけに注目すると (a)(b) を混同するリスクはゼロではない。
  「委譲先」「協調プラグイン」という語がキーになっており、もし将来ユーザーが
  「このプラグインを登録して」とだけ言った場合（対象が曖昧な場合）は、
  description だけでは判定しきれず、確認質問が必要になる可能性がある。
