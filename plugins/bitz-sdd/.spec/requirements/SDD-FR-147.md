---
id: SDD-FR-147
version: 1.1
status: verified
domain: verification
priority: medium
origin: SI-SDD-014
verification_method: unit-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### SDD-FR-147 実装コードディレクトリの参照走査対象拡張

- **説明**: 参照走査の実装ディレクトリが `src` 決め打ちであるため、実装コードを
  `scripts/`・`hooks/`・`skills/<name>/scripts/` へ置くプロジェクトでは、
  要件 ID を明記した実装コードが存在しても参照として数えられない。走査対象へ
  これらのディレクトリを加える。ただし「実装からの参照」という指標の意味を保つため、
  追加対象ではコード拡張子のファイルだけを走査し、Markdown（`SKILL.md` 等の解説文書）を
  実装参照として数えない。また追加対象からの参照は未参照判定にのみ用い、幽霊参照判定の
  入力にはしない。実装コードの docstring・ヘルプ・エラーメッセージには使用例としての
  ID が自然に登場し、これらを幽霊参照として扱うと誤検知になるため。
- **受入基準 (EARS)**:
  - WHEN 要件 ID を含む実装コードが `scripts/`、`hooks/`、または `skills/<name>/scripts/` にある THEN 当該要件を未参照として報告しないこと SHALL
  - WHEN 追加走査対象のディレクトリに要件 ID を含む Markdown がある THEN その言及を実装からの参照として数えないこと SHALL
  - WHEN 追加走査対象のディレクトリのコードが存在しない ID に言及する THEN それを幽霊参照として報告しないこと SHALL
  - WHILE 追加走査対象が有効な間 THE `spec_inspect.py` は従来の走査対象（`.spec/specs`・`.spec/tasks`・`tests`・`test`・`src`）における幽霊参照の検出を変更しないこと SHALL
  - WHERE 追加走査対象のディレクトリが存在しないワークスペースにおいて THE `spec_inspect.py` は従来と同一の結果を返すこと SHALL
- **検証手段**: tests/test_spec_inspect.py の unit-test で、(1) `skills/<name>/scripts/` の
  コードが参照する要件が未参照から消えること、(2) 同ディレクトリの Markdown だけが言及する
  要件は未参照に残ること、(3) 追加ディレクトリ内のコードが言及する存在しない ID が幽霊参照として
  報告されないこと、(4) 従来の走査対象での幽霊参照検出が不変であること、(5) 追加ディレクトリを
  持たないワークスペースの結果が不変であることを検証する。
- **Revision History**:
  - 1.0 (2026-07-29) 初版（draft 起票）。SI-SDD-014 から導出、Design Gate の論点2を実装する。
  - 1.1 (2026-07-29) 実装中に、走査対象へ加えた実装コードの docstring 内の使用例
    （`commit_lint.py` の TSK-042、`spec_scaffold.py` の CORE-TSK-001、
    `spec_inspect.py` の FR-012）が幽霊参照として FAIL することが判明。人間裁定により
    「追加走査対象は未参照判定にだけ使う」を採用し、幽霊参照に関する EARS 節を改訂した。
    裁定の所在: `.spec/reports/decision-2026-07-29-si-sdd-014.md`（実装中の追加裁定）
