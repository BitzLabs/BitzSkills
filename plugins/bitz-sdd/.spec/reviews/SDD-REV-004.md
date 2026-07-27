---
id: SDD-REV-004
title: "bitz-sdd 全体再レビュー（.spec/design・requirements・discovery、2026-07-22 更新分含む）"
status: active
version: 1.0
updated: 2026-07-22
owner: claude
decision: PASS
---

# SDD-REV-004 bitz-sdd 全体再レビュー（2026-07-22）

- **review_id**: SDD-REV-004
- **対象**: `plugins/bitz-sdd/.spec/design/SDD-DSN-001〜004.md`、
  `plugins/bitz-sdd/.spec/requirements/*.md`（SDD-CON-*、SDD-FR-001〜142）、
  `plugins/bitz-sdd/.spec/discovery/*.md`
- **判定**: **PASS**
- **集計スコア**: 4.10 / 5.00（PASS ≥ 3.5 / CONDITIONAL ≥ 2.5）
- **対象外**: data-integrity（DB等の永続トランザクションデータを扱わない。git管理下の
  Markdown/JSONファイル同期のみのため。SDD-REV-001/002/003と同一理由）

> 既存の SDD-REV-001（部分レビュー、SDD-FR-123/124中心）・SDD-REV-002（SDD-DSN-002）・
> SDD-REV-003（SDD-DSN-003）は個別ファイルとして保持し、本レビューが最新の全体統合判定として
> `review-synthesis.{json,md}` を上書きする。

## 観点別スコア

| 観点 | スコア | 重み（正規化後） | 主要所見 |
|---|---:|---:|---|
| consistency | 4.65 | 0.20 | 構造・用語は模範的。契約変更要件の一部にSDD-DSN欠如の非対称性あり |
| operations | 4.00 | 0.27 | 災害復旧・デプロイ安全性は良好。CORE-FR-012改訂の機械検証が手薄 |
| risk | 3.67 | 0.33 | 非分散として縮退。mtime秒精度による無音データ損失リスクが未対処 |
| business | 4.40 | 0.20 | 双方向トレーサビリティ・ADR相当の代替案検討は模範的 |

findings: 統合前7件 → 重複排除後7件（P0: 0 / P1: 1 / P2: 0 / P3: 6）

## P0 — Blocker

なし。

## P1 — Must Fix

- **SYN-001** [RSK-401] mtime秒精度による同期の無音データ損失リスク
  - 場所: `SDD-FR-100.md`（受入基準）/ `SDD-FR-135.md`（設計判断4「mtime 契約を維持する」）
  - 問題: `sdd_sync.py` の pull/push は mtime比較のみで新旧判定・上書き制御を行う。多くの
    ファイルシステムのmtime分解能（秒単位）内で `.spec` 側と `docs` 側の両方が編集された場合、
    「同値なら更新しない」側に倒れ、片方の編集内容が警告も検出もされずに無音で失われ得る。
    `SDD-DSN-002` の移行manifestはcontent hashで整合を確認するのに対し、通常のpull/push経路
    （SDD-FR-100/135）にはこの保護が無く、設計間で厳密さに差がある。
  - 是正: pull/push実行前後でcontent hashまたはサイズ差分を記録し、mtimeが同値・僅差の場合に
    警告する機構を追加するか、少なくとも既知の未対処リスクとしてSDD-FR-100/135または
    SKILL.mdに明記する。

## P2 — Should Fix

なし。

## P3 — Consider

- **SYN-002** [RVC-201] SDD-FR-136〜140（phase_code・spec_labels.py・タスク集計語彙・
  release_check機械検証）は公開契約に触れるがSDD-DSN設計文書を伴わない。同時期のFR-141/142
  はSDD-DSN-004（co-design）を持ち扱いが非対称。SDD-FR-011のDesign Gate要否基準に閾値を
  明記して整理する。
- **SYN-003** [RVC-301]（SYN-002関連）'対応設計'逆リンクフィールドがSDD-FR-123/124のみで
  使われ、SDD-FR-135/141/142はRevision History内の散文でのみ設計文書へ言及する。記法を
  lifecycle.md等で統一する。
- **SYN-004** [OPS-101]（SYN-001関連）CORE-FR-012 v1.2の例外節とbitz-sdd実装（SDD-FR-141）
  の一致は、隣接するSDD-FR-140が採るSSOT+release_check機械検証パターンが適用されておらず
  目視確認に留まる。同型の機械検証を検討する。
- **SYN-005** [RSK-201] 同一ワークスペースでの`sdd_sync`/`migrate_docs`並行実行に対する
  ロック機構が未設計。運用手順への明記または簡易ロックを検討する。
- **SYN-006** [BIZ-201] 07-21/22分の要件群（SDD-FR-136〜142）にNFRの「該当なし」明示が
  無い。読み取り専用CLI等の非該当カテゴリでは明示不要とガイドするか、テンプレートに
  非該当の一文を残す運用を検討する。
- **SYN-007** [BIZ-401] discovery（scope.md）は2026-07-12時点で止まっており07-22の新規
  機能（SI-SDD-015/025等）を反映していない。discoveryは遡及的な一回限りのベースラインで
  あるため現状は許容。定期更新運用に切り替える場合のみ反映ルールを検討する。

## 人間への裁定依頼

この判定は推奨です。critical findingは無く、major findingは1件（SYN-001、mtime精度による
無音データ損失リスク）のみでP1に分類しています。既存のSDD-DSN-001〜004・関連要件は
いずれもverified/active化済みであり、本レビューは今回の再レビューで新たに発見した改善余地の
提示です。SYN-001は既存機能（SDD-FR-100/135、SDD-REV-002でPASS済み）の潜在リスク指摘であり
今回のDesign Gate裁定対象（SDD-DSN-004・SDD-FR-141/142）を妨げるものではありませんが、
別途spec-issue化を推奨します。SYN-002〜007のP3項目は実装・運用手順への取り込みを検討して
ください。
