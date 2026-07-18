# scripts/docs_inspect.py

docs/ 側（人間ナラティブ層）の構造検証。`.spec/` 側の `spec_inspect.py` と対になる。
stdlib のみ（pyyaml 不要）。

## 使い方

```bash
python scripts/docs_inspect.py <repo-root>          # → docs-inspection-report.md
python scripts/docs_inspect.py <repo-root> --json   # 機械可読
python scripts/docs_inspect.py <repo-root> --strict # WARN も非ゼロ終了に含める
```

ERROR があれば終了コード 1（CI ゲート用）。`--strict` で WARN も失敗扱い。

## spec_inspect.py への統合

同じ Finding モデル（severity / code / path / message）なので、1 関数として取り込める:

```python
from docs_inspect import run_docs_checks
findings += run_docs_checks(repo_root)   # .spec/ の検査結果に docs/ 側を合流
```

Verify フェーズと Promotion Gate では両方を実行し、レポートを人間に提示する。

## チェック一覧

| code | severity | 内容 |
|---|---|---|
| FM_ABSENT | ERROR | 非 exempt 文書に frontmatter が無い |
| FM_MISSING | ERROR | 必須項目欠落（id/title/status/version/changeImpact/project_type/updated/owner） |
| FM_ENUM | ERROR | status / changeImpact / project_type が enum 外 |
| FM_SEMVER | ERROR | version が semver でない |
| FM_DATE | WARN | updated が ISO 日付でない |
| ID_FORMAT | ERROR | id が DOC-\<area\>-\<slug\> 形式でない |
| ID_DUP | ERROR | id 重複 |
| AREA_MISMATCH | ERROR | id の英語areaが日本語章の許容集合と不一致 |
| LAYOUT_MISSING | ERROR | 必須6章のいずれかが無い |
| LAYOUT_LEGACY | ERROR | 旧英語8章が日本語6章と混在 |
| LAYOUT_UNKNOWN | ERROR | 未定義の番号章がある |
| OPTIONAL_UNKNOWN | ERROR | 未対応の optional_chapters を宣言 |
| OPTIONAL_UNDECLARED | ERROR | 06_リファレンスがあるが reference 宣言が無い |
| OPTIONAL_MISSING | ERROR | reference 宣言があるが 06_リファレンスが無い |
| EXCLUDED_INVALID | ERROR | 管理章またはdocs外を excluded_paths で隠そうとしている |
| SUPERSEDE_MISSING | ERROR | status=superseded なのに superseded_by が無い |
| SUPERSEDE_DANGLING | ERROR | superseded_by が実在しない DOC-id を指す |
| REG_GHOST | ERROR | MASTER.md レジストリ行に対応する実ファイルが無い |
| REG_ORPHAN | WARN | 実在するが MASTER.md 未登録（decisions/・postmortems/・テンプレ・_ 始まりは除外） |
| PT_MASTER_MISSING | WARN | MASTER.md に project_type 宣言が無い |
| PT_NO_PUBLIC_API | ERROR | project_type=library/both なのに 公開API.md が無い |
| PT_APP_HAS_PUBLIC_API | WARN | project_type=app に library 専用 公開API.md がある |
| PT_DOC_CONFLICT | WARN | 文書の project_type が MASTER(app/library) と矛盾 |
| ADR_BRIDGE | WARN | requirements.yaml の decided_by ADR に対応する decisions/ADR-*.md が無い |

## 検査対象外（exempt）

`_` 始まり（_conventions.md, _scaling.md）、`*-template.md`、`README.md`、
`意思決定/` と `ポストモーテム/` 配下の実体。MASTER.md は frontmatter は検査するが orphan 対象外。

## 自己検査

同梱テンプレート一式は本スクリプトを 0 件で通過する（`python scripts/docs_inspect.py <この束>`）。
意図的違反フィクスチャで全 code の発火を確認済み。
