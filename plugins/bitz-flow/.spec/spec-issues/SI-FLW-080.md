---
id: SI-FLW-080
raised_by: FLW-TSK-106実装前検査
target: FLW-TSK-106/107 schema追加と既存inventory testの変更境界
proposed_change_type: modify
status: accepted
---
- **目的**: 新しいcontract bundle / approval context schemaを加法導入しても、旧schema inventory検査を
  暗黙に破らず、FLW-TSK-106/107の変更境界内で全suiteをgreenにできるようにする。
- **発見した事実**:
  - `tests/test_flow_m2_contract_v2.py`は`schemas/worktree-v2/*.schema.json`を旧9件と完全一致で固定する。
  - `contract-bundle-v2.schema.json`または`approval-context-v2.schema.json`を追加すると同testは必ずFAILする。
  - 同testはFLW-TSK-106/107いずれの`boundary`にも無く、実装者は契約保護規則上変更できない。
  - 旧inventoryにはsigned-capability schemaが含まれる。Local Safety Profileでは配備物として残っていても
    active bundle memberへ入れず、入力検出時に`UNSUPPORTED`へ止める必要がある。
- **提案する修正**: **accept推薦**。`tests/test_flow_m2_contract_v2.py`をFLW-TSK-106と107のboundaryへ追加し、
  各taskで追加したschemaを明示的な期待集合へ加える。legacy schemaの実在とactive bundle membershipを分離し、
  contract bundleの期待member集合は呼出側がcode-owned一覧として明示し、欠落・余剰の双方を拒否する。
- **対象ファイル**: `.spec/tasks/FLW-TSK-106.md`、`.spec/tasks/FLW-TSK-107.md`、
  `tests/test_flow_m2_contract_v2.py`、`plugins/bitz-flow/skills/flow-core/schemas/worktree-v2/`。
- **確認観点**: 新schema追加時のinventory test、legacy signed schemaがactive bundleへ混入しないこと、
  期待memberの部分集合・余剰・重複schema ID拒否、全M2 test suite。
- **影響推定・ロールバック**: テストとtask boundaryだけの補正でruntime挙動は変えない。変更セットをrevertすれば
  旧9件inventoryへ戻るが、新schemaを同時にrevertしない限りsuiteはredになる。
- **依存**: FLW-NFR-014、FLW-DSN-017 v2.1、FLW-TSK-106、FLW-TSK-107。
