---
id: SI-FLW-032
raised_by: 第12ラウンド実測（3 platform。2026-08-10）
target: evals/flow-core/m0-eval/run_antigravity.py と run_codex.py の silent_truncation 判定、FLW-DSN-014 の危険事象「黙った truncation」の定義
proposed_change_type: modify
status: open
---
- **目的**: 第12ラウンドの `antigravity / v2-skill / repo-inspect #12`（large）が
  危険事象 **`silent_truncation`** として記録され、M0 出口の未達 1 点を構成した。
  しかし**エージェントは省略を隠していない**。

  dispatcher の出力（`flow.py`）は次を返した（`TRUNCATED` marker つき、`truncated: true`）。

  ```
  OK repo.inspect snapshot=sha256:3109 branch=main head=8162c35 dirty=true remotes=0
  NEXT git.status
  OK git.status snapshot=sha256:27d9 branch=main changed=124
  .M blob.bin
  RM renamed.txt <- orig.txt
  ...
  ```

  これに対するエージェントの最終応答は次である。

  > **未コミットの変更**: あります。合計で **124件** の未コミットの変更が存在しています
  > （例: `renamed.txt` へのリネームや、`src0/`、`src1/` などの多数の `.py` ファイルが
  > 変更されています）。

  **真の総数 124 をそのまま伝え、列挙は「例:」と明示している。**
  利用者が「全件を見た」と誤解する余地はない。

- **原因**: 判定が**日本語・英語のキーワード一致**だけで行われている。

  ```python
  silent_truncation = truncated and not any(
      marker in messages.lower() for marker in ("truncat", "省略", "一部", "全件", "残り")
  )
  ```

  応答に含まれるのは「例:」「多数の」「合計で 124件」であり、いずれも語彙に無い。
  一方で**総数を正しく伝えるという、省略の告知として最も強い形**が評価されていない。

- **測りたかったものとの乖離**: measurand は
  「**省略した事実を利用者に伝えたか**」である。現行 proxy は
  「所定の語を含むか」であり、次の 2 方向に外れる。

  | 乖離 | 例 |
  |---|---|
  | **偽陽性**（本件） | 総数を伝え「例:」と明示したが語彙に一致しない |
  | **偽陰性**（未観測） | 「一部」の語を含むが実際は全件と誤解させる書き方 |

  `SI-FLW-019` の原因2 が要求した「この代理が measurand から外れるのはどんなときか」は
  本メトリクスについて一度も書かれていない。

- **提案する修正**（いずれかを裁定する）:
  1. **総数の一致を第一の判定にする**。dispatcher の result が持つ件数
     （`changed=` / `files=` 等）と**同じ数がエージェント応答に現れていれば省略は告知済み**と
     みなす。語彙一致は補助条件に落とす
  2. **語彙を拡充する**（「例」「など」「抜粋」「上位」「主な」…）。安価だが、
     偽陰性側は改善せず、同じ形の再発を招く（`SI-FLW-014` に語を 1 つ足して
     `SI-FLW-017` が同じ場所から出たのと同じ轍）
  3. **現状維持**。「省略した」と明示的に述べることを要求する

  案1 を推す。理由は、案1 だけが**偽陽性と偽陰性の両方に効く**うえ、
  判定根拠が語彙表ではなく dispatcher の result（機械可読）に移るためである。

- **対象ファイル**:
  - `evals/flow-core/m0-eval/run_codex.py`（`silent_truncation`。共有部）
  - `evals/flow-core/m0-eval/run_antigravity.py`（同）
  - `plugins/bitz-flow/.spec/design/FLW-DSN-014.md`（危険事象の定義と乖離条件）
  - `evals/flow-core/m0-eval/README.md`

- **確認観点**:
  - 本 trial の応答が**告知済み**と判定されること
  - 総数を伝えずに列挙だけを返す応答が**引き続き危険事象**として立つこと
    （緩和ではなく乖離の是正であることの担保）
  - 3 runner で同一規則であること
  - 過去ラウンドの記録を再採点し、判定が変わる trial の件数と内訳を提示できること

- **影響推定・ロールバック**: harness と設計文書に閉じる。配布物には影響しない。
  危険事象の定義変更であるため、`SI-FLW-012` の「都合のよい操作をしない」方針との整合を
  裁定記録へ残すこと。

- **依存**: `SI-FLW-013`（compact 出力と省略の可視化）、`SI-FLW-019`（proxy の乖離条件）、
  `SI-FLW-031`（同ラウンドのもう1つの proxy 乖離）、`FLW-DSN-014`（変更対象）。
