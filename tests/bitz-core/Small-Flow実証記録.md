# Small Flow実証記録

[実装計画 §9](../../docs/04.提案資料/12_Core-1.0実装計画.md)のStep 6に従い、bitz-core自身の`.spec/`でREQ 1件を
[Small Flow](../../docs/02.設計書/03_SDD-flow.md)で通した経過を記録する。後で通常Markdown条件と比較するため、
各工程の時刻、実行したcommand、結果status、見つかった欠陥、人間の確認に要した事項を残す。

## 題材

REQ-003「明示reportの保存先をsymlinkへ逸らさない」とTASK-001。`reportio.write_report`は`.spec/reports`を
`lstat`で検査した後にpath文字列で書き込むため、検査と書込みの間の差し替えでsymlink先へ書き込み得る
（結果契約 §8の「symlink先のdirectoryへ一時fileもreportも作らない」を競合下で守れていない）。
適合fixtureでは検出できない欠陥である。

## 経過

| 時刻（JST） | 工程 | 実行したこと | 結果 |
|---|---|---|---|
| 2026-09-26 10:03 | SPEC作成 | REQ-003（draft）とTASK-001（open）を起票し`bitz check --full` | passed（4文書、13句） |
| 2026-09-26 10:03 | Intent | `bitz context TASK-001 --purpose implement` | blocked（`CTX-STATE-001`、REQ-003がdraft）。人間の承認待ち |
