---
name: env-doctor
description: bitz-env で展開した開発環境の健全性を診断する。ガードレール3層（.claude/settings.json の permissions ⇔ プラグイン同梱フック ⇔ AGENTS.md のナラティブ）の同期ズレ、レジストリと実際に有効なプラグインの食い違い、CLAUDE.md 委譲マトリクスの陳腐化を検出して修正案を出す。「環境を診断して」「ガードレールがずれていないか確認して」「env-doctor」「環境の健全性チェック」と言われたとき、またはガードレール・permissions を変更した後に使用する。
metadata:
  version: "0.1.0"
  author: br7.hide
  created: "2026-07-11"
  updated: "2026-07-11"
---

# env-doctor

## 目的

env-init が生成した環境は、プラグインの更新に自動追従しない。また、ガードレールは
「permissions（恒久層）・同梱フック（即効層）・AGENTS.md（ナラティブ層）」の
3層で意図的に二重化されており、片方だけ緩める事故が起きやすい。
本スキルはその同期ズレを検出し、修正案を**提案する**（修正の実施はユーザー承認後）。

## 診断項目

### 1. ガードレール3層の突き合わせ

| 検査 | 方法 |
| --- | --- |
| permissions の deny に最小集合（rm -rf / sudo / force push / reset --hard / clean -f / 認証情報 Read）が揃っているか | `.claude/settings.json` を読み、env-init の `references/permissions.md` のテンプレートと比較 |
| AGENTS.md のガードレール節（マーカー区間）が permissions の内容と矛盾しないか | 禁止リストの項目を突き合わせ |
| 同梱フックが有効か | プラグインが enabled か確認（可能なら `/hooks` 相当の情報、不可なら bitz-env のインストール状態をユーザーに確認） |

### 2. 協調構成の突き合わせ

| 検査 | 方法 |
| --- | --- |
| レジストリ（`.claude/bitz-env.local.md`）のアダプタが実際に有効か | インストール済みプラグイン一覧（取得可能なら）と比較。取得不能ならユーザーに確認 |
| CLAUDE.md の委譲マトリクス（マーカー区間）がレジストリ・`.claude/agents/` の実体と一致するか | 割り当て表の advisor / worker / アダプタ行を実体と突き合わせ |
| advisor / worker の frontmatter が有効か（model 指定・description） | `.claude/agents/*.md` を読む |

### 3. 生成物の陳腐化

- env-init のテンプレート（プラグイン側）と生成物（プロジェクト側）の
  マーカー区間を比較し、テンプレート更新に取り残された差分を報告する

## 出力形式

チェックリスト形式で報告する:

```
# env-doctor 診断結果

## ガードレール3層
- [PASS] permissions: deny 最小集合が揃っている
- [FAIL] AGENTS.md: 禁止リストに sudo が無い → 修正案: …

## 協調構成
- [WARN] レジストリの bitz-collab-example が plugin 一覧に見当たらない → env-register で棚卸しを提案

## 総合: 2 FAIL / 1 WARN — 修正を実施しますか？
```

## してはいけないこと

- ユーザー承認なしの修正実施（診断と提案まで）
- ガードレールの緩和提案（緩和はユーザー発意のみ。doctor は「強い方に揃える」提案をする）
