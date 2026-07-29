---
implements: SDD-FR-151, SDD-FR-152
depends_on: []
boundary: skills/sdd-test/scripts/spec_verify.py, skills/sdd-test/SKILL.md, tests/test_spec_verify.py
status: done
---

### 検証コマンドの実出力から機械可読証跡を記録する

- **作業内容**: `spec_verify.py record` を新設し、検証コマンドを実行して
  `.spec/verification/<command-id>--<commit短縮>.json` へ証跡を書く。安定項目と
  観測値（実行時間）を分離し、同一 commit・同一 command-id は上書きして冪等にする。
  raw 出力・環境変数は保存せず、秘密値らしき引数と実行者ホームの絶対パスは記録を拒否する。
  証跡ディレクトリ自身の差分は dirty 判定から除外し、記録が次の記録を自己ブロックしないようにする。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
