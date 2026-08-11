---
implements: FLW-NFR-009
depends_on: [FLW-TSK-022]
boundary: evals/flow-core/m0-eval/README.md,evals/flow-core/m0-eval/rescoring-*.json,evals/flow-core/m0-eval/run-manifest-*.json
status: done
---

### 保存済みtrialを再採点して新旧差分を監査する

- **作業内容**:
  - 原trialを変更せず、raw logから決定的に再導出できる記録だけを新規則で再採点する。
  - 旧・新規則のtrial単位差分、unknown、自己診断を新規`rescoring-*.json`へ記録する。
  - `SI-FLW-036`で説明済みの2差分だけか確認し、READMEの規則version対応表を更新する。
  - 想定外差分またはunknownがあればactiveを切り替えずblockedとして報告する。
- **完了条件**: 原trialのdigestが不変で、新旧の規則・入力digestと判定差分を追跡できること。
- **事前確認**: `evals/`配下の既存READMEまたはrun manifestを更新する直前に、ユーザーの明示承認を得る。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
