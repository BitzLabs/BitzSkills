---
id: SDD-CON-022
version: 1.0
status: draft
domain: upstream
priority: high
origin: skills/sdd-discovery/SKILL.md v0.2.2（reverse-derived）
verification_method: manual-check
derived_from:
supersedes:
superseded_by:
confidence: high
---

### SDD-CON-022 ディスカバリー成果物のマスター配置先制約

- **説明**: 上流探索の成果物がでっち上げを排除した信頼できるソースであるよう、すべてのディスカバリー成果物は `.spec/discovery/` 配下に直接配置されなければならない。
- **受入基準 (EARS)**:
  - WHEN 上流探索フェーズの成果物（ビジョン、成功指標、スコープ、ペルソナ/ジャーニー、ポジショニング、仮説）を作成または更新するとき THEN 開発者は直接 `docs/` ディレクトリに書き込まず、`.spec/discovery/` 配下の対応するマスターファイルに書き込む SHALL
  - WHILE 上流探索成果物を記述している間 WHERE 根拠のないターゲット数値やペルソナ情報があるとき THEN 開発者はその情報を `TBD` または `[proto / 未検証]` と明示する SHALL
- **検証手段**: SKILL.md / references の目視確認 + skill-validator チェックリスト
- **Revision History**:
  - 1.0 (2026-07-12) 初版（実装 v1.4.5 からの reverse-derived。ワークスペース新設に伴う逆起票）
