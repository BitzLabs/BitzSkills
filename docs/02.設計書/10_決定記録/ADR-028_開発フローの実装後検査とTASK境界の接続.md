---
id: ADR-028
title: 開発フローの実装後検査とTASK境界の接続
status: accepted
relations:
  requires:
    - ADR-025
  related:
    - ADR-009
---

# ADR-028 開発フローの実装後検査とTASK境界の接続

## Context

Small Flowは`Intent -> Context -> Check -> Implement -> Verify -> Done`であり、`Check`は実装の前に
1回だけ置かれていた。運用設計も`bitz check`を「編集直後」としながら、フロー図では実装前に配置していた。

一方[ADR-025](ADR-025_Git基準版とcheck明示対象の確定.md)は、TASK IDまたはTASKファイルpathを明示した
`bitz check`だけがTASK `changes`との境界比較を行うと定めている。実装前の汎用`bitz check`では、実装によって
新たに生じる変更pathを`changes`と比較できず、実装後に汎用`check`を実行してもTASKを明示しなければ
境界を強制しない。結果として、境界外へ変更を書いたままVerifyとDoneへ到達する経路が存在した。

Full Flowは「品質検査コマンドはSmall Flowと同じものを使う」と述べながら、図では`Check`を1箇所しか
持たず、同じ欠落を継承していた。

## Decision

1. Small Flowの骨格を次へ改訂する。

   ```text
   Intent -> Context -> Pre-check -> Implement -> Post-check -> Verify -> Human Review -> Done
   ```

2. `Pre-check`は実装前の`bitz check`とし、SPECの構文、関係、状態遷移、および既存作業ツリーの
   不適合を確認する。`Post-check`は実装後の`bitz check`とし、実装で生じた変更集合を検査する。
3. TASKを起点とするフローでは、`Post-check`で`bitz check <TASK-ID>`を必須とし、ADR-025の明示対象規則で
   `changes`境界を強制する。Gitが利用できない場合は`SPEC-TASK-BOUNDARY-002`／`blocked`とし、
   暗黙に通過させない。
4. 実装後に静的検査を経ずに`Done`へ到達する経路を作らない。`Post-check`が非成功のままVerifyへ進まない。
5. `Post-check`とVerifyの失敗戻り先を分類する。コンパイル、Lint、単体テスト、境界外変更は`Implement`へ戻す。
   仕様矛盾、要求の意味変更、権限不足は自動修復せず人間確認へ戻す。一時的なツール障害は同じ副作用を
   増やさない冪等な再実行だけを許可する。
6. Full FlowもPre-check、Implement、Post-check、Verifyの同じ骨格を共有する。Full Flow固有のレビュー
   否決edgeと`Done`への接続はUC-FLOW-006として別に裁定する。
   （2026-08-31追記: UC-FLOW-006は同日に裁定し、否決edgeを`04_SDDプロセス設計` §3へ反映した。
   レビューの承認・否決はCoreの機械契約に含めない。）
7. Coreの公開操作は追加しない。本決定はフロー配置と必須呼出しの契約であり、`bitz check`の対象選択規則、
   Diagnostic、終了コードはADR-025と既存仕様のままとする。

## Consequences

- TASK起点の作業で、境界外のコード変更がDoneより前に必ず検出される。
- 実装前後の`check`が別段階として名前を持ち、運用設計の「編集直後」とフロー図が一致する。
- TASKを持たない小さな変更では`Post-check`が汎用`check`となり、境界検査は行われない。境界保証が必要な
  作業はTASKを作る必要がある。
- Small FlowとFull Flowの検査配置が同一になり、Full Flow専用の検査経路を作らずに済む。

## Alternatives

1. **`Check`を1箇所のまま実装後へ移す**: 実装前のSPEC不適合と作業ツリー衝突を検出できず、
   プリフライトの前提が崩れるため採用しない。
2. **汎用`check`でも常に全TASKの`changes`を検査する**: 無関係なopen TASKの境界が現在の変更へ適用され、
   偽陽性が日常化するため採用しない（ADR-025の明示対象規則を維持する）。
3. **境界外変更をwarningにする**: 提案資料READMEでTASK境界のwarning化・自動承認を不採用としており、
   `blocked`を維持する方針と矛盾するため採用しない。

## Notes

- 本ADRは2026-08-31のユースケース・フロー遷移レビューUC-FLOW-001に対する裁定である。
- TASK起点のHuman Review後に`open -> done`と最終checkを行う終端手順は
  [ADR-034](ADR-034_TASK完了終端とdone起点操作の確定.md)で補完する。Decision 1および4は変更しない。
- Decision 4の「非成功」は`failed`、`blocked`、`error`を指し、`passed_with_warnings`は通過することを
  [ADR-035](ADR-035_check空対象とフロー通過statusの確定.md)で明確化した。
- 関連文書: [04_SDDプロセス設計](../03_SDDフロー.md),
  [06_運用設計](../04_運用手順.md),
  [08_実装ロードマップ](../../04.提案資料/12_Core-1.0実装計画.md),
  [09_ユースケース設計](../05_ユースケース.md),
  [SPECファイル規定/05](../../03.詳細設計/02_SPECモデル/03_文書種別・本文テンプレート.md),
  [SPECファイル規定/06](../../03.詳細設計/02_SPECモデル/04_関係・トレースモデル.md)

- 開発フロー骨格へ`Integrate`段階を追加する部分改訂をADR-038で行った。本ADRのDecisionは変更していない。

## Revision History

| Date | Summary | Reference |
|---|---|---|
| 2026-08-31 | Small/Full Flowの実装後検査とTASK明示境界検査を確定 | — |
| 2026-08-31 | UC-FLOW-006の裁定結果をDecision 6へ注記 | `UC-FLOW-006` |
| 2026-09-01 | TASK起点フローの完了終端をADR-034へ接続 | `ADR-034` |
| 2026-09-01 | Decision 4の非成功statusを明確化 | `ADR-035` |
| 2026-09-01 | 骨格へ`Integrate`を追加する部分改訂をADR-038で行った | `ADR-038` |
| 2026-09-03 | ADR-039の再編に合わせて関連文書linkを現構造へ更新（非意味的訂正） | 提案24 G8 |
