---
id: SDD-FR-121
version: 1.0
status: implementing
domain: workflow
priority: medium
origin: SI-CORE-017（ルート .spec/spec-issues/。2026-07-12 ユーザー提案: sdd-issue 新設）
verification_method: manual-check
derived_from:
supersedes:
superseded_by:
confidence: high
---

### SDD-FR-121 sdd-issue スキルによる要望インテークと予備判定付き起票

- **説明**: ばらばらに届く要望を整理し、可否の予備判定を付けて spec-issue に登録するインテークスキル sdd-issue を新設する。現状の起票は sdd-core の軽量レーン節の自由記述運用で、要望の分割・重複チェック・裁定材料の提示が定型化されていない。規律・ライフサイクルの正は sdd-core のまま、sdd-issue はインテーク運用フローのみを担う（棲み分けを sdd-core に追記する）。
- **受入基準 (EARS)**:
  - WHEN ユーザーが要望を持ち込み spec-issue 化を求めたとき THEN sdd-issue は ①要望の整理（1要望 = 1 spec-issue に分割）②重複チェック（spec_status.py の JSON 出力で既存 spec-issue・要件と突合）③可否の予備判定（既存要件との矛盾・ガードレール抵触・spec_inspect --impact による影響範囲・軽量レーン適否）④委託先ワークスペース判定（ルート/サブ）⑤spec_scaffold.py による採番・起票 ⑥裁定材料の提示（accept / reject の推薦と根拠を本文に記載）の順で処理する SHALL
  - WHEN sdd-issue が spec-issue を起票するとき THEN status は常に open で起票し、起票ファイルは spec_inspect PASS の書式である SHALL
  - IF エージェントが sdd-issue 経由で accepted / rejected 化（裁定）を試みたとき THEN spec_update.py の --by-human 強制により拒否される SHALL（可否の「判定」は推薦であり裁定は人間のみ、と SKILL.md に明記する）
- **検証手段**: skill-validator チェックリスト PASS + release_check PASS + skill-tester による発動テスト（description が sdd-core のトリガー「要件」「spec」と過剰競合しないこと）+ 起票された spec-issue の spec_inspect PASS 確認 + SKILL.md の目視確認（裁定＝人間専用の明記・sdd-core との棲み分け）
- **Revision History**:
  - 1.0 (2026-07-16) 初版（draft 起票）
