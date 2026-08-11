---
id: FLW-CON-001
version: 1.0
status: verified
domain: governance
priority: high
origin: FLW-DSC-003
verification_method: manual-check
derived_from:
supersedes:
superseded_by:
confidence: high
---

### FLW-CON-001 Python 3固定と除外技術

- **説明**: v2の実装言語と採用しない技術を人間裁定どおり固定する。
- **受入基準 (EARS)**:
  - WHEN v2 runtime artifactを実装または変更する THEN bitz-flowはPython 3.10+標準ライブラリだけをruntime実装に使用すること SHALL
  - WHEN runtime dependencyを検査する THEN bitz-flowはPython追加package依存0件を記録すること SHALL
  - WHEN source treeと設計optionを検査する THEN bitz-flowはGo、Rust、MCP、platform固有hook、透過proxyの実装または移行候補0件を記録すること SHALL
  - WHEN Python実装が必須安全契約を満たさない THEN bitz-flowはscope縮小、再設計、No-Goのいずれかを人間へ提示すること SHALL
  - WHEN Python実装が必須安全契約を満たさない THEN bitz-flowは別言語への部分置換、再実装、移行比較を開始しないこと SHALL
- **検証手段**: dependency manifest、source file種別、設計・migration文書、M0〜M5の実装言語を人間が確認し記録する。
- **Revision History**:
  - 1.0 (2026-07-29) Design GateのPython 3固定・Go禁止裁定からdraft起票
