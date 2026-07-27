---
implements: SDD-FR-144
depends_on: [SDD-TSK-029, SDD-TSK-030]
boundary: skills/sdd-core/references/lifecycle.md, skills/sdd-git/SKILL.md, scripts/spec, spec_inspect.py, tests/test_spec_inspect.py, tests/test_spec_status.py, spec evidence, manifests
status: done
---

### target-head統合ゲートと運用契約を結線する

- **作業内容**: target commit SHAへ束縛したpreflight、Plan直列採番、共通writer lock、
  recovery/rollback手順、テスト仕様、version bumpを統合する。統合検査を阻害していた
  折り返しEARS節の物理行誤判定と、fixture・旧レビューの疑似ID参照も回帰テスト付きで是正する。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
