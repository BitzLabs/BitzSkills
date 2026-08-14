---
id: QLT-DSC-005
title: "bitz-quality レビュー基盤 ペルソナとジャーニー"
status: draft
version: 1.0
updated: 2026-08-14
owner: br7.hide
---

# ペルソナとジャーニー

## P1: SDD開発者

- Job: Design Gate前に、必須観点を漏らさずレビューし、指摘を追跡可能にしたい。
- Journey: target確定 → profile選択 → 並列review → synthesis → schema検査 → 人間Gate。
- Failure: モデルごとに形式が揺れる、P0/P1が消える、古いtargetのPASSを採用する。

## P2: プラグイン保守者

- Job: 観点やplatform adapterを追加しても公開schemaと既存consumerを壊したくない。
- Journey: schema/profile変更 → contract test → platform qualification → versioned release。

## P3: Gate裁定者

- Job: 応答全文ではなく、根拠・例外・未追跡事項・互換性を短時間で検分したい。
- Journey: synthesis確認 → blocking/agenda分離 → decision-ref記録 → Gate裁定。
