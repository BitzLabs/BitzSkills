---
id: SI-SDD-011
raised_by: 4プラグインの Discovery docs 同期（2026-07-18）
target: sdd-docs の Discovery 成果物同期マッピング不足
proposed_change_type: modify
status: accepted
---
- **目的**: sdd-discovery は vision / metrics / scope / personas / positioning の5つを
  `docs/01-context/` へ同期すると規定するが、`sdd_sync.py` の `DEFAULT_MAPPING` は vision と scope のみで、
  metrics・personas・positioning・scope 内の constraints を同期できない。6ステップの結論を
  docs ナラティブ層へ漏れなく展開できるようにする。
- **提案する修正**:
  1. `metrics.md` → `success-metrics.md`、`personas.md` → `personas-journeys.md`、
     `positioning.md` → `positioning.md` のマッピングを追加する
  2. `scope.md` から non-goals と constraints を決定的に分割するか、`.spec` 側成果物を分ける契約を設計する
  3. 5成果物すべての pull / diff / push 方針と欠損時 SKIP をテストする
  4. SKILL.md の同期表と実装のマッピングを単一の正に寄せ、二重定義の再発を防ぐ
- **対象ファイル**: `skills/sdd-docs/scripts/sdd_sync.py`、`skills/sdd-docs/SKILL.md`、
  `skills/sdd-discovery/SKILL.md`、`tests/test_sdd_sync.py`、関連する SDD-FR 要件、bitz-sdd マニフェスト。
- **確認観点**: Discovery 5成果物から docs/01-context の mission-vision、success-metrics、non-goals、
  constraints、personas-journeys、positioning が生成され、`docs_inspect.py --strict` を通ること。
- **影響推定・ロールバック**: 公開同期マッピングの追加であり契約変更のため軽量レーン不可。
  マッピング・テスト・要件を一括 revert すれば現行2ファイル同期へ戻せる。
- **依存**: SI-SDD-010（docs frontmatter と本文同期の契約統一）。
- **予備判定（推薦）**: **accept 推奨**。スキル手順と実装が乖離し、利用者が正常終了しても
  Discovery 成果物の一部が docs に現れない。SI-SDD-010 後に通常フローで実装する。
- **実施**: 2026-07-29 SDD-FR-149（Discovery成果物のdocs同期マッピング網羅）/ SDD-FR-150
  （同期マッピングSSOTと文書側同期表の一致検証）として要件化し、PR #117 で実装・verified。
  提案2は `.spec` 側成果物を分ける契約（`constraints.md` の独立）を採用し、対応を 1:1 に保った。
  提案4は `release_check.py` の sync-mapping マーカー照合で機械検証する。
  Design Gate 裁定は `.spec/reports/decision-2026-07-29-si-sdd-011.md`。
  既存ワークスペースの `scope.md` にある制約節の切り出しは裁定点3により対象外。
