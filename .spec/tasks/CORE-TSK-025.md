---
implements: CORE-FR-011
depends_on: []
boundary: scripts/spec, tests/test_spec_wrapper.py, .spec/requirements/CORE-FR-011.md, .spec/design/DSN-004.md, .spec/specs/spec-wrapper-codex-resolution/test-spec.md, .spec/spec-issues/SI-CORE-034.md, .spec/STATE.md, .spec/reviews/
status: done
---

### scripts/spec のClaude/Codex横断解決

- **作業内容**:
  - overrideを最優先に維持し、Codex CLI discoveryとClaude固定版を候補モデルへ統合する。
  - discovery状態別のcache縮退、安全側停止、単一完全版、厳格SemVer、fingerprint検証を実装する。
  - fixtureだけでCodex-only / Claude-only / 共存・競合・破損・timeout・custom CODEX_HOMEを検証する。
  - 要件1.1、設計、issue、test-spec、状態ログを実装・検証結果へ同期する。
- **検証結果**: 対象pytest 25件・全pytest 328件・release_check・overrideなし実地statusはgreen。
  全ワークスペースinspectは既知baselineだけでexit 1（本変更による新規問題0件）。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
