---
name: quality-doctor
description: bitz-quality の品質管理・QA環境の健全性を読み取り専用で診断する。ディレクトリ構造（.spec/quality/）、再発防止ルール台帳（rules-ledger.md）、セッションファイル（qa-session.json）、依存関係の整合性をチェックし、問題があれば修復手順を報告する。「quality-doctor」「品質環境を診断して」「QAの健全性チェック」「bitz-quality の診断」と言われたときに使用する。初期化は quality-init、QAプロセスの統括は quality-core が担当する。
metadata:
  version: "0.1.0"
  author: br7.hide
  created: "2026-08-14"
  updated: "2026-08-14"
---

# quality-doctor

`quality-doctor` は、プロジェクトの `bitz-quality` 環境が健全にセットアップされているかを**読み取り専用で診断**するスキルです。

## 1. 診断項目

1. **ディレクトリ構造**: `.spec/quality/` 配下の各サブディレクトリ（`sessions`, `scorings`, `analyses`, `viewpoints`, `reports`, `rules`）の実在確認。
2. **再発防止ルール台帳**: `.spec/quality/rules/rules-ledger.md` の実在とスキーマ整合性。
3. **進行中セッション**: `.spec/quality/sessions/*.json` の JSON 構造と Phase 状態の整合性。
4. **依存関係**: 前提プラグイン `bitz-flow>=0.2` の充足状況。

## 2. 実行手順

同梱スクリプト `<このスキル>/scripts/quality_doctor.py` を実行して診断します。

```bash
# カレントディレクトリの診断
python3 <このスキル>/scripts/quality_doctor.py .
```

## 3. 修復ガイダンス

- `.spec/quality/` またはサブディレクトリが存在しない場合:
  `quality-init` スキルを実行して初期化を行ってください。
- ルール台帳が破損している場合:
  バックアップを確認の上、`quality-init` による台帳復元を行ってください。
- セッションファイルのパースエラーが発生している場合:
  該当の `qa-session.json` の JSON 構文を修正するか、新しいセッションを開始してください。
