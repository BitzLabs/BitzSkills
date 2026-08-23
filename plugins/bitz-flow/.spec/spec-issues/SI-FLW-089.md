---
id: SI-FLW-089
raised_by: FLW-REV-027
target: flow-core recovery / promotion marker
proposed_change_type: modify
status: open
---
- **目的**: reconcile closureを追記する前にcrash-held active markerの適格性を確定する。
- **提案する修正**: plan時にmarker存在・operation ID・bundle digestをauditへ束縛し、apply時はclosure前にpromotion lock下で再検証する。正常DONEや既にclosedのoperationへreconcileを案内しない。
- **対象ファイル**: `worktree_recovery.py`、`worktree_promotion.py`、operability audit/reconcile、crash tests。
- **確認観点**: marker欠落・不一致ではclosure 0件。closure後marker closure前crashは同decision retryで単一closureへ収束すること。target lockとpromotion lockを同時保持しないこと。
- **影響推定・ロールバック**: 二authorityの順序変更を伴うため独立変更とし、lock order不変条件を保護する。
- **依存**: `SI-FLW-088`。accept推薦（不可逆closureがmarker検証より先行するため）。
