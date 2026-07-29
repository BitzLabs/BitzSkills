# 裁定記録 — bitz-flow v2 Design Gate

- **日付**: 2026-07-29
- **裁定者**: hide（リポジトリ所有者）
- **対象**: SI-FLW-002〜005の採否、bitz-flow v2 Design Gate
- **裁定の形式**: チャットでの明示裁定を、Codexが
  `--on-behalf-of hide`による代行可視化経路で反映する。本人性は機械検証されない。
- **裁定原文**: 「SI-FLW-002〜005をacceptし、Design Gateを承認します」

## 裁定

1. `SI-FLW-002`をacceptedとし、fetchとinspectの分離、鮮度証跡、工程別診断を
   v2要件へ派生する。
2. `SI-FLW-003`をacceptedとし、状態変更を行わないbranch auditをv2要件へ派生する。
3. `SI-FLW-004`をacceptedとし、branch-only対象をWorkUnit状態機械で扱う。
4. `SI-FLW-005`をacceptedとし、PRをprepare / publish / checks / ready / merge /
   post-mergeへ段階化する。
5. FLW-REV-002の多観点レビューPASS（4.74）とFLW-REV-003のSEレビューPASSを根拠に、
   FLW-DSN-000およびFLW-DSN-002〜014をDesign Gate承認済みのactive設計とする。
6. 現行v1のFLW-DSN-001、FLW-FR-001/002はv2 Promotion Gateまでcurrentとして維持する。

## 追加の人間裁定

- 「200UE」は「ISSUE」の誤記として扱う。
- 実装言語はPython 3.10+に固定する。
- Goによる実装、部分置換、再実装、移行比較は行わない。
- Pythonで必須安全契約を成立させられない場合は、scope縮小、再設計、またはNo-Goを裁定する。
- MCP、Rust、プラットフォーム固有hook、透過proxyは実装対象外のままとする。

## Discovery成果物のstatus解釈

Discovery GateのGoはDiscoveryからDesignへの進行裁定であり、FLW-DSC-000〜006の
frontmatterを`active`へ変える裁定ではない。`sdd-discovery`の成果物は`draft`を維持し、
Goの正は`assumptions.md`と`worksheet.md`のDiscovery Gate記録とする。

このため、Design Gate通過後もFLW-DSC-000〜006が`draft`であることは未裁定や後戻りを
意味しない。フェーズの機械判定はDSCのstatusだけへ依存させず、Gate裁定と後続成果物を扱う
bitz-sdd側の責務とする。

## 残余条件

- cross-host競合はsingle coordinator、marker重複検出、canary即時停止で統制する。
- flow-doctorとflow-coreの共通result envelopeをM1のgolden release gateで検査する。
- M1〜M5の最大PR数、最大作業session数、縮退可能な出荷境界をFLW-DSN-014 v1.1と
  FLW-FR-012 v1.2で定量化した。FLW-DSN-014 v1.2とFLW-FR-012 v1.3では初期budgetと位置づけ、
  milestone開始時の実績記録と人間による予算再確認、上限到達時の継続・scope縮小・No-Go裁定を要求する。

## 次工程

active設計からv2のFR / NFR / CONをEARS形式でdraft起票する。要件のdraft→approvedは
別の人間裁定とし、approved前にM0実装へ進まない。
