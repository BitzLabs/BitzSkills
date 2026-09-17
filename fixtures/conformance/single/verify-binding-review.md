# verify binding fixture review

[適合fixture仕様 §6.6](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#66-verify)の
`SINGLE-063`、`SINGLE-064`、`SINGLE-065`を扱う。`SINGLE-066`と`SINGLE-068`は意図してこの回に含めない
（後述の「保留」を参照）。いずれもreview済みの期待値であり、Coreの挙動を観測したものではない。

## 起点を2つ持つworkspace

`SINGLE-063`と`SINGLE-064`には、同じcommand名を要求する2つのtargetが必要である。そのため入力は、1つのworkspace内に
独立した2つの連鎖`REQ-001 ← TECH-001`と`REQ-002 ← TECH-002`を持つ。両TECH文書は、同じcommand名で同じtest path
`tests/test_shared.py`を宣言する。

[verify仕様 §4](../../../docs/03.詳細設計/03_操作仕様/03_verify.md#4-処理)は、targetごとに別の`purpose=verify`の
Contextを解決し、`bindingRefs`の和集合を取り、`(workspaceId, commandName)`ごとにtest pathを重複排除する。
したがって期待値は、Digestが**異なる**2件の`targetResults[]`と、共有pathを1回だけ`tests`に持つ1件の`commands[]`である。

- `SINGLE-063`: 両targetが通過する。`covers`は両規範文を挙げ、`argv`は共有pathを1回だけ展開する。
- `SINGLE-064`: `TECH-001`が`tests`を宣言しないため、`REQ-001:AC-01`はtestのないMUSTとなり、そのtargetは
  `bindingRefs: []`で`blocked`になる。`REQ-002`は実行する。`covers`は`REQ-002:AC-01`だけを挙げる。実行に
  至らなかったtargetの規範文を、commandが対象として主張してはならない。最上位のstatusは2つの最悪値の`blocked`／2である。

## `{tests}`は置換位置であり、末尾への追加ではない

`SINGLE-065`はDigestの入力を再利用し、command templateを`["/bin/true"]`へ縮める。
[verify仕様 §5](../../../docs/03.詳細設計/03_操作仕様/03_verify.md#5-command実行)は、置換位置がなければpathの件数に
かかわらずargvを1回実行するため、`argv`は`["/bin/true"]`のままで、`tests`には宣言した2つのpathが並ぶ。
test pathが`argv`へ漏れないことを回帰試験で確認する。
`argv` templateはDigest材料なので、このfixtureはgoldenではなく固有のDigestを持つ。

## 監査が強制する不変条件

`check_sharing`は次の結果を拒否する。共有bindingが複数のcommand実体へ複製されたもの、test pathが重複排除されて
いないもの、重複排除したpathを複数回展開したもの、2つのtargetが同じDigestを返すもの、非成功のtargetがbindingを
要求したもの。これらはmatrixの行が挙げる性質なので、fieldのliteralな一致だけでなく、性質として検査する。

## 参照計算Bの変更

Bは以前、説明できない強いedgeをすべて拒否しており、起点が1つの入力を前提にしていた。1つのworkspaceに独立した
起点が2つある場合、*もう一方*のContextに属するedgeは正当である。現在の検査は、計算中の閉包に触れるedge
（参照元、参照先、または参照先の規範文を所有する文書が閉包内にあるもの）にだけ働き、閉包内で説明できないものは
引き続き拒否する。この変更がなければ、Bは`SINGLE-063`のどちらのDigestも計算できない。

## 保留

`SINGLE-066`（規範文のないTECHでの文書単位のtest）と`SINGLE-068`（done TASKの起点）は保留する。どちらも、
この参照計算がまだ導出しない閉包の挙動を必要とする。`SINGLE-066`では起点から前向きにたどる`refines` edge、
`SINGLE-068`ではtarget規範文が別の文書にあるTASK起点のContextの内容である。期限に合わせてこれらの形を作らず、
解決の論点を検討・記録する専用の段階で扱う。

## 限界

- Coreは実行していない。Coreとの一致はGate Bで判定する。
- `SINGLE-064`は、registryの`skip-target`という継続単位に従い、`CTX-COVERAGE-TEST-001`をblockedのtargetに置く。
  `SINGLE-060`と一致する。
- 重複排除したpathの順序は、整列した宣言順である。共有pathが1つなので、要素が1つなら一致する整列規則どうしを
  このfixtureでは判別しない。
