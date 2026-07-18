---
implements: CORE-FR-014
depends_on: [CORE-TSK-017]
boundary: plugins/bitz-flow/.spec/discovery/**
status: implementing
---

### bitz-flow の sdd-discovery 実施（FLW- 6成果物）

- **作業内容**: `plugins/bitz-flow/.spec/discovery/` に SI-CORE-005 と同書式の6成果物
  （vision / metrics / scope / personas / positioning / assumptions、プレフィックス FLW-）を
  作成する。書式の前例は plugins/bitz-ddd/.spec/discovery/。仮説検証ゲートの裁定材料
  （SDD 非採用プロジェクトでの単体需要は未検証等のオープン仮説）を assumptions に含め、
  Go / No-Go 裁定は人間に残す。委譲ゲート判定により deep-reasoner へ委譲（量産系・
  司令塔より下位ティアで実行可能）。検収は司令塔が spec inspect + 内容確認で行う。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
