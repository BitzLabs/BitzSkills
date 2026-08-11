# 裁定記録 — verified 要件の適用範囲が後続 milestone で広がる場合の扱い

- **日付**: 2026-08-12
- **裁定者**: hide（対話での選択）
- **対象**: `SI-FLW-040`
- **提示した選択肢**: A（M1 スコープの新要件を起票）/ B（ライフサイクルに戻り経路を追加）/
  C（既存要件を milestone ごとに分割）/ D（裁定を保留し write 側だけ進める）

## 裁定

**B を採用する** — bitz-sdd のライフサイクルに `verified → implementing` の戻り経路を追加する。

実装者は A（影響が bitz-flow 内に閉じる）を推奨していたが、裁定者は根本解決である B を選んだ。

## 背景

`FLW-FR-004`（Git 読み取りと工程別診断）と `FLW-CON-002`（Operation Contract と副作用上限）は、
要件本文としてはもともと M1 の範囲を含むが、M0 では read 部分だけを検証して verified になった。
M1 のタスクから `implements` すると `spec_inspect` が
「verified/promoted だが未完了 local task がある」で FAIL し、
`spec update --to implementing` は `precondition-failed: 不正遷移: verified -> implementing` で拒否される。

`FLW-CON-002` は M1-1 で `implements` から外して回避したが、`FLW-FR-004` は
「残る Git read」タスクにとって唯一の該当要件であり同じ回避ができない。

## 影響

- **bitz-sdd の変更**であり、全ワークスペースへ波及する。sdd-core の `spec_update.py` の
  `TRANSITIONS` と `references/lifecycle.md`、および遷移テストが対象。
- bitz-sdd 側は自身の SDD 規律（spec-issue → 要件 → 実装）に従って進める。
  `SI-FLW-040` は bitz-sdd へ**委託**する。
- 本リポジトリは bitz-sdd を**リリース済み版に固定**して消費しているため、
  bitz-sdd の変更が main へ入り、固定版が更新されるまで M1-4 の
  「残る Git read」（`FLW-TSK-042`）と contract 全行検証（`FLW-TSK-046`）は着手できない。
- M1-4 の write 側（`git.fetch` / `git.sync` / `git.publish-branch` / `repo.doctor`）は
  `FLW-FR-005` / `FLW-FR-011` / `FLW-CON-005` / `FLW-CON-006` で表現でき、影響を受けない。

## 設計上の注意（bitz-sdd 側で扱う）

戻り経路を無条件に開くと「verified を取り消して作業をやり直す」ことが常態化し、
verified の意味が薄れる。少なくとも次を検討する。

- 戻り遷移の実行権限（`agent` か `human` か）
- 戻した事実と理由を STATE へ残すこと
- 既存の検証証跡（`.spec/verification/`）を無効化しないこと
- Promotion Gate での検分方法（一度 verified になった要件が再び implementing を経た履歴の扱い）
