# 裁定記録 — 承認 capability の条件付き縮退（選択肢 B2）

- **日付**: 2026-08-15
- **裁定者**: hide
- **対象**: `FLW-DSN-016` §4 の承認 capability 機構
- **提示した材料**: `.spec/reports/investigation-2026-08-15-capability-reduction.md`
- **提示した選択肢**: B1（完全撤去）/ B2（条件付き縮退）/ B3（前提の復活）/ B4（現状維持）
- **裁定原文**: 「B2 で進めましょう」
- **記録者**: claude（裁定者の明示指示に基づく代行記録・実行者未検証）

## 裁定

**B2 を採用する。**

1. 承認の既定は **`--confirm <operation_id>` ＋ 単回 nonce ＋ `expires_at`** とし、
   署名（`algorithm` / `key_id` / signature 検証）を要求しない。
2. **trusted key registry が存在する配備でのみ**署名検査を有効化する。
   鍵隔離（executor と別の owner-only process / keystore に秘密鍵を置くこと）を
   署名モードの**前提条件として明文化**する。
3. どちらのモードで承認を判定したかを **result へ明示**する。
4. `worktree_runtime.apply()` が自ら trusted key registry を読むよう是正する
   （`FLW-REV-016:RSK-204`）。署名モードでのみ意味を持つが、B2 / B3 いずれでも
   無駄にならないため本裁定に含める。

## 裁定の根拠

### 1. 署名は M1 からの流用であり、worktree 固有の脅威分析に基づかない

`FLW-DSN-016` §4（L328-331）は「M1 の capability envelope をそのまま再利用」
「新規機構ではない」と明記している。M1 の原型（`FLW-DSN-015` L248-254）は
**quarantine 解除**という例外イベントの文脈で、署名対象に `reviewer` を持ち
registry は repository owner が管理していた。M2 への移植で `reviewer` が落ち、
承認者が executor と別であるという前提だけが失われた。

### 2. `operation_id` が承認 scope 全体を既に束縛している

`worktree_runtime.plan()` は承認 context 全体を含む facts の digest を `operation_id` とし、
apply は `--confirm` との一致に加え、**各副作用の直前に plan を再導出して同一性を再検査**する。
capability の scope 検査・freshness 検査は同じ束縛を署名付き envelope で二重に持つにすぎない。

したがって署名を外すことは束縛を弱める変更ではなく、**二重の片方を外す**変更である。

### 3. 残すべきは `expires_at` と nonce だけ

`RuntimePlan` に有効期限 field が無いため `expires_at` は固有であり、
承認の再利用を拒否する nonce も固有である。どちらも暗号を必要としない。

### 4. B3 を採らない理由

`reviewer` を復活させれば署名は設計どおり機能するが、worktree の作成・再開は
**通常操作**であり、M1 の quarantine 解除（例外イベント）と承認頻度が異なる。
1件ずつ外部承認者の署名を要求する運用は現実的でないと判断した。
ただし B2 は registry の存在によって署名モードを残すため、
将来この運用を採る余地は閉じない。

## 帰結

| 対象 | 変更 |
|---|---|
| `flowlib/worktree_capability.py` | 署名検査を条件付きへ。`WorktreeApprovalCapability` の必須 field を見直す |
| `flowlib/worktree_runtime.py` | `apply()` が registry を読む。署名なしモードの承認経路 |
| `flowlib/cli.py` | `--capability-file` を条件付きへ。`--nonce` の追加。モードの result 表示 |
| `FLW-DSN-016` §4 | 規範を B2 へ改訂（署名モードの前提条件を明記） |
| result schema | 承認モードを表す field の追加可否 |
| テスト | `M2-FLT-010`〜`015`（署名系 fault）の再構成 |

実装は **`SI-FLW-061`** として起票する。

## 予算

本裁定に実施予算は含まれない。`SI-FLW-057`（M2 分）/ `058` / `059` と合わせて、
後続の予算裁定で確定する（`FLW-REV-016:GP-005` の後続）。
`SI-FLW-061` は `SI-FLW-057` と同じ `apply()` を触るため、着手順の調整が要る。

## 未確定（後続へ）

- 承認モードを result のどの field で表すか（`data.approval_mode` を候補として提示済み）
- `FLW-REV-013:GP-002` / `GP-011`（capability 化を求めた前提条件）の再裁定要否
- `SI-FLW-061` と `SI-FLW-057` の着手順と、両者を1 PR にまとめるか
