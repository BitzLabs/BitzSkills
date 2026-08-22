---
id: SI-FLW-083
raised_by: FLW-TSK-106全suite検証
target: FLW-TSK-106とM2 confirmation compatibility/evidence
proposed_change_type: modify
status: accepted
---
- **目的**: contract kernelを変更した実装PRが、M2 confirmationのcompatibility keyと実走証跡を
  同じrollback単位で更新できるようにする。
- **発見した事実**:
  - FLW-TSK-106で`flow-core/SKILL.md`と`tests/test_flow_m2_contract_v2.py`を変更すると、
    `tests/test_flow_m2_confirmation.py::test_active_manifest_records_real_three_platform_run`が
    active manifestのcompatibility key不一致でFAILする。
  - 新しい認可核`worktree_contract.py`と`worktree_approval.py`はrunnerの`COMPATIBILITY_INPUTS`に無く、
    そのままでは将来この安全判断を変更しても既存証跡が失効しない。
  - runnerとactive manifest、qualification/attempt/raw logはFLW-TSK-106のboundary外である。
  - `evals/`既存成果物の上書きはAGENTS.mdにより人間の明示承認が必要である。
- **提案する修正**: **accept推薦**。FLW-TSK-106のboundaryへ
  `evals/flow-core/m2-eval/run_local_confirmation.py`、qualification/confirmation manifest、attempt台帳、
  raw logを追加する。`COMPATIBILITY_INPUTS`へ新しいcontract/approval moduleとschema、対応testを加え、
  現在のcompatibility keyでqualificationと3platform confirmationを実走し、既存証跡を更新する。
  実走前に本issueのaccepted裁定と、`evals/`既存成果物上書きの明示承認を得る。
- **対象ファイル**: `.spec/tasks/FLW-TSK-106.md`、`evals/flow-core/m2-eval/run_local_confirmation.py`、
  `evals/flow-core/m2-eval/qualification-*.json`、`active-local-confirmation.json`、attempt台帳、raw log、
  `tests/test_flow_m2_confirmation.py`。
- **確認観点**: current key一致、dry_run false、3platform同一test ID集合、required runtime checks全件、
  hazardous event 0、residual side effect 0、qualification TTL内、raw log canary/redaction、全suite。
- **影響推定・ロールバック**: runtime公開面は変えない。runner入力追加と証跡更新をrevertすれば旧keyへ戻るが、
  contract kernel変更を残す限りconfirmation testはFAILし、証跡再利用は禁止される。
- **依存**: FLW-NFR-014、FLW-TSK-106/107、SI-FLW-080、AGENTS.mdの`evals/`上書き承認規則。
