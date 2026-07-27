---
feature: spec-wrapper-codex-resolution
implements: CORE-FR-011
design: DSN-004
status: verified
verification_method: example-test
updated: 2026-07-27
---

# scripts/spec Claude/Codex横断解決 テスト仕様

## 検証マトリクス

| 要件・設計判断 | テストケース | 期待結果 |
|---|---|---|
| override最優先 | override固定版、Codex CLI非呼出し | 指定ルートだけから解決 |
| Codex valid | fake CLI installed+enabled、custom CODEX_HOME | CLI versionと同一のcache固定版を実行 |
| authoritative-negative | disabled / uninstalled / no-entry | Codex cacheを迂回せずClaudeのみへ縮退 |
| unavailable / corrupt | CLI不在・非ゼロ・timeout / JSON不正・出力過大 | 状態契約どおりfallbackまたはCodex除外 |
| Claude pinned | projectPath一致 / 不一致 | 一致固定版を優先、不一致はcacheへ |
| 固定版検証 | manifest欠落・version不一致・4ツール欠落 | 他版へfallbackせずexit 3 |
| 複数固定版 | version差 / 同版fingerprint差 / 同一実体 | 差異はexit 3、一致時だけ決定的選択 |
| cache fallback | strict SemVer、release/RC、不正名、全4ツール | 最大の完全な単一plugin版を選択 |
| 実行境界 | 引数・終了コード、実行直前再検証、実行時消失 | 透過または整形済みexit 3 |
| 診断 | 解決不能・曖昧性・discovery障害 | 安全な分類、探索ルート、override/再試行を表示 |
| 基本契約 | 未知ツール・引数なし・version直書き禁止 | usage失敗、ソース検査green |

## 実行コマンド

- 対象: `.venv/bin/pytest tests/test_spec_wrapper.py -q`
- 全体: `.venv/bin/pytest tests/ -q`
- リリース: `python3 scripts/release_check.py`
- 仕様: `python3 scripts/spec inspect --workspace . plugins/* --check-only`

## 検証結果

- status: verified
- evidence:
  - `.venv/bin/pytest tests/test_spec_wrapper.py -q` → 25 passed / exit 0
  - `.venv/bin/pytest tests/ -q` → 328 passed / exit 0
  - `python3 scripts/spec status . --json` → overrideなしでCodex cache 2.8.0を解決 / exit 0
  - `python3 scripts/release_check.py` → PASS / exit 0
  - `python3 scripts/spec inspect --workspace . plugins/* --check-only` → exit 1。
    変更対象の問題は0件で、着手前からの既知baseline
    （rootのSDD-FR-999幽霊参照、bitz-sddのEARS lint 10件とSDD-REV-001幽霊参照）のみ残存。
