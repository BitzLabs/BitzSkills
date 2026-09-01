---
id: ADR-014
title: Semantic IRと段階的Context Projection
status: accepted
relations:
  related:
    - ADR-010
    - ADR-015
---

# ADR-014 Semantic IRと段階的Context Projection

## Context

EARS-AIをLLMへ渡す方法には、原文Markdownをそのまま渡す案、ASTのJSONだけを渡す案、両方を渡す案がある。
原文だけでは、規範文、説明、例をLLMが実行ごとに再解釈するため、句単位の検査、網羅性、digestを決定論的に
扱えない。一方、全依存文書についてASTと原文を同時に渡すと情報が重複し、遠い依存の背景説明によって
起点の意図が希釈される。

依存深度で探索自体を打ち切る案は、末端の`MUST`や禁止事項を欠落させる。必要なのは依存解決の省略ではなく、
完全に解決した結果からLLMへ渡す表現を段階化することである。

## Decision

1. Markdownを人間が編集する正本として維持し、Parserは規範文を軽量なSemantic IRへ変換する。
   既存の互換名称として`AST`を残すが、Lexer tokenやMarkdown装飾を公開する具象構文木にはしない。
2. Semantic IRはID、出典、主体、発動条件、規範強度、処理、拡張、参照を保持し、Core、Profile、
   Context Resolutionの共通機械契約とする。LLMにEARS-AIの構文解析を委ねない。
3. Context Resolutionは強い依存を先に完全解決し、型、状態、循環、上限を検査してからProjectionを生成する。
   段階的提示を探索打切りや部分成功として扱わない。
4. 完全解決したapplicable文書の規範文をConstraint Ledgerへ収録する。全`MUST`は依存距離にかかわらず
   LLMへ明示し、深い依存にあることを理由に参照だけへ落とさない。
5. 文書の提示を`full`、`normative`、`reference`の3段階とする。既定Projectionは規範強度、purpose、role、
   TASK対象性を優先し、依存距離はその後の判断材料にする。
6. 追加参照は、同じ起点とpurposeに対する`bitz context --expand <document-id>`で行う。改訂履歴は
   `--expand <document-id>#revision-history`で明示展開する。常駐サービスや
   セッション状態を新設せず、同じ入力から同じ結果を返す。
7. Context Digestは完全解決した意味集合から計算し、Projectionの違いを含めない。実際の提示内容には
   別のProjection Digestを付ける。
8. Coreとアダプター間の正規契約はJSONとする。LLM向けMarkdownはJSON/Semantic IRから生成し、
   独立した意味解釈を加えない。SPEC由来テキストは引き続き未信頼データとして扱う。

## Consequences

- ParserとSemantic IRは引き続きPhase 1の必須成果物となるが、詳細な具象構文木は不要になる。
- LLMは全`MUST`と作業境界を最初に確認でき、背景・例・advisoryは必要な場合だけ追加参照できる。
- 完全性の判定とトークン節約を分離でき、Projectionを変更してもstale判定の意味は変わらない。
- `context`のJSON Schemaに`resolution`、`constraintLedger`、`projection`、`projectionDigest`が追加される。
- CoreはProjectionの再現性と、解決集合外の文書を暗黙追加しないことを検査する必要がある。
- 構造化データだけでは伝わりにくい背景や設計理由は原文に残り、明示展開によって利用できる。

## Alternatives

1. **全原文だけを渡す**: LLMが構文と規範性を再解釈し、モデル間で判定が揺れる。
2. **Semantic IRだけを渡す**: 背景、理由、例が失われ、曖昧な判断時に原文へ戻れない。
3. **全ASTと全原文を常時渡す**: 情報が重複し、トークン消費とコンテキスト希釈が増える。
4. **依存深度で探索を打ち切る**: 深い位置の必須制約を欠いた部分コンテキストを正常に見せる。
5. **LLMに参照先を自由探索させる**: 選択が非決定論的になり、参照漏れをCoreが検出できない。

## Notes

次のDecision項目が後続ADRによって部分改訂されている。本ADRの他のDecisionは有効である。

| 対象 | 後継ADR | 内容 |
|---|---|---|
| Decision 6、7 | [ADR-015](ADR-015_SPEC改訂履歴の必須化.md) | 改訂履歴を非規範メタデータとして意味集合から除外し、明示展開時の返却規則と`semanticHash`／`fileHash`の分離を定義 |
| Decision 7 | [ADR-039](ADR-039_Core-1.0仕様構造の再編とscope縮小.md) | `projectionDigest`の公開を取りやめ、公開hashを`contextDigest`だけに限定 |

## Revision History

| Date | Summary | Reference |
|---|---|---|
| 2026-08-27 | 初版を作成 | — |
| 2026-08-27 | Revision Historyの非規範化と明示展開をADR-015で追加 | `ADR-015` |
| 2026-08-31 | Frontmatterと固定H2構成へ移行 | `ADR-020` |
| 2026-08-31 | 部分改訂の対象Decision項目を`Notes`へ明示 | `ADR-015` |
| 2026-09-01 | Decision 7の公開digestが`ADR-039`で変更されたことを注記 | `ADR-039` |
