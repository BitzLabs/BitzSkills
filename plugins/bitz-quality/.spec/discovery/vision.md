---
id: QLT-DSC-001
title: "bitz-quality レビュー基盤 プロダクトビジョン"
status: draft
version: 1.0
updated: 2026-08-14
owner: br7.hide
---

# プロダクトビジョン

## Vision

Claude Code、Codex CLI、Antigravity 2.0のどれを使っても、レビュー観点・入力範囲・出力schema・
Gate判定・追跡規則が同じ契約に収束し、人間が個々のモデル応答ではなく例外とGateを裁定できる状態を作る。

## Target Group / JTBD

- AIエージェントで仕様・設計・コードを開発し、レビュー品質をモデルの即興から分離したい開発者。
- BitzSDDのDesign/Promotion Gateへ、機械検査可能なレビュー結果を入力したい利用者。
- 「変更対象を渡したら、必要な専門観点が選ばれ、重複排除済みの指摘と判定を得たい」。

## Product

論理Reviewer契約、review profile、platform adapter、個別結果schema、synthesizer、監査可能な統合結果を
提供するQA provider。SDDのstatus/GatePassage、FlowのGit/PR強制は所有しない。

## Non-goals

- LLM推論を完全に決定的にすること。
- SDD要件statusやGitHub PRをqualityが直接変更すること。
- 初回リリースで`sdd-review`を削除すること。
- 特定モデル、特定platform、特定アプリのエージェント定義を唯一の正にすること。
