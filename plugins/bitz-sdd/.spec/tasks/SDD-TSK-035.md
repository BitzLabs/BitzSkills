---
implements: SDD-FR-143
depends_on: []
boundary: skills/sdd-core/scripts/spec_inspect.py, skills/sdd-core/references/lifecycle.md, tests/test_spec_inspect.py, .spec/requirements/SDD-FR-143.md, 3マニフェスト
status: done
---

### baseline監査によるCLI迂回の事後検出

- **作業内容**: `spec_inspect.py` の `check_state_events()` へ baseline 監査を追加する。
  workspace の `.spec/PROJECT.md` frontmatter が `audit_baseline: <commit-ish>` を宣言している
  ときのみ作動し、未宣言なら git を一切呼ばず従来どおり無検査で PASS させる（オプトイン）。
  判定は「未記録の到達状態」で行う: baseline 時点の status と、STATE の記録済み event の始点
  （event が無ければ現 status）を突き合わせ、両者が食い違い、かつ未記録の到達状態が
  人間裁定必須状態（approved / promoted / deprecated / accepted / rejected / superseded）
  なら `audit-corruption` として FAIL する。baseline commit を解決できない場合（git 不在・
  repo 外・SHA 未解決）は FAIL させず WARN として報告する。
  `references/lifecycle.md` に `audit_baseline` の記法と監査契約を追記し、
  `tests/test_spec_inspect.py` へ未宣言時の無検査・未記録 promotion の検出・
  記録済み遷移の非検出・git 解決失敗時の WARN の unit-test を追加する。
  bitz-sdd を minor bump し、release_check と全 pytest で検証する。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
