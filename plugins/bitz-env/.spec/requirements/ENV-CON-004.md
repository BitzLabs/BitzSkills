---
id: ENV-CON-004
version: 1.0
status: approved
domain: guardrail
priority: high
origin: SI-ENV-001（REV-001 risk RSK-201/RSK-202）
verification_method: manual-check
derived_from:
supersedes:
superseded_by:
confidence: high
---

### ENV-CON-004 ガードの位置づけ（誤操作抑止・二重化前提）

- **説明**: 同梱フック（env_guard.py）は「誤操作の抑止」を目的とする層であり、
  悪意ある回避を防ぐセキュリティ境界ではない。正規表現ベースの検出は
  コマンド置換・エンコード・環境変数展開などで回避可能であることを前提とする。
  また、恒久的な防御は env-init が生成する permissions 層が担い、フック単独では
  完全な防御にならない（フックは fail-open で可用性を優先する即効層）。
- **受入基準 (EARS)**:
  - WHERE ガードの防御力をドキュメント・スキルで説明する箇所 THE システムは 「誤操作抑止でありセキュリティ境界ではない」旨を明示する SHALL
  - WHEN env-init が未実行で permissions 層が存在しない THEN env-doctor は 恒久層の不在を WARN として報告する SHALL
- **検証手段**: README / ENV-DSN-001 / env-doctor SKILL.md の記述レビュー（manual-check）
- **Revision History**:
  - 1.0 (2026-07-11) 初版（SI-ENV-001 accepted による）
  - 1.0 (2026-07-11) 人間裁定により approved 化（チャット指示）
