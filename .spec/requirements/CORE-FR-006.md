---
id: CORE-FR-006
version: 1.0
status: verified
domain: governance
priority: medium
origin: SI-CORE-021
verification_method: manual-check
derived_from:
supersedes:
superseded_by:
confidence: high
---

### CORE-FR-006 Execute 委譲ゲート（役割分類と委譲判定の提示）

- **説明**: Execute（実装）フェーズでタスクに着手する前に、各タスクを役割で分類し
  「委譲するか司令塔が自己実行するか」の判定を提示する**委譲ゲート**を sdd-implement に設ける。
  司令塔（起動モデル）が機械的作業まで直接実行してトークンを浪費する構造を是正する。
  判定の詳細手順は sdd-implement の reference（delegation-routing）に切り出し、SKILL.md 本文から参照する。
- **受入基準 (EARS)**:
  - WHEN sdd-implement で承認済み要件をタスクへ分解し着手する前 THEN 各タスクを役割（機械的修正 / 難調査・設計 / 量産 / 検証）で分類すること SHALL
  - WHEN タスクを役割分類した THEN 委譲レジストリに照らして委譲先候補と「委譲 / 自己実行」の判定を提示すること SHALL
  - THE 委譲判定の手順は sdd-implement の reference に定義され、SKILL.md 本文から参照されること SHALL
- **検証手段**: sdd-implement/SKILL.md と reference の inspection。委譲ゲート手順の存在、
  役割分類の4区分、レジストリ参照、reference への切り出しと本文からの参照を確認する。
- **Revision History**:
  - 1.0 (2026-07-13) 初版（draft 起票）
