# 裁定記録 — M1-6 confirmation の範囲

- **日付**: 2026-08-12
- **裁定者**: hide
- **対象**: `FLW-DSN-015` の M1-6 区分（confirmation）
- **提示した選択肢**: A（実 GitHub canary でフル confirmation）/ B（local-only confirmation）/
  C（qualification のみ 3 platform 実走）/ 保留

## 裁定

**C を採用する** — qualification を 3 platform で実走して active manifest を発行し、
**被測定物の confirmation は M2 以降へ送る**。

## 根拠

1. **縮退規則3との整合**: `FLW-DSN-014` は「M2 未完了では worktree-first の安全境界が閉じないため
   M1 Git write を公開しない」と定める。公開しない operation を 3 platform で正式確認しても、
   その証跡は公開時の担保にならない（公開時には worktree 境界が加わり前提が変わる）。
2. **cross-host 証明の不在**: 同設計は「cross-host で予約と lease を証明できなければ
   write confirmation を `UNSUPPORTED` にする」と定める。実 GitHub を使わない現状では
   remote-write の confirmation は成立しない。
3. **M1 出口条件は充足済み**: 「M1 所属 operation の contract 全行・fault fixture・重複 commit 0」は
   M1-3（fault 17件）・M1-4（contract 全行・重複 commit 0）・M1-5（fault 13件）で機械検証済み。
   残るのは「3 platform 正式確認と active manifest」であり、その被測定物を
   **計測器そのもの**に限定するのが C である。

## 範囲

- **含む**: 3 platform（claude / codex / antigravity）で qualification を**実走**し、
  `Q-NORMAL` / `Q-REJECT` / `Q-CORRUPT` を各ちょうど1件、合格条件を満たすことを実測する。
  PASS した manifest を active manifest として発行する。
- **含まない**: M1 operation（read / local-write / remote-write / doctor）の被測定物 confirmation。
  実 GitHub canary の作成。remote-write の実行。

## 影響

- M1 の出口は「contract 全行・fault fixture・重複 commit 0」で満たされる。
- **v2 の Promotion Gate へは進まない**。M1 operation は引き続き `UNSUPPORTED` で、
  active manifest が示すのは「計測器が 3 platform で適格である」ことに限られる。
- M2 以降で worktree-first の安全境界が閉じた後、被測定物の confirmation を行う。
  そのときは本裁定の前提（縮退規則3・cross-host 証明）を再確認する。

## 記録すべき実績

M1-6 完了時に、合成自体の運用コスト（台帳の整合検査・失効判定の保守）の実績を
run manifest へ記録し、M2 以降の budget 再校正の材料とする
（`decision-2026-08-12-m1-5-roi.md` の Go 条件で積み残した項目）。
