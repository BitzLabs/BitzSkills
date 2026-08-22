---
id: FLW-REV-024
title: "FLW-DSN-017 v1.5 独立再レビュー"
status: active
version: 1.0
updated: 2026-08-22
owner: codex
decision: FAIL
---

# 設計レビュー統合レポート — FLW-DSN-017 v1.5

- **review_id**: FLW-REV-024
- **対象**: FLW-DSN-017 v1.5、FLW-NFR-014 v1.3、FLW-TSK-106〜114、関連discovery
- **判定**: **FAIL**
- **集計スコア**: **2.35 / 5.00**（PASS ≥ 3.5 / CONDITIONAL_PASS ≥ 2.5）
- **Design Gate**: 通過不可。旧Gateはv1.5へ流用しない

## 観点別スコア

| 観点 | スコア | 重み | 主要所見 |
|---|---:|---:|---|
| consistency | 2.65 | 0.15 | case-insensitive target、activation粒度、署名artifact所有が未確定 |
| data-integrity | 2.00 | 0.25 | 容量予約、archive chain、key履歴に完全性ギャップ |
| operations | 2.20 | 0.20 | archive復旧、trust anchor、管理CLI認可が不足 |
| risk | 2.00 | 0.25 | lease authority、probe snapshot、promotion CAS、release retryが未閉鎖 |
| business | 3.40 | 0.15 | 定量性と分割は改善、署名責任と利用者導線が未接続 |

findings: 統合前26件 → 重複排除後12件（P0: 0 / P1: 8 / P2: 3 / P3: 1）

## 総括

v1.5は、旧レビューの11件をすべて設計上解消し、Safety Kernel、OS適合層、promotion、
mutation、recovery、operationsの責務分離と4段階rolloutを確立した。未実装であること自体は
findingにしていない。

一方、新たに導入した不変journal、署名policy、archiveの境界がまだ閉じていない。特に、
mutationとreleaseが共有するlease/fencing authority、測定済みartifactだけをprobeするsnapshot、
promotionの競合排除、releaseのcrash/retry収束は、実装前に確定しなければ安全保証を成立させられない。
さらにarchiveは不変event削除禁止と直接矛盾し、長期運用のための追加設計が本体のGateを阻害している。

## P0 — Blocker

なし。

## P1 — Must Fix

- **SYN-001** [RSK-201] lease・fencing・journalを更新する単一authorityがない
  - 場所: §5・§7、TSK-108〜110
  - 問題: mutationとrecoveryが同じcounter/lockを別経路で更新でき、token単調性と最大1 writerを破り得る。
  - 是正: Git権限を持たないTargetLeaseJournalServiceを唯一の更新authorityにする。
- **SYN-002** [RSK-202] 測定artifactとprobe実行artifactの同一性が閉じていない
  - 場所: §6.4、TSK-113
  - 問題: hash後のpath/import差替えにより未知codeをprobeで実行し得る。
  - 是正: handleからimmutable staging snapshotを作り、実行・importをsnapshot内へ固定する。
- **SYN-003** [RSK-203] promotion最終再照合とACTIVE公開がCASされていない
  - 場所: §6.4、rollout、TSK-113
  - 問題: 最終再照合後のregistry変更とactive state公開が競合する。
  - 是正: generation CAS/lock、またはPENDING→再照合→ACTIVEの二段階commitを採る。
- **SYN-004** [RSK-204] quarantine releaseのcrash・retry収束が未定義
  - 場所: §7、TSK-110
  - 問題: token発行・event公開・応答喪失間の再試行を冪等に判定できない。
  - 是正: release専用phase列、crash表、decision digest/nonceの冪等規則を定義する。
- **SYN-005** [RSK-401/RVC-201/RVC-202/BIZ-101/DIN-201/OPS-301] 署名policyとreviewer registryのroot of trust・履歴がない
  - 場所: §6.4・§7.2・§7.3、TSK-106/110/111/113/114
  - 問題: signer role、trust anchor、anti-rollback、失効、過去receipt検証、schema ownerが未割当。
  - 是正: role責任表、closed署名schema、単調generation、旧snapshot保持、PolicyVerifierを定義する。
- **SYN-006** [RSK-402/DIN-102/DIN-202/DIN-302/OPS-201/OPS-401/OPS-402] archiveが不変journalと矛盾し、所有・復旧契約もない
  - 場所: §4.2・§7.3、TSK-110/114
  - 問題: event削除禁止とDONE原本削除が矛盾し、chain、restore、crash、task/schema ownerも未定義。
  - 是正: 推奨はM2で原本pruneを禁止してarchiveをscope外へ戻すこと。採用時は独立設計・Gateとする。
- **SYN-007** [DIN-101/OPS-101] mutation完了証跡の容量予約がない
  - 場所: §4.2・§7.3、NFR保持上限
  - 問題: Git副作用後のENOSPCでpostcondition/quarantine receiptを残せない。
  - 是正: mutation前に最悪journal量と緊急receipt量を同一filesystemへ予約する。
- **SYN-008** [DIN-301/RVC-102] schema単位activationとgroup manifestの粒度が矛盾する
  - 場所: §6.3、TSK-106/108/110/111/113
  - 問題: activation/<schema-id>.json規約とgroup manifest boundaryが一致しない。
  - 是正: schema単位またはall-or-nothing group単位へ設計・loader・taskを統一する。

## P2 — Should Fix

- **SYN-009** [RVC-101] case-insensitive volume向けcollision keyを可逆表示pathと分離する。
- **SYN-010** [OPS-302] 状態変更CLIにpromotion/recovery/reviewerのauthorization matrixを設ける。
- **SYN-011** [RVC-301/BIZ-301] 多階層dispatcher grammarとflow-doctor/worktree doctorのroutingを統一する。

## P3 — Consider

- **SYN-012** [OPS-202] doctor検出、reconcile、quarantine初動のproto RTOを定義する。

## FAILの解消方針

Design Gate再判定には次の6論点を裁定し、P1を設計・要件・task boundaryへ反映したうえで、
同じ5観点の独立再レビューを行う必要がある。

- [ ] lease/journalの単一authorityとrelease retry状態機械
- [ ] immutable probe snapshotとpromotion CAS/二段階commit
- [ ] 署名role、root of trust、anti-rollback、過去key履歴
- [ ] M2 archiveをscope外へ戻すか、独立設計へ分離
- [ ] mutation前のdurability容量予約
- [ ] activation manifestの粒度統一

## 旧レビュー指摘の扱い

FLW-REV-023のP1〜P3はv1.4/v1.5で設計反映され、今回の5観点レビューで元の根本原因が解消済みと
確認できたため、11件をresolvedへ更新した。本レビューの指摘は、解消後のv1.5へ追加された新しい
境界に対するものであり、旧findingの単純な持ち越しではない。

## 人間への裁定依頼

この判定は推奨である。現状ではDesign Gateを通過させず、GP-001〜006を裁定して再設計し、
再レビュー後にGateを判断することを推奨する。
