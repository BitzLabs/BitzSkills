---
id: FLW-FR-006
version: 2.1
status: implementing
domain: workflow
priority: high
origin: SI-FLW-004
verification_method: unit-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### FLW-FR-006 worktree-firstライフサイクル

- **説明**: 書込み作業をWorkUnit単位のworktreeへ分離し、作成、再開、完了、失敗保全、discardを状態機械化する。
- **受入基準 (EARS)**:
  - WHEN 新しい書込みWorkUnitを開始する THEN bitz-flowは1 WorkUnit、1 worktree、1 branchの対応をplanすること SHALL
  - WHEN worktree pathを計画する THEN bitz-flowはrepo slug、repo identity短縮値、work IDを含む衝突しないpathを返すこと SHALL
  - WHEN repo外worktreeのcreateを要求する THEN bitz-flowはcanonical pathとeffectsを提示して明示的人間承認を要求すること SHALL
  - WHEN 既存worktreeをresumeする THEN bitz-flowはpath、branch、HEAD、Git common dirがplanと一致した場合だけ同じWorkUnitとして再開すること SHALL
  - WHEN branch-onlyのv1対象を監査する THEN bitz-flowはworktreeが存在しないlegacy WorkUnitとして分類すること SHALL
  - WHEN merged WorkUnitをfinishする THEN bitz-flowはmerge証跡監査後にworktree除去とlocal branch処理を段階別に実行すること SHALL
  - WHEN WorkUnitが失敗状態になる THEN bitz-flowはworktreeと未コミット変更を保持して`failed-retained`を返すこと SHALL
  - WHEN failed-retained WorkUnitをdiscardする THEN bitz-flowは固定manifestの全targetと明示的人間承認が一致した場合だけ列挙targetを除去すること SHALL
  - WHEN M2のworktree writeをapplyする THEN bitz-flowはplanが返した`operation_id`、期限、単回nonce、
    `--confirm <operation_id>`による明示的人間確認を要求し、各Git副作用の直前にplan contextを再照合すること SHALL
  - WHEN M2で`signed-capability`の宣言または入力を検出する THEN bitz-flowは`plan-digest`へ降格せず
    `UNSUPPORTED_APPROVAL_MODE`を返し、Git副作用を0件にすること SHALL
  - WHEN M2の承認方式をresultまたはreceiptへ記録する THEN bitz-flowは`plan-digest`を明示し、
    trusted key registry、署名鍵、reviewer roleをM2の判定入力にしないこと SHALL
  - WHEN `worktree.finish`または`worktree.discard`を要求する THEN bitz-flowはM3まで
    `UNSUPPORTED`を返し、M2の受入対象に含めないこと SHALL
  - WHEN create/resumeの承認経路を検査する THEN bitz-flowは廃止済みsigned-capability経路と
    旧contextをproduction handlerから参照せず、旧入力は内容を解析せずmutation前に
    `UNSUPPORTED` / `unsupported-approval-mode`へ閉じること SHALL
  - WHEN create/resumeのplatform能力を判定する THEN bitz-flowはproductionコードが生成した
    closed `PlatformEvidence`を用い、観測不能・未知・network filesystemを`supported`へ
    格上げしないこと SHALL
- **検証手段**: path衝突、repo identity、resume不一致、branch-only、finish部分失敗、dirty保全、
  manifest外target不変をunit testで検証する。create/resumeの是正は
  `FLW-TSK-115`（旧承認経路の除去。`tests/test_flow_m2_legacy_approval.py`）と
  `FLW-TSK-116`（実環境platform probeの結線。`tests/test_flow_m2_platform_probe.py`）が担う。
  `finish`／`discard`はM2の検証対象外であり、M3の入口条件として扱う
  （移送裁定: `.spec/reports/decision-2026-08-15-m0-shipping-surface-and-m2-rescope.md`）。
- **Revision History**:
  - 2.1 (2026-08-24) create/resume是正（`FLW-TSK-115`／`116`）を検証手段へ直接トレースし、`finish`／`discard`がM3であることとplatform evidenceの格上げ禁止を受入基準へ明示（`SI-FLW-090`）
  - 2.0 (2026-08-22) M2 Local Safety Profileへ縮退し、条件付き署名をV2初期版から外してplan-digestへ限定
  - 1.1 (2026-08-17) 承認モードの配備意図を追跡下の宣言から読み、registry削除時の無言降格を`BLOCKED`へ倒す3値判定を追加（`SI-FLW-073`。裁定参照: .spec/reports/decision-2026-08-17-si-flw-072-073-075.md）
  - 1.0 (2026-07-29) accepted SI-FLW-004とFLW-DSN-006/012からdraft起票
