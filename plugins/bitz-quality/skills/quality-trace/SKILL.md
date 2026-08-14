---
name: quality-trace
description: .spec/requirements/ の EARS 要件 ID と tests/ 配下のテストケースを自動照合し、トレーサビリティマトリクスおよび検証証跡（verification evidence）を出力する。「トレーサビリティを確認して」「要件カバレッジを出して」「quality-trace」と言われたときに使用する。
metadata:
  version: "0.1.0"
  author: br7.hide
  created: "2026-08-14"
  updated: "2026-08-14"
---

# quality-trace

`quality-trace` は、**要件定義（EARS）⇄ 自動テストコード ⇄ 検証証跡（Evidence）** の双方向トレーサビリティを自動照合・可視化するスキルです。

## 1. トレーサビリティ連携モデル

```mermaid
graph LR
    Req[".spec/requirements/ (QLT-FR-*)"] <--> Trace["quality-trace 照合"]
    Trace <--> Test["tests/ (test_*.py)"]
    Test --> Result["pytest 実行結果"]
    Result --> Evidence[".spec/quality/reports/traceability-matrix.md"]
```

## 2. 実行手順

### 手順 1: トレーサビリティ照合の実行
```bash
python3 <このスキル>/scripts/quality_trace.py verify . --save
```

## 3. 規律

- **未カバー要件のゼロ化**: approved 状態の要件は必ず対応するユニットテストまたは結合テストで参照され、100% カバレッジを維持すること。
- **証跡の自動蓄積**: テスト実行結果はマトリクスレポートとして `.spec/quality/reports/` に永続化すること。
