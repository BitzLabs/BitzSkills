---
implements: SDD-FR-121
depends_on: []
boundary: plugins/bitz-sdd/skills/sdd-issue/
status: done
---

### sdd-issue スキル新設（要望インテーク→予備判定→起票）

- **作業内容**: `plugins/bitz-sdd/skills/sdd-issue/SKILL.md` を新設する。フロー:
  ①要望の整理（1要望 = 1 spec-issue に分割）→②重複チェック（spec_status.py の JSON 出力で
  既存 spec-issue・要件と突合）→③可否の予備判定（既存要件との矛盾・ガードレール抵触・
  spec_inspect --impact による影響範囲・軽量レーン適否）→④委託先ワークスペース判定（ルート/サブ。
  origin / delegated_to フィールドの設定。SI-CORE-015 の正式化前は本文記載でも可）→
  ⑤spec_scaffold.py で採番・起票 →⑥裁定材料の提示（accept / reject の推薦と根拠を本文に記載）。
  権限分離の維持: status は常に open で起票し、accepted / rejected 化（裁定）は人間のみ。
  「判定」は推薦であることを SKILL.md に明記する（sdd-core 憲法4と整合）。
  規律・ライフサイクルの正は sdd-core のまま、本スキルはインテーク運用フローのみを担う。
  description は sdd-core（「要件」「spec」）と過剰競合しないようインテーク系トリガーに限定する。
  frontmatter は metadata（version/author/created/updated）必須。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
