---
id: SDD-DSN-000
title: "仕様変更の完全性境界 — 設計作業台帳"
status: active
version: 1.1
updated: 2026-07-27
owner: codex
---

# 設計作業台帳

対象: SI-SDD-022、SI-SDD-023、SI-SDD-024。

## API 導出表

| API | 層 | 依存 | 由来 |
|---|---|---|---|
| `spec update` の通常遷移 | Process | 遷移表、要件・タスクfrontmatter | SI-SDD-023 |
| `spec update --interactive-decision` | Experience（対話CLI） | 人間裁定必須遷移、TTY、確認チャレンジ | SI-SDD-022 |
| `spec update --recover <event-id>` | Process | transaction journal、成果物hash、STATE event | SI-SDD-022、SI-SDD-023 |
| `spec scaffold` | Process | ID走査、排他的ファイル生成 | SI-SDD-024 |
| `spec inspect --workspace ...` | System audit | 全workspaceの成果物レジストリ | SI-SDD-023、SI-SDD-024 |

## 技術適合性マトリクス

| 候補技術 | カテゴリ | 適合性 | 根拠シグナル | 判断 | 条件/リスク |
|---|---|---|---|---|---|
| Python標準ライブラリ | CLI実装 | High | 現行2スクリプトがstdlibのみで配布される | Adopt | 外部依存を追加しない |
| TTY確認チャレンジ | 明示的な対話入力の強制 | High | SI-SDD-022の非対話実行事故 | Adopt | 人間性の認証機構ではない |
| 構造化STATE event | 裁定証跡 | High | 現行STATE行では入力境界・復旧単位を判定できない | Adopt | JSONを機械SSOT、Markdown行を表示層にする |
| workspace mutation lock | 競合制御 | High | 並行遷移でlost updateが起こり得る | Adopt | 自動stale解除をせず明示復旧 |
| write-ahead journal | crash recovery | High | statusとSTATEは別ファイルで単一replaceでは原子化できない | Adopt | hash照合できない場合は安全側停止 |
| 共有タスク索引ヘルパ | 遷移前提と事後監査のSSOT | High | `spec_update` と `spec_inspect` が同じimplements関係を使う | Adopt | 純粋な読取関数に限定 |
| 排他的ファイル生成 | 同一worktree内の採番競合 | High | `exists()`→`write_text()`にTOCTOUがある | Adopt | 競合時は再採番せず安全側停止 |
| 中央採番サービス／DB | cross-branch予約 | Low | ローカル・オフライン・stdlib配布契約に根拠がない | Reject | 運用直列化と統合時検査で代替 |
| Gitロックファイル | cross-branch予約 | None | ブランチごとに複製され共有ロックにならない | Reject | 衝突を防げない |

## Design Gate 裁定点

- [x] CLI保証を「遷移表＋明示的な対話入力」に限定し、人間性の認証はできないという残余リスクを明記する。
- [x] 誤認を招く`--by-human`を廃止して`--interactive-decision`へ置換し、検証可能なhost receiptが無い代行経路は設けない。
- [x] status・STATE更新はworkspace lock＋write-ahead journal＋hash照合復旧で一貫化する。
- [x] task前提は要件所有workspace内のlifecycle taskを正とし、cross-workspace taskだけでは遷移させない。
- [x] taskなし／未完了taskありの要件遷移に脱出口を設けない。
- [x] `--by-human`廃止をCLIの破壊的変更として扱い、実装時にsemver majorを適用する。
- [x] cross-branch採番は中央予約を導入せず、Plan直列化＋target head照合＋既存duplicate検査を正とし、残余リスクを明記する。
- [x] repository書込み権限者とlock参加writerを信頼し、非協調writerの最終競合窓は保証外とする。

承認: 2026-07-27、user（チャット裁定）。SDD-DSN-005をDesign Gate通過とする。
