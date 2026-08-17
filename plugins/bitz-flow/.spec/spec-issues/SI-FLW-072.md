---
id: SI-FLW-072
raised_by: FLW-REV-019（DIN-203 / RSK-404 / RSK-306 / DIN-304 / RVC-302 / DIN-305 / RVC-306 / RVC-307 / RSK-208 / DIN-207 / OPS-202 / RSK-205）
target: audit の通常運用における解除区分の実効性・cause 語彙の schema 反映・設計文書の自己矛盾
proposed_change_type: modify
status: open
---
- **目的**: `SI-FLW-067` の対処（PR #294）で**閉じなかった通常運用上の問題**を閉じる。
  M2 出口条件6と4は今回も未達である。receipt store と保護境界を同時に操作できる主体への
  強い改ざん耐性は V2 のスコープ外とする（裁定:
  `.spec/reports/decision-2026-08-17-v2-operational-integrity-scope.md`）。

- **発見した事実**（独立レビュア複数が別経路で実測）:
  1. **chain 検証は破損を止めたが、整合的な再偽装を止めない**（`DIN-203` critical / `RSK-404`）—
     digest を正しく計算し直した receipt を置けば通る。実測で audit が `OK` へ反転した。
     末尾切詰めも chain が整合したまま通り、次の apply が採番を埋め直すため恒久的に不可視になる。
     **自己整合性の検証には真正性の錨が無い。** この後半は上記裁定により V2 の対象外である。
  2. **`release_class` は公開経路で今も定数**（`RSK-306` / `DIN-304` / `RVC-302`）—
     `classify_quarantine` へ実観測を渡す形にしたが、渡している入力の一部が固定のままで
     到達可能な像が `worktree-unresolved` の1点。検査するはずのテストが恒真になっている。
  3. **`cause: "quarantined"` が公開 schema の enum に無い**（`DIN-305` / `RVC-306`。**新規回帰**）—
     `result.py` の `ALLOWED_CAUSES` にだけ足し、`result-v1.schema.json` へ足していない。
     `build_result` の cause 検査が schema ではなく実装定数を見ているため素通りし、
     `M2-FLT-023` は cause を走査しない。**`ORPHAN` とまったく同じ型の逸脱**である。
  4. **設計文書が自分自身と矛盾**（`RVC-307`）— `FLW-DSN-016` §2 の GP-014 多重語表が
     `ORPHAN` を `worktree_state` の値として列挙し続けており、§7 の追記と正面から対立する。
     schema から機械導出すると 13行中4行が誤り。同節は自ら「手で維持する一覧は必ず腐る」と書いている。
  5. **`INDETERMINATE` の取りこぼし**（`RSK-208` / `DIN-207`）— store が `chmod 000` の形、
     receipts ディレクトリ消失、**自 operation の中断（PARTIAL）**を今も外部起因と誤分類する。
  6. **裁定 案1 の範囲内でも取りこぼす**（`OPS-202` / `RSK-205`）— 手動削除の後に同名の
     空ディレクトリを作り直すと `OK` へ戻り、symlink 差替えも `OK`。
     裁定 A が scope に含めた「binding 不整合」は今も検出されない。

- **提案する修正**:
  - 整合的な再偽装および外部アンカー・鍵管理による真正性の錨は V2 の対象外とする。
  - `QuarantineEvidence` の全入力を実観測から作り、4区分が実際に分岐することを
    **到達可能性テスト**（各区分を生成する fixture）で固定する
  - `cause` の語彙を schema と実装で**単一の正**から導出する（三者照合の対象に加える）
  - `FLW-DSN-016` §2 の多重語表を schema から機械導出するか、表自体を撤去する
  - `INDETERMINATE` の条件へ store 読み取り不能・dir 消失・自 operation 中断を加える
  - binding 検証（`audit_external_binding_change`）を公開 audit から呼び、
    空ディレクトリ・symlink を実体と認めない

- **対象ファイル**: `flowlib/` の `cli.py` / `result.py` / `worktree_runtime.py` /
  `worktree_capability.py` / `worktree_cleanup.py`、`schemas/result-v1.schema.json`、
  `.spec/design/FLW-DSN-016.md`、`tests/test_flow_m2_runtime.py`

- **確認観点**: 偽装・末尾切詰め・空ディレクトリ再作成・symlink・store 読み取り不能・
  自 operation 中断の**それぞれに陽性対照**を置く。4区分すべてに到達する fixture を置く。

- **依存**: M2 出口条件6と4の判定に直結する。Completion Gate の前提。
