---
implements: SDD-FR-148
depends_on: []
boundary: skills/sdd-core/scripts/spec_inspect.py, tests/test_spec_inspect.py
status: done
---

### manual-check要件の未参照報告を別セクションへ分離する

- **作業内容**: `inspect()` の未参照リストを `verification_method` で二分し、
  自動検証手段（manual-check 以外）の要件を従来の見出しへ、`manual-check` の要件を
  専用の見出しへ列挙する。manual-check 側には検証記録で担保される旨の注記を添える。
  未参照の検出そのものは取りやめず、PASS / FAIL 判定にも影響させない。
  レポート冒頭のサマリ行は未参照件数を含まないため変更しない。
  `tests/test_spec_inspect.py` に、manual-check 要件が自動検証側へ現れないこと・
  専用見出しへ列挙されること・自動検証要件が従来どおり列挙されること・
  終了コードが不変であることを検証する unit-test を追加する。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
