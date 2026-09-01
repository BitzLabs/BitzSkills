---
id: ADR-037
title: Git基準版間のSPEC同一性と削除規則
status: accepted
relations:
  requires:
    - ADR-025
  supersedes:
    - ADR-032
  related:
    - ADR-013
    - ADR-036
---

# ADR-037 Git基準版間のSPEC同一性と削除規則

## Context

Git変更集合は削除とrenameを保持するが、削除されたSPEC pathを基準版の文書IDへ対応付ける規則がなかった。
現在版だけを索引すると、承認済み文書や不採用・中止理由を保持する終端文書の削除を状態遷移として検査できず、
モノレポmemberをcatalogから外すことで配下のSPECを検査対象から除外できる。

またADR-032は、1つのGit基準版と現在版の2時点比較で「現在は削除されているIDが別の意味で再出現した場合」を
検出するとした。しかし現在版に同じIDが存在すれば、それが同一文書の移動・改訂か、削除後の再利用かを
中間履歴なしに区別できない。semanticHashの差だけでは正当な改訂との違いを判定できない。

## Decision

1. CoreはGit基準版と現在版について、文書種別、path、Frontmatter IDを読み、連合では
   `(workspaceId, documentId)`、単一workspaceでは実効workspace IDを補った同じ組を文書同一性のキーとする。
2. 基準版と現在版に同じキーが存在する場合は同一文書とする。pathだけが異なる場合はrenameとして扱い、
   本文、状態、関係の変更は既存の保護・遷移規則で検査する。CoreはsemanticHashの差からID再利用を推測しない。
3. 基準版に存在するキーが現在版に存在しない場合はSPEC削除とする。Git管理済みSPECの削除は、種別や状態を問わず
   `SPEC-STATE-TRANSITION-001`／error／`failed`とする。廃止・不採用・中止は`outdated`、`superseded`、
   `rejected`、`cancelled`など既存の状態と理由で表現し、履歴文書を残す。
4. Git基準版に存在しない未追跡の新規SPECを、Gitへ記録する前に破棄する操作はCoreの検査対象外とする。
5. モノレポでは基準版catalogと現在版catalogの両方から索引を作る。memberの削除またはpath変更によって
   基準版側のSPECを現行索引から隠さず、同じworkspace IDと文書IDが現在版にあれば移動、なければ削除として
   Decision 2または3を適用する。SPECを持たないmemberの削除は既存のcatalog検査だけを適用する。
6. 現在集合内の重複は`EAI-CORE-ID-002`および`SPEC-ID-DUPLICATE-001`で検出する。
   `EAI-CORE-ID-003`はCore 1.0のDiagnosticから削除する。削除を含むcommitがCore検査を迂回した後の
   長期的なID再利用禁止はGitレビューの責務とする。
7. Git不在またはunborn repositoryでは基準版索引を作れないため、現在集合の重複と状態語彙だけを検査する。
   SPEC削除と長期的なID再利用を検査できないことをwarningとして表示する。
8. Coreはtombstone索引を構築せず、到達可能Git履歴を走査しない。

## Consequences

- 削除とrenameが実装者ごとのpath推測に依存せず、終端履歴の物理削除も状態遷移として防止できる。
- member catalogの変更で基準版側のSPECを検査から隠せない。
- 2時点比較で証明できない「別の意味」を機械判定せず、正当なrenameや改訂をID再利用と誤判定しない。
- Git全履歴索引や永続状態を追加せず、Core 1.0の決定論性と軽量性を維持する。
- Core検査を経ずに過去の削除がcommitされた場合、後日のID再利用はCoreだけでは検出できない。

## Alternatives

1. **semanticHashが変わったrenameをID再利用とみなす**: renameと同時の正当な改訂を誤検出するため採用しない。
2. **到達可能Git履歴からtombstone索引を構築する**: clone深度で結果が変わり、永続索引と性能負荷も増えるため
   採用しない。
3. **終端文書だけ削除を禁止する**: `draft`や`open`の物理削除で不採用・中止理由の記録を迂回できるため採用しない。
4. **member catalogは現在版だけを読む**: member削除により基準版SPECを検査対象外にできるため採用しない。

## Notes

- 本ADRは2026-09-01の実装前異常ケースレビュー`EDGE-001`に対する裁定である。
- 本ADRはADR-032を文書全体として置き換える。ADR-025のGit基準版と変更集合は変更せず、
  基準版と現在版のSPEC同一性および削除時の効果を追加する。
- 基準版で同一キーが複数pathへ解決する場合の扱いはADR-038で追加した。本ADRのDecisionは変更していない。

## Revision History

| Date | Summary | Reference |
|---|---|---|
| 2026-09-01 | SPEC同一性、rename、削除、ID再利用のCore保証範囲を確定 | `EDGE-001` |
| 2026-09-01 | 基準版の重複キーの扱いをADR-038で追加した旨を注記 | `ADR-038` |
