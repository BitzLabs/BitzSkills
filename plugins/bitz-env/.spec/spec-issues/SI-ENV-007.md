---
id: SI-ENV-007
raised_by: sdd-review 第2ラウンド クロスモデル（agy/Gemini）AGY-3 + AGY-4
target: plugins/bitz-env/.spec/requirements/ENV-FR-005 + collab-contract.md
proposed_change_type: bump
status: accepted
---
- **矛盾/曖昧の内容**: LLM をコンポーネントとして委譲・協調に組み込む際の防御的設計が2点欠落。
  (1) 盲目的な検収: Worker が返す DIGEST（自己申告の要約）のみで Center が検収すると、
  別モデルの幻覚・他ファイル破壊・隠蔽を見逃す。REV-001 は「検収は中心」と述べるが
  客観的な差分確認ステップが要件化されていない。
  (2) 委譲の再帰: Worker がさらに委譲を呼ぶ再帰にストッパーが無く、委譲のピンポンで
  コンテキスト・API コストが枯渇しうる。
- **提案する修正**:
  (a) ENV-FR-005 か collab-contract に「検収は DIGEST に依存せず、git diff / status 等の
      客観的状態変化を Center 自ら取得して検証する」を受入基準化。
  (b) 委譲・相談リクエストに深さ制限（Depth）または相関 ID を持たせ、上限到達で
      追加委譲を禁止（中心が判断）。あるいは「サブエージェントからのネスト委譲は禁止」を制約化。
- **影響推定**: ENV-FR-005 の受入基準追加、collab-contract の検収・再帰条項追加、
  env-orchestration SKILL.md の手順反映。契約変更を含むため Design Gate 対象。
