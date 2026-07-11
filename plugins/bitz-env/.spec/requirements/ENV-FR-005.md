---
id: ENV-FR-005
version: 1.1
status: approved
domain: collab
priority: high
origin: 製作プラン + 実装 v0.1.0（reverse-derived）
verification_method: example-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### ENV-FR-005 モデル非依存の役割割り当てと劣化動作・防御的協調

- **説明**: 協調運用は特定モデルを前提とせず、中心（ユーザー選択モデル）からの
  相対位置で役割（advisor / worker）を定義する。advisor / worker のモデルは env-init の
  セットアップ時に選択して生成する。協調相手が利用不可でも環境全体は停止せず
  劣化動作しなければならない。また LLM をコンポーネントとして組み込む前提として、
  検収は自己申告（DIGEST）に依存せず客観的状態で行い、委譲の再帰には
  ストッパーを設ける（防御的協調）。
- **受入基準 (EARS)**:
  - WHEN env-init を実行する THEN システムは中心モデルを確認し、advisor / worker の 割り当て案を提示してユーザー選択で確定する SHALL
  - IF advisor が利用不可（未生成・プラン制約・障害）THEN システムは相談を スキップして作業を続行し、その旨を成果物に明記する SHALL
  - IF 合議のメンバーが1名しか成立しない THEN システムは相談型へ格下げして実施する SHALL
  - WHEN 中心が worker の委譲結果を検収する THEN システムは DIGEST のみに依存せず、git diff / git status 等の客観的な状態変化を中心自らが取得して検証する SHALL
  - WHERE 委譲・相談を実行する箇所 THE システムは worker / advisor からのネスト委譲（委譲先がさらに別エージェントへ委譲すること）を禁止し、追加委譲の要否は中心のみが判断する SHALL
- **検証手段**: evals/env-init/・evals/env-orchestration/（割り当て分岐・劣化動作・客観的検収・ネスト委譲拒否シナリオ）
- **Revision History**:
  - 1.0 (2026-07-11) 初版（実装 v0.1.0 からの reverse-derived）
  - 1.0 (2026-07-11) 人間裁定により approved 化（チャット指示）
  - 1.1 (2026-07-11) SI-ENV-007 accepted による改訂: 客観的検収・ネスト委譲禁止を追加
  - 1.1 (2026-07-11) 人間裁定により approved 化（チャット指示）
