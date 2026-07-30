---
id: CORE-CON-012
version: 1.0
status: draft
domain: governance
priority: high
origin: SI-CORE-038
verification_method: unit-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### CORE-CON-012 SKILL.md のスクリプト呼び出しは基準を明示する

- **説明**: SKILL.md に書くスクリプト実行例は、**どこを基準にした相対パスかを表記から判別できる**
  形にする。実測（2026-07-30、bitz-sdd）ではスクリプト呼び出し32件のうち31件が
  `python3 scripts/<name>.py` という基準の書かれていない形で、リポジトリ相対ともスキル相対とも
  読める状態だった。スキルは任意のプロジェクトへ配置されるため、読み手（人間もエージェントも）は
  この表記から実行すべきパスを決定できない。さらに、そのうち5件は**自スキルに存在しない
  スクリプト**（`sdd_sync.py` は sdd-docs 配下）をスキル相対に見える形で参照しており、
  `CORE-CON-004`（スキルの自己完結）に反していた。表記を3分類に固定して機械検証する。

  | 参照先 | 表記 |
  |---|---|
  | 自スキル同梱のスクリプト | `<このスキル>/scripts/<name>.py`（スキル相対と明示する） |
  | 他スキル同梱のスクリプト | **パスで書かない**。スキル名で言及する（`CORE-CON-004`） |
  | 消費先リポジトリのスクリプト（`scripts/spec` 等） | リポジトリ相対でよいが、プラグイン同梱ではない旨を添える |

- **受入基準 (EARS)**:
  - WHEN SKILL.md が自スキル同梱のスクリプトを実行例として示す THEN パスを `<このスキル>/scripts/` から始まる形で表記すること SHALL
  - WHEN SKILL.md のスクリプト実行例を検査する THEN 基準の書かれていない裸の `scripts/<name>.py` 形式を規約違反として非ゼロで報告すること SHALL
  - WHEN SKILL.md が自スキルに存在しないスクリプトをパスで参照している THEN `CORE-CON-004` 違反として非ゼロで報告すること SHALL
  - WHEN SKILL.md が消費先リポジトリのスクリプトを示す THEN スキル同梱ではないことが本文から判別できること SHALL
  - WHEN 検査対象の SKILL.md を集める THEN `plugins/*/skills/*/SKILL.md` を動的に収集し、新規に追加された SKILL.md も明示的な登録なしに対象へ含めること SHALL
  - WHEN スクリプトを持たないスキルの SKILL.md を検査する THEN 違反も警告も報告しないこと SHALL
- **検証手段**: `tests/test_skill_script_reference.py`（新設）で unit-test する。`CORE-CON-011` の
  `tests/test_cli_contract.py` と同型に、`plugins/*/skills/*/SKILL.md` を動的収集して
  実行例のパス表記を検査し、参照先スクリプトの実在をスキルフォルダ内で解決する。
  既存の全 SKILL.md が PASS することを導入時に確認する。
- **Revision History**:
  - 1.0 (2026-07-30) 初版（draft 起票）。`SI-CORE-038` 提案4 と
    `decision-2026-07-30-order7-scope.md` 裁定F から導出。
