---
implements: FLW-NFR-001
depends_on: FLW-TSK-010
boundary: evals/flow-core/fixtures/v2-skill/
status: done
---

### v2 SKILL.md の入口拘束を強化する（SI-FLW-008 accepted）

- **作業内容**: 裁定記録 `.spec/reports/decision-2026-08-05-si-flw-008-entry-protocol.md`
  に従い、v2 fixture の SKILL.md 本文を構造で是正する。`FLW-DSN-010` の
  「SFCR 未達なら文章を長くするのではなく description・入口数・command 命名・
  result の next action を改善する」に従い、**行数を増やさずに拘束力を上げる**。

  1. **入口の拘束を本文の最初の行へ置く**。見出しの直後に禁止事項を「してはならない」形の
     単文で置き、スキルを読んだ時点で制約が有効になることを明示する。
     `FLW-DSN-010` が固定する本文の節順（Mandatory entry protocol → Intent routing →
     Plan / apply rule → Stop conditions → References routing）は変更しない。
  2. **`NEXT` を無視した場合の扱いを明示する**。M0 第2ラウンドで agy が
     `git diff --stat --summary HEAD~1 HEAD` を自力で組み立てた事象に対応し、
     比較元は `--base <ref>`（既定 `HEAD`）で指定するものであり、
     ref を自分で組み立ててはならないことを Intent routing と compact の節に置く。
  3. platform 別の文面分岐は行わない（`CORE-CON-004` スキルの自己完結）。
     共通文面で効く言い回しだけを採用する。

- **完了条件**:
  - v2 fixture の SKILL.md が上記1〜3を満たし、`FLW-DSN-010` の節順と
    「本文に通常経路の生 `git` / `gh` 例を置かない」制約、目標 100〜150 行を維持していること。
  - fixture の frontmatter `metadata.version` を semver で bump し `updated` を更新していること。
  - 稼働中の v1 スキル（`plugins/bitz-flow/skills/flow-core/`）と配布物を変更していないこと。
- **備考**: 提案4（3 platform での M0 再実測）は本タスクの範囲外とし、`FLW-TSK-012` で行う。
  再実測は `SI-FLW-010`（harness の corpus 共有による state_change 誤検知）の解消後に実施する
  ——先に解消しないと state_change の真偽を raw log と突き合わせる必要が残るため。
  本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
