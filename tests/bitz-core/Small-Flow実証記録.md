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
| 2026-09-26 10:07 | 承認 | 管理者がREQ-003の内容を確認してapprovedへ変更 | approved |
| 2026-09-26 10:07 | Context | `bitz context TASK-001 --purpose implement` | passed、`resolution.complete: true`、2文書、対象`MUST` 3件（addressed・tested）。Digest `sha256:f347a6e0f1092de470b65b9c44f04aba1dc2e4f9d6869bacfc81c82aafce09a6` |
| 2026-09-26 10:07 | Pre-check | `bitz check TASK-001` | passed（変更なし） |
| 2026-09-26 13:09 | Implement（1回目） | 実装担当がBundleを入力に`--expect-digest`で再照合（passed、staleでない）してから`reportio.py`と`test_reportio.py`を変更 | 単体試験521件OK、適合fixture 318件passed |
| 2026-09-26 13:09 | Post-check（1回目） | `bitz check TASK-001` | passed（`changes`の範囲外の変更なし） |
| 2026-09-26 13:09 | Verify（1回目） | `bitz verify TASK-001` | passed（REQ-003の3句、binding 1件） |
| 2026-09-26 13:09 | Review（司令塔） | `reportio.py`の差分を目視 | 欠陥1件: `.spec/reports`のfd取得後に名前が差し替えられると、差し替え前のdirectoryへ書き成功を返す。AC-02（保存中の差し替えで`SPEC-REPORT-WRITE-001`）に反する。試験はfd取得前の差し替えだけを再現していた。Post-checkとVerifyはこの欠陥を検出できない。Implementへ差し戻し |
| 2026-09-26 13:20 | Implement（2回目） | 実装担当が確定直後に`.spec`と`reports`の名前とfdの同一性（`st_dev`、`st_ino`）を照合し、不一致なら確定済みreportを除去して`SPEC-REPORT-WRITE-001`を返すよう修正。fd取得後の差し替え試験2件を追加 | 単体試験523件OK、適合fixture 318件passed。新しい試験は修正前の実装で失敗することを確認（陰性対照） |
| 2026-09-26 13:20 | Post-check（2回目） | `bitz check TASK-001`、`bitz check --full` | passed（変更は`changes`の2 fileだけ） |
| 2026-09-26 13:20 | Verify（2回目） | `bitz verify TASK-001` | passed（REQ-003の3句、試験12件） |
| 2026-09-26 13:20 | Review（司令塔、2回目） | 差分を目視 | 欠陥なし。human reviewへ |
