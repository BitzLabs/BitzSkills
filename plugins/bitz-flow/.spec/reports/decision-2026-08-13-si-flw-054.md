# 裁定記録 — SI-FLW-054（M2 運用規定）

- **日付**: 2026-08-13
- **裁定者**: hide
- **対象**: `SI-FLW-054`
- **裁定**: 推奨案で accept
- **裁定経路**: 対話確認（`open → accepted`）

## 裁定内容

1. reconnaissance は時間・件数・byte の上限を持ち、失敗・超過・`INDETERMINATE` 時は
   write を fail-closed で `BLOCKED` にする。具体値は既存 NFR から設計時に導出し、要件・fixture・
   出口条件で機械検証可能にする。
2. quarantine は解除目標時間、棚卸し頻度、滞留時のエスカレーション、責任者を定義する。
3. quarantine・intent・receipt を列挙・参照できる read operation を追加する。
4. 承認時の最小提示情報と承認率・連続承認等の観測指標を設ける。M2 では自動拒否せず警告とする。
5. 安全な finish / discard を利用できない環境では create を `UNSUPPORTED` とし、診断・audit のみ許可する。
6. ABA 経路 C は一時的な `UNAVAILABLE` と恒久的な `UNSUPPORTED` を分離し、いずれも
   「更新なし」へ倒さない。
7. intent・receipt・quarantine・nonce は Git ref の寿命に依存しない common-dir 配下の
   owner-only 領域へ保存し、retention と改ざん検知を定義する。
8. repo 外 worktree root ごとに lock・atomicity・identity 安定性・時刻粒度を probe し、
   判定不能なら write を許可しない。
9. 承認 capability の脅威モデルを誤操作・別プロセスによる誤用の防止とする。鍵を実行主体から
   隔離できない環境では、悪意ある主体への防御を主張しない。
10. Activity API の timeout・rate limit・部分ページ・権限不足を個別分類し、完全性を証明できない
    結果は `INDETERMINATE` とする。

## 波及と次の作業

- `FLW-DSN-016` の運用規定、read operation、fixture を改訂する。
- `FLW-DSN-014` の capability matrix と縮退規則を改訂する。
- `FLW-FR-007` に reconnaissance 上限と fail-closed 要件を反映する。
- operation catalog / result schema と `SI-FLW-052` の整合検査へ接続する。
- 公開契約と要件に触れるため、改訂後に再レビューと Design Gate の再裁定を行う。
