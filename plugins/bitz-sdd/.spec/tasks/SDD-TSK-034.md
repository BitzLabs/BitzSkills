---
implements: SDD-FR-145
depends_on: [SDD-TSK-032, SDD-TSK-033]
boundary: skills/sdd-core/SKILL.md, references/lifecycle.md, references/gates.md, .spec/requirements/SDD-FR-143.md, 3マニフェスト
status: done
---

### 運用文書・権限マトリクス・契約整合とリリース（minor）

- **作業内容**: `references/lifecycle.md` の権限マトリクスへ代行可視化経路と記録語彙を追記し、
  `references/gates.md` の Promotion Gate チェックリストへ「代行遷移の decision-ref を人間が
  確認」を追加する。`SKILL.md` の権限の分離節を2経路へ更新する。SDD-FR-143 を 2.0 へ bump
  （TTY 節を対話確認経路指定時に限定。保証内容は不変・適用範囲の限定を SDD-FR-145 が引き受ける
  旨を Revision History に明記）。bitz-sdd を minor bump（3.1.0）し、release_check と全 pytest
  で検証する。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない。
