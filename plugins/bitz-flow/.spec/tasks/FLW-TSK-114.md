---
implements: FLW-NFR-014
depends_on: [FLW-TSK-110,FLW-TSK-113]
boundary: plugins/bitz-flow/skills/flow-core/references/operation-catalog.md,plugins/bitz-flow/skills/flow-core/scripts/flowlib/worktree_operability.py,plugins/bitz-flow/skills/flow-core/scripts/flowlib/cli.py,plugins/bitz-flow/docs/runbooks/m2-worktree-quarantine.md,tests/test_flow_m2_operability.py
status: pending
---

### operations control plane・SLI・runbookを統合する

- **作業内容**: doctor、promotion check/apply、quarantine list/show/reconcile/release-record、
  receipt verifyを公開CLIとoperation catalogへ接続する。
  - read-only commandは実行前後のstate digest不変を検証し、管理commandも下位controllerの
    公開API以外から永続fileを編集しない。
  - closed resultにresult/cause code、side-effect state、自動復旧可否、operator action、
    operation ID、receipt pathを必須化する。
  - cause別停止、lock待機、quarantine滞留、token不連続、chain failure、容量迫近を
    SLIへ接続し、通知未設定でも手動対応先と終了codeを失わない。
  - runbookにreviewer keyの登録/rotation/失効、support profile、保持/archive、
    audit-onlyからdefault-onの展開とrollbackを記載する。
- **完了条件**: runbookの全commandが実在し、read-onlyの副作用0件、全停止原因の
  operator action欠落0件、通知未設定時の証跡喪失0件、active/quarantine証跡の自動削除0件を
  E2E fault fixtureで確認する。共有runtime変更のため全pytest、spec inspect、release checkを実行する。
- **実行判定**: 運用統合の最終タスク。recoveryとpromotionの完了後に開始し、
  下位の安全判定をCLI独自ロジックで上書きしない。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
