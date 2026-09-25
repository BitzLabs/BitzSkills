---
id: ADR-054
title: 規範文のlocal-idをFrontmatterの参照形式へそろえる
status: accepted
relations:
  requires:
    - ADR-013
  related:
    - ADR-005
    - ADR-051
---

# ADR-054 規範文のlocal-idをFrontmatterの参照形式へそろえる

## Context

Core 1.0の実装（Step 2）で、EARS-AI Core構文仕様の字句規則とFrontmatter Schemaの字句規則が
食い違っていることが判明した（[Gate B認定記録](../../../tests/bitz-core/Gate-B認定記録.md) 2026-09-25 Step 2）。

[EARS-AI言語・Semantic IR仕様 §2.1](../../03.詳細設計/01_EARS-AI/01_言語・Semantic-IR仕様.md#21-id)の
`local-id`は[ADR-013](ADR-013_文書IDとローカルIDの字句規則訂正.md)以来

```ebnf
local-id = alnum, { alnum | "-" } ;
```

であり、英数字で始まり英数字とハイフンだけを含む文字列を広く受理する。一方、Frontmatter Schema
（`docs/03.詳細設計/schemas/frontmatter.schema.json`の`idString`）が`tests[].covers`や`relations`から
statement IDを参照するために要求する規範文部分の形式は

```regex
[A-Z][A-Z0-9-]*-[0-9]{2,}
```

であり、大文字始まりで末尾が「ハイフン＋2桁以上の数字」の文字列だけを受理する、より狭い部分集合である。

この差により、`ac1`のようなEARS-AI構文としては妥当な`local-id`を持つ規範文が書けるが、その規範文IDは
Frontmatter Schemaの形式に一致しないため`tests[].covers`や`relations`から一切参照できない。参照できない
規範文IDは、それをMUSTとして課しても`verify`のtest対応要求（[関係・トレースモデル §8](../../03.詳細設計/02_SPECモデル/04_関係・トレースモデル.md#8-coverage)）を
満たす手段がなく、`verify`を必ず`blocked`にする。この不整合はCore 1.0の実装（Step 2）が両者を別々に検査する
ことで暫定的に吸収していたが、規範文としては未解決のまま残っていた。

## Decision

1. **`local-id`の狭小化**: EARS-AI言語・Semantic IR仕様 §2.1の`local-id`を、Frontmatter Schemaの`idString`の
   規範文部分と同じ集合になるよう改める。

   ```ebnf
   local-id = upper, { upper | digit | "-" }, "-", digit, digit, { digit } ;
   ```

   （`upper`、`digit`は同仕様§3で定義済みの終端を再利用する。）
2. **Diagnostic**: この規則に反する`local-id`を持つ規範文IDは`EAI-CORE-ID-001`（`EAI-ID-FORMAT`）とする。
   既存の`document-id`側の規則は変更しない。
3. **本ADRが訂正する範囲**: 本ADRは[ADR-013](ADR-013_文書IDとローカルIDの字句規則訂正.md)の`local-id`の
   字句規則だけを部分改訂する。`document-id`の規則、Core 1.0の配置可能な文書接頭辞、ADR-005の他の決定は
   変更しない。

## Consequences

- Frontmatterの`relations`・`tests[].covers`から参照できない規範文IDを新規に書けなくなり、
  「書けるが参照不能」という状態を早期にDiagnosticで検出できる。
- 既存fixtureのうち、新形式に反する`local-id`を使うものは規範文どおりに追従が必要になる。fixtureの変更は
  Core実装の変更と同一commitに含めない（[ADR-051](ADR-051_適合fixtureの変更手続きを確定する.md)）。
- Core Parserは`local-id`の字句検査を新しい規則へ更新する必要がある（後続commit）。
- 既存の妥当な`local-id`（例: `AC-01`）は新形式にすでに適合しており、通常の記述慣行への影響はない。

## Alternatives

1. **Frontmatter Schemaの`idString`を`local-id`と同じ広い集合へ広げる**: 字句規則の食い違いは解消するが、
   英数字とハイフンだけからなる任意の文字列（例: `ac1`）が規範文IDとして許容されたままになり、
   参照不能な規範文IDを早期に検出できないという根本問題が残る。採用しない。
2. **現状維持（Coreが両者を別々に検査する）**: Step 2の暫定実装のまま規範を変えない案。実装の解釈だけに
   依存し、規範文として一意に決まらない状態が続くため採用しない。

## Notes

- 反映先: [EARS-AI言語・Semantic IR仕様 §2.1](../../03.詳細設計/01_EARS-AI/01_言語・Semantic-IR仕様.md#21-id)。
- 影響するfixtureとCore Parserの追従は後続commitで行う。

## Revision History

| Date | Summary | Reference |
|---|---|---|
| 2026-09-25 | 初版を作成。EARS-AIの`local-id`をFrontmatter Schemaの`idString`と同じ集合へ狭小化 | ADR-013 |
