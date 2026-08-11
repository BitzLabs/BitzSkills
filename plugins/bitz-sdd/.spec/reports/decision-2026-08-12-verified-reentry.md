# 裁定記録 — verified 要件の再着手経路をライフサイクルへ追加する

- **日付**: 2026-08-12
- **裁定者**: hide（対話での選択）
- **対象**: `SI-SDD-040`（bitz-flow `SI-FLW-040` からの委託）
- **委託元の裁定記録**: `plugins/bitz-flow/.spec/reports/decision-2026-08-12-verified-requirement-rescope.md`

## 裁定

**ライフサイクルに `verified → implementing` の戻り経路を追加する**（委託元で提示した選択肢 B）。

委託元の実装者は「影響が bitz-flow 内に閉じる新要件起票」（選択肢 A）を推奨したが、
裁定者は根本解決である本案を選んだ。

## 経緯

bitz-flow の M1-4 着手時に、`FLW-FR-004`（Git 読み取り）が M0 で read の一部だけを検証して
verified になっており、M1 で残る read を実装しようとしても

- 新しいタスクの `implements` に書くと `spec_inspect` が FAIL
- `spec update --to implementing` は `precondition-failed: 不正遷移: verified -> implementing`

となって着手できないことが判明した。`FLW-CON-002` でも同じ問題が M1-1 で起きており、
そのときは `implements` から外して回避したが、`FLW-FR-004` は該当タスクにとって
唯一の要件であり回避できない。

## 歯止め（無条件には開かない）

戻り経路を無条件に開くと「verified を取り消してやり直す」ことが常態化し、verified の意味が薄れる。
次を必須とする。

1. **実行権限は `human`**。人間裁定必須遷移として扱い、`--interactive-decision` か
   `--on-behalf-of`（+ `--decision-ref`）の経路を要求する。機械が勝手に取り消せない。
2. **理由を裁定参照として残す**。なぜ再着手するのかを STATE から辿れるようにする。
3. **既存の検証証跡を無効化しない**。`.spec/verification/` の記録は削除・改変せず、
   再び verified になるときに新しい証跡が追加される。
4. **`promoted` からの戻りは追加しない**。Promotion Gate を通ったものは
   deprecated 経由でのみ変更する（現行のまま）。

## 影響

全ワークスペースへ波及する。本リポジトリは bitz-sdd をリリース済み版に固定して消費しているため、
本変更が main へ入り固定版が更新されるまで、bitz-flow の `FLW-TSK-042` と `FLW-TSK-046` は
着手できない。
