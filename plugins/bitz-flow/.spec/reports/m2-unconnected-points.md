# M2 未接続点の再記録（FLW-TSK-106〜114）

- **日付**: 2026-08-24
- **起点**: `SI-FLW-090`（`FLW-REV-027:SYN-007` P1）
- **記録者**: claude
- **裁定の前提**: `.spec/reports/decision-2026-08-24-flw-nfr-014-reopen.md` に従い、
  `FLW-TSK-106`〜`114` の `done` は**取り消さない**。各taskは宣言した変更境界の作業を
  完了しており、過大主張は要件レベルの `verified` にあった。本書はその境界と
  **当時未接続だった点**を事後に明示する記録である。

## なぜ必要か

`FLW-REV-027`（FAIL 2.12）は、114 task が `done`・`FLW-NFR-014` が `verified` である一方で
production 経路が成立していなかったと判定した。task の完了条件は各taskの変更境界内で
閉じており、**境界を越えた「production から到達するか」を誰も引き受けていなかった**。
本書はその隙間を記録し、`FLW-TSK-115`〜`121` がどこを埋めたかを対応づける。

## 未接続点と是正の対応

| # | 未接続だった点 | 影響したtask | 是正 | 現状 |
|---:|---|---|---|---|
| 1 | `PlatformObservation` を構築する production コードが存在せず、`plan()` は `platform evidence is required` で必ず例外停止した | `FLW-TSK-111`（platform adapter） | `FLW-TSK-116` | 解消（probe実装・`platform_evidence_for()` へ結線） |
| 2 | 廃止済み signed-capability 経路と旧 context が production handler に残存し、`worktree_dir_guard_key` は `ApprovalContext` に存在しない field を参照していた | `FLW-TSK-106`（契約核）、`FLW-TSK-108`（TargetTransaction authority） | `FLW-TSK-115` | 解消（参照0件） |
| 3 | worktree 経路の全 subprocess に `timeout=` が無く、hang した Git child が無期限にブロックした | `FLW-TSK-109`（plan-digest runtime） | `FLW-TSK-117` | 解消（`process.run()` 監督下） |
| 4 | intent と緊急 receipt が2回 publish で、その間の停止が「Git副作用0件・nonce消費済み・`INDETERMINATE`」を作った | `FLW-TSK-108` | `FLW-TSK-118` | 解消（単一 durable record） |
| 5 | `QUARANTINED` を `confirmed-complete` へ分類できた | `FLW-TSK-110`（復旧監査とreconcile） | `FLW-TSK-119` | 解消（`DONE` かつ予定postcondition成立時に限定） |
| 6 | reconcile closure が active marker の適格性確認より先に不可逆追記された | `FLW-TSK-110`、`FLW-TSK-114`（運用コマンド統合） | `FLW-TSK-120` | 解消（適格性検査を closure 前へ） |
| 7 | coverage manifest が名指しする test の実在も、fixture／production の別も検査していなかった | `FLW-TSK-114` | `FLW-TSK-121` | 解消（`contract_version: 2`・機械検査） |
| 8 | `FLW-NFR-014` の出口条件が **fixture 成立**で書かれていた | 要件レベル | `FLW-TSK-121` | 解消（production 証跡へ据え直し） |

## 残る未接続点（是正では埋まらないもの）

次は実装の欠陥ではなく、**公開集合が gated である限り原理的に埋まらない**。
`FLW-DSN-017` §13.1 の行6〜11 に対応する。

- `worktree.create` / `resume` / `audit` / `reconcile` / `doctor` の **production E2E**。
  8つの handler はすべて `_GATED_HANDLERS` にあり、公開 dispatcher から到達しない
  （縮退規則3）。production から実証できるのは「到達しないこと」と
  「旧承認方式の即時拒否」に限られる。
- **macOS / Windows の実観測**。probe は実装済みだが実走していない。Windows は
  SID 取得手段が未確定のため、現状 `owner-unobservable` で必ず不支持になる。
- **10,000 event／100 MiB 規模での30秒収束**の実測。

## 完了判定への拘束

上記が埋まるのは公開集合の復帰後である。したがって `FLW-NFR-014` の再 `verified` は
`FLW-REV-027` と同じ5観点の再レビューで **PASS** を得た後に限る。
**再レビュー PASS 前に Promotion Gate を通さない。**
