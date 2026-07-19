---
implements: SDD-FR-132
depends_on: []
boundary: plugins/bitz-sdd/skills/sdd-core/{scripts,references}, plugins/bitz-sdd/skills/sdd-issue/SKILL.md, tests/, .spec/spec-issues/SI-CORE-015.md, bitz-sdd マニフェスト
status: done
---

### 委託フロー規定・spec_inspect 横断検証・scaffold 拡張

- **作業内容**: SDD-FR-132 の受入基準に従い、テスト先行で以下を実装する:
  1. tests/test_spec_inspect.py に委託チェックの回帰テストを追加
     （後方互換 PASS / リンク切れ FAIL / 双方向欠如 FAIL / 注記付き origin 容認 / 正常委託 PASS）
  2. spec_inspect.py に spec-issue 専用ローダーと `delegated_to` 横断検証を追加
     （要件ローダーとは分離。status 語彙・ID 正規表現の誤検知を避ける）
  3. spec_scaffold.py の spec-issue 雛形で `--origin` / `--delegated-to` を受ける
     （tests/test_spec_scaffold.py に生成テスト追加）
  4. lifecycle.md に委託フロー節を追加（2方向 + サブ↔サブ禁止 + ルート SPEC 不在時 + 書式）
  5. sdd-issue SKILL.md の「未規定の項目は本文の自由記述で補う」注記を更新
  6. bitz-sdd マニフェスト bump（minor）
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
