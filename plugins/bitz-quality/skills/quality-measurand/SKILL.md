---
name: quality-measurand
description: 統合品質メトリクス（要件充足率・ルール蓄積数・総合健全性スコア）の測定およびミューテーション自己診断（人工欠陥注入テスト）を実行する。「品質メトリクスを出して」「ミューテーションテストを実行して」「テストの検出力を自己診断して」「quality-measurand」と言われたときに使用する。
metadata:
  version: "0.1.0"
  author: br7.hide
  created: "2026-08-14"
  updated: "2026-08-14"
---

# quality-measurand

`quality-measurand` は、ソフトウェアの**品質測定系モデル**に基づき、客観的な品質メトリクス集計とテストスイート自身の検出力（ミューテーション自己診断）を測定するスキルです。

## 1. 測定系モデルの構成

```mermaid
graph TD
    Code["被測定物 (コード・仕様・テスト)"] --> Measurand["quality-measurand 測定系"]
    Measurand --> Metrics["品質メトリクス (充足率・ルール数・スコア)"]
    Measurand --> Mutation["ミューテーション自己診断 (欠陥注入・Kill判定)"]
    Metrics --> Rep1[".spec/quality/reports/quality-metrics.md"]
    Mutation --> Rep2[".spec/quality/reports/mutation-diagnosis.md"]
```

## 2. 実行手順

### 手順 1: 品質メトリクスの測定・集計
```bash
python3 <このスキル>/scripts/quality_measurand.py metrics . --save
```

### 手順 2: ミューテーション自己診断の実行
```bash
python3 <このスキル>/scripts/quality_measurand.py mutate . --save
```

## 3. 規律

- **測定系の独立性**: 被測定対象の変更を伴わずに測定を実行し、客観的な数値（スコア・充足率）として記録すること。
- **テストの自己検証**: 静的ゲートおよびレビュー機能が欠陥を100%撃墜（Kill）できることを定期的に診断すること。
