---
id: CORE-CON-010
version: 1.0
status: verified
domain: governance
priority: medium
origin: SI-CORE-029
verification_method: manual-check
derived_from:
supersedes:
superseded_by:
confidence: high
---

### CORE-CON-010 version bump の PR 内配置規約

- **説明**: スキル変更に伴うプラグイン version bump は変更を届ける同一 PR に含める。
  コミット上の位置は固定せず、実装コミットへの同梱を推奨しつつ、bump 単独コミットも許容する。
  これにより、bump の含め忘れを防ぐという本来の統制を維持し、テスト先行フローの
  red → green → status 遷移というコミット順序と矛盾しないようにする。
- **受入基準 (EARS)**:
  - WHEN スキル変更によりプラグイン version の更新が必要になる THEN 開発者は version bump を同一 PR に含めること SHALL
  - WHERE version bump をコミットする位置を決める THE 規約は PR の最終コミットへの固定を要求しないこと SHALL
  - WHERE version bump を実装コミットと分ける THE 規約は bump 単独コミットを許容すること SHALL
- **検証手段**: AGENTS.md のコミット・PR 規約が上記3点を明記していることを目視し、
  `python3 scripts/release_check.py` と仕様一括検証が PASS することを確認する（manual-check）。
- **Revision History**:
  - 1.0 (2026-07-18) 初版（draft 起票）
  - 1.0 (2026-07-18) SI-CORE-029 の起票時前提を再検証。対象文言は現存し、
    最終コミット固定の規約と実運用の乖離も継続しているため、提案趣旨に乖離なし。
