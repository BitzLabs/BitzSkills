# 裁定記録 — FLW-REV-027 是正 spec-issue の一括受理

- **日付**: 2026-08-24
- **裁定者**: hide（リポジトリ所有者）
- **対象**: `SI-FLW-084`、`SI-FLW-085`、`SI-FLW-086`、`SI-FLW-087`、
  `SI-FLW-088`、`SI-FLW-089`、`SI-FLW-090`、`SI-FLW-091`
- **裁定原文**: 「8件すべて accept で進める」
- **提示済み提案**: `FLW-REV-027`（判定 FAIL・集計スコア 2.12・risk 1.33 で floor 未達）が
  起票した P0 2件・P1 5件・P2 1件を、各 spec-issue の accept 推薦どおり受理し、
  依存順に要件化・タスク分解へ進める。
- **記録者**: claude（裁定者の明示指示に基づく代行記録・実行者未検証）

## 裁定

1. `SI-FLW-085` を accepted とする（依存なし・先行）。create/resume CLI を plan-digest 専用契約へ
   一致させ、廃止済み signed-capability 経路と旧 context 参照を production handler から除去する。
   旧入力は内容を解析せず `UNSUPPORTED / unsupported-approval-mode` へ即時に閉じる。
2. `SI-FLW-084` を accepted とする。OS 別 read-only probe を追加し、doctor と plan で同一の
   evidence 生成器を用いて closed `PlatformEvidence` を production CLI から plan へ渡す。
   観測不能は `UNSUPPORTED_FILESYSTEM` へ閉じ、supported へ格上げしない。
3. `SI-FLW-086` を accepted とする。read/write 共通の有限 TimeoutBudget と process supervision を
   実装し、hang・出力超過・終了不能でも 30 秒以内に closed terminal result へ収束させる。
   終了を証明できない write は緊急 receipt を保持して `INDETERMINATE` へ閉じる。
4. `SI-FLW-087` を accepted とする。intent と緊急 receipt を単一 durable transaction record として
   確定するか、receipt 確定前を `INTENT_DURABLE` と扱わない中間状態へ変更する。
   永続形式へ触れるため Design Gate 対象とし、旧形式は推測移行せず fail-closed とする。
5. `SI-FLW-088` を accepted とする。`confirmed-complete` を `DONE` かつ予定 postcondition 成立時に
   限定し、`QUARANTINED` は常に indeterminate / quarantine へ分類する。
6. `SI-FLW-089` を accepted とする。plan 時に marker 存在・operation ID・bundle digest を audit へ
   束縛し、apply 時は closure 前に promotion lock 下で再検証する。
   target lock と promotion lock を同時保持しない不変条件を保護する。
7. `SI-FLW-090` を accepted とする。fixture 内部の検証と production 接続完了を区別し、
   `FLW-NFR-014`・`FLW-FR-006`・TSK-106〜114 の `verified` / `done` / coverage の
   過大主張を実態へ揃える。
8. `SI-FLW-091` を accepted とする。過去 9 レビューの未解決 P0/P1 88 件を後続是正証跡へ照合し、
   resolved または現行 issue への追跡状態へ更新する。履歴内容は削除せず status / 参照のみ修正する。

## 実装着手条件

- 上記 8 件を `accepted` へ遷移し、この裁定記録を `decision_ref` として残す。
- 実装は依存順に直列化する: `SI-FLW-085` → `SI-FLW-084` → `SI-FLW-086` /
  `SI-FLW-087` → `SI-FLW-088` → `SI-FLW-089` → `SI-FLW-090`。
  `SI-FLW-091` は依存なしのため独立に着手できる。
- `SI-FLW-087` は永続形式変更を伴うため、実装前に Design Gate を通す。
- worktree operation の公開集合は現在の gated 状態を維持し、
  `FLW-REV-027` の Gate blocking 条件 4 項をすべて満たし同 5 観点の再レビューで
  **PASS** を得るまで Promotion Gate を通さない。
