# done TASK起点fixture review

[適合fixture仕様 §6.6](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#66-verify)の最後の行である
`SINGLE-068`を扱う。これでverifyの節は完了する。
review済みの期待値であり、Coreの挙動を観測したものではない。

## 先に契約を確定した

このfixtureは、期待値が未確定の論点に依存していたため、それまでの2回の作業では保留していた。起点TASKが
`addresses`する参照先を所有する文書が、**verify**のContextに含まれるかという論点である。
[適合fixture仕様 §3.3](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#33-実成果物との対応)は、
契約より先にfixtureを追加することを禁じているため、先に契約を確定した。

[関係・トレースモデル §6.3](../../../docs/03.詳細設計/02_SPECモデル/04_関係・トレースモデル.md#63-verify)は現在、
これを直接述べている。起点TASKは、`addresses`する参照先とそれを所有する文書を`contextDocuments`へ含め、
その文書から`interpret`の閉包規則を適用する。`implement`と異なり、起点TASKの`requires`閉包は含め**ない**。

新しい決定はしていない。[verify仕様 §3](../../../docs/03.詳細設計/03_操作仕様/03_verify.md#3-対象)は、TASK targetが
`addresses`する参照先を検証することを既に求めており、その文書がContextの外にあれば実行できない。§6.3がそれを
書いていなかっただけである。変更ではなく欠落の補完であることは、次の2点で独立に確認した。

1. target展開の参照計算は、vectorを最初にreviewした時点からこの読みを実装しており、この編集で**25ケースの期待集合は
   変わらない**。（2026-09-17訂正: 参照計算はverifyの起点TASKでも`requires`をたどっていた。§6.3を正として
   `TASK-REQUIRES-NOT-TARGET`の期待集合と参照計算を修正した。経緯は
   [Diagnostic意味網羅review](../Diagnostic意味網羅review.md)を参照。）
2. Diagnosticの条件は追加しない。`addresses`は強い関係なので、解決できない参照先は既存の
   `SPEC-RELATION-MISSING-001`になる。registryの119条件は変わらない。

監査はこの編集を自分で検出した。Diagnostic reviewの台帳と`targets/cases.json`がこの文書のhashを固定しており、
固定した期待値をreviewし直すまで通過しなかった。再reviewの結果を[Diagnostic意味網羅review](../Diagnostic意味網羅review.md)
に記録し、その後でhashを更新した。

## fixture

`TASK-001`は`done`で、`REQ-001:AC-01`だけを`addresses`する。起点がcancelledでblockedになる
`SINGLE-067`の、成功側の対である。

| | `SINGLE-067` cancelled | `SINGLE-068` done |
|---|---|---|
| status | `blocked`／2 | `passed`／0 |
| `contextDigest` | `null` | 固有の値 |
| `statements` | `[]` | `["REQ-001:AC-01"]` |
| `bindingRefs` | `[]` | `["root::default"]` |

Contextは3文書を持つ。起点のTASK、`addresses`する規範文を所有する`REQ-001`、`REQ-001`を具体化しtest対応を持つ
`TECH-001`である。したがってDigest材料の`documents[]`は、コードポイント順に`REQ-001, TASK-001, TECH-001`となる。

**`AC-02`は意図して`addresses`しない。** 同じREQの規範文だが、起点TASKのtargetは所有文書の全規範文ではなく、
TASK自身の`addresses`から決まる。そのため`AC-02`はtargetにならず、それを対象にするtestもbindingへ入らない。
`tests`は`tests/test_auth.py`だけ、`covers`は`REQ-001:AC-01`だけを持つ。どちらかが混入した結果を監査は拒否する。
これが、`SINGLE-055`のREQ起点とTASK起点を区別する点である。

## 限界

- Coreは実行していない。Coreとの一致はGate Bで判定する。
- このfixtureは、`addresses`する参照先が解決できるTASK起点を固定する。追記した文が定めるもう一方の非成功の分岐
  （解決できない`addresses`の参照先は、targetを空にせず失敗させる）はmatrixにfixtureがなく、既存の
  relation不在の行だけで扱う。
- この起点TASKは`requires`を宣言しないため、verifyで`requires`閉包を含めない規定は、このfixtureでは判別しない
  （後に`SINGLE-110`で判別した）。
