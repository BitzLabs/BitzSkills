# 検討書 — M0 eval 測定系の健全性（全10ラウンド再解析）

- **日付**: 2026-08-07
- **作成**: claude（司令塔セッション）
- **対象**: `FLW-DSN-014` の M0 出口条件と `evals/flow-core/m0-eval/` の採点系
- **方法**: **再実測を行わず**、リポジトリに確定済みの trial 記録 23 ファイル
  （全10ラウンド・v2-skill 732 trial を含む計 1,000 超 trial）を再解析した。
  fixture からの baseline 実測と `flow.py` の直接実行のみ追加で行った
- **契機**: `SI-FLW-017` / `SI-FLW-018` / `SI-FLW-019` の裁定材料の作成。
  10 ラウンドを回して出口に到達していない状態が続いており、
  個別 issue の裁定の前に測定系そのものが判定に耐えるかを確認した

## 要旨

1. **未起票の測定系欠陥を 3 件発見した**（発見1〜3）。うち 1 件は
   **`SI-FLW-017` の推奨修正が機能しないこと**を意味する。
2. **Cross-model Decision Parity は初回ラウンドから一度も達成可能でなかった**。
   実際のパリティは全ラウンドで 100% である。
3. 測定系を是正すると、**第10ラウンドの不合格は実質 1 事象に収束する**
   （`SI-FLW-018` の生 git 直行）。
4. `FLW-DSN-014` の本文は 2026-08-05 の裁定（`SI-FLW-009` → `FLW-NFR-008`）に
   追随しておらず、**要件と実装の双方に矛盾している**。

## 発見1 — `exit_code` 計装が 3 runner で非等価（→ `SI-FLW-020`）

`exit_code` の実体が runner ごとに違う。

| runner | 実体 | `flow.py` の exit 2 を捕捉 |
|---|---|---|
| codex-cli | Codex event の `item.exit_code`（実値） | ○ |
| claude-code | `1 if item["is_error"] else 0`（Bash tool の error flag） | ○ |
| **antigravity** | 出力に `error` / `failed` / `exit code: 1` を含むかの文字列判定 | **×** |

`flow.py` は `--base HEAD~1` に対し実際には exit 2 を返す（fixture 実測）。

```text
$ flow.py --repo <small> git diff-summary --base HEAD~1
INVALID_INPUT git.diff-summary cause=invalid-ref stage=inspect
exit=2  bytes=63
```

この文字列に `error` / `failed` / `exit code: 1` は含まれないため、agy は 0 と記録する。

v2-skill 条件の全ラウンド集計。

| platform | v2 trial | flow.py 呼出 | 非ゼロ exit の観測 | `self_retried` |
|---|---:|---:|---:|---:|
| claude-code | 240 | 226 | 2 | 2 |
| codex-cli | 312 | 399 | 11 | 11 |
| **antigravity** | 180 | **242** | **0** | **0** |

出力 byte 長で同定すると、agy は `diff-summary` だけで **38 回 INVALID_INPUT を受けている**
（OK は最小 220 B、INVALID_INPUT は 63〜64 B で判別可能。`--help` は約 1541〜1570 B）。

| ラウンド | INVALID_INPUT 呼出 | 該当 trial | 採点対象が INVALID | 非ゼロ exit で記録 |
|---|---:|---:|---:|---:|
| r2 | 3 | 3 | 0 | 0 |
| r3 | 10 | 9 | 0 | 0 |
| r7 | 10 | 10 | **1** | 0 |
| r8 | 7 | 7 | 0 | 0 |
| r10 | 8 | 8 | **2** | 0 |

**帰結**

- `SI-FLW-017` の推奨案1（`exit_code == 0` の一致を優先）は、agy では全 `exit_code` が 0 の
  ため**選択結果が現行と一切変わらない**。欠陥が観測された当の platform で無効である。
- `self_retried` は `any(exit_code not in (0, None)) and len(relevant) > 1` であり、
  **agy では構造的に永久 false**。`sfcr()` はこれを失敗として数えるため
  **agy の SFCR は過大評価**されている。
- Cross-model Decision Parity を、platform 間で等価でない計装の上で比較している。

**`SI-FLW-017` の記述の訂正**: 「第10ラウンドで表面化」「第8Rはたまたま失敗呼出が先に来ていた」は
不正確である。順序依存の露出は **r7 と r10 の 2 ラウンド**であり、r8 は INVALID_INPUT 呼出
7 件があったものの採点対象にはならなかった。

**修正の方向**: compact 出力の先頭トークンは `result-v1.schema.json` の `code` enum
（11 値）であり、**platform の event contract に依存せず読める**。採点と `self_retried` を
これに切り替える。

## 発見2 — Decision Parity が corpus をまたいで比較（→ `SI-FLW-021`）

```python
by_task[trial["task"]][trial["platform"]].add(key)   # ← corpus を落としている
```

trial は small / medium / large の 3 corpus に散っている（r1 から一貫）。`dirty-status` の
`decision` は corpus ごとに `changed=8` / `changed=34` / `changed=124` と当然に異なるため、
同一 platform 内でも「判定が揺れている」と数えられる。

| ラウンド | 現行（task 単位） | (task × corpus) 単位 |
|---|---:|---:|
| r7 | 1/3 = **33%** ❌ | 9/9 = **100%** ✅ |
| r8 | 1/3 = **33%** ❌ | 9/9 = **100%** ✅ |
| r10 | 1/3 = **33%** ❌ | 9/9 = **100%** ✅ |

合格していた 1/3 は `repo-inspect` のみ。この task の `decision` は corpus 非依存のため
たまたま素通りしていた。docstring は既に「**同じ fixture・同じ task で**3platform の判定が
一致した割合」と書いており、**実装が docstring に追いついていない**。

**この欠陥は数値の悪化を伴わなかった**。10 ラウンドすべてで同じ FAIL 行を出力し続けながら、
どの spec-issue にも起票されていない。`SI-FLW-019` の「良い数値が測定系の欠陥を隠す」より
悪い形であり、**恒常的な FAIL 行が背景化していた**。

## 発見3 — 計装が runner 間で不均一

`_task_output` は `run_codex` を `common` として 3 runner が共用するが、`observation` 辞書は
各 runner が個別に構築している。`SI-FLW-012` / `SI-FLW-014` で追加した歯止め用の field は
**`run_codex.py` にしか存在しない**。

| field | 導入 | codex | claude | agy |
|---|---|:-:|:-:|:-:|
| `empty_output_positions` | SI-FLW-012 | ○ | × | × |
| `task_output_missing` | SI-FLW-012 | ○ | × | × |
| `help_invocations` | SI-FLW-014 | ○ | × | × |

「除外を黙って捨てない」という裁定時の歯止めが、**codex-cli でしか効いていない**。

## 発見4 — `FLW-DSN-014` が裁定に追随していない

| 出典 | status の byte 削減閾値 | 分母 |
|---|---|---|
| `FLW-DSN-014` 本文（v1.4） | **70%** | no-skill でエージェントが実際に消費した出力（`SI-FLW-007`） |
| `FLW-NFR-008`（2026-08-05 裁定） | **40%** | 固定 baseline `git status` 長形式 |
| `score.py` の実装 | **40%** | 同上 |

`FLW-DSN-014` の `implements:` は `FLW-NFR-008` へ更新済みだが**本文が旧のまま**であり、
設計文書が要件と実装の両方に矛盾している。`SI-FLW-019` の原因1
「測定量の定義が仕様に無く、実装が事実上の仕様になっている」の最も直接的な実例である。

## 測定系を是正したときの第10ラウンド

| M0 出口条件 | 現行採点 | 測定系是正後 |
|---|---|---|
| Invocation ≥95% / baseline +20pt | 97 / 100 / 100%、+96.7〜100pt | 同じ ✅ |
| SFCR ≥90%（platform 別） | 97 / 100 / **93**% | 97 / 100 / **100**%（※）✅ |
| Cross-model Decision Parity 100% | **33%** ❌ | **100%** ✅ |
| 必須 field 保持 100% | **97.2%** ❌ | **99.1%** ❌ |
| golden schema 一致 100% | 100% ✅ | 同じ ✅ |
| 危険事象 各 0 件 | raw_fallback **1** ❌ | 同じ **1** ❌ |
| byte 削減 40% / 80% | 47.9% / 89.0% ✅ | 同じ ✅ |
| coverage 10 trial/cell | 充足 ✅ | 同じ ✅ |

※ 採点対象の是正で 2 trial が回復する一方、`self_retried` の是正で agy の SFCR は
**下がる可能性がある**（発見1 の帰結）。上表は採点対象の是正のみを反映しており、
`self_retried` 是正後の値は再採点で確定させる必要がある。

第10ラウンドの残る不合格の内訳。

```text
必須 field 落ち 3 件
  antigravity  diff-summary small  trial=1   ← 発見1（採点対象が INVALID_INPUT）
  antigravity  diff-summary large  trial=9   ← 発見1（同上）
  claude-code  diff-summary medium trial=2   ← SI-FLW-018（生 git 直行。first=raw-git）

危険事象 1 件
  claude-code  diff-summary medium trial=2   raw_fallback
```

**測定系を是正すると、第10ラウンドの不合格は `claude-code / diff-summary / medium / trial 2`
の 1 事象に収束する。**この 1 trial が必須 field 落ち・raw_fallback・SFCR/Invocation の
減点を同時に起こしている。すなわち `SI-FLW-018` の生 git 直行が、
**M0 出口を塞いでいる唯一の実質的な事象**である。

## 測定系欠陥の全体像（`SI-FLW-019` の表の更新）

`SI-FLW-019` は測定系 6 件・被測定物 7 件と整理しているが、本再解析で **9 件**になる。

| 種別 | 件数 | ID |
|---|---:|---|
| **測定系（harness・採点規則）** | **9** | 007, 009, 010, 012, 014, 017, **020**, **021**, （発見3 は未起票） |
| 被測定物（dispatcher の契約） | 3 | 006, 011, 015 |
| 被測定物（SKILL.md の誘導） | 4 | 008, 013, 016, 018 |

測定系が被測定物の 1.3 倍である。`SI-FLW-019` が「個々の bug ではなく `FLW-DSN-014` の
設計不足として扱う」とした判断は、本再解析で強く裏付けられた。

## 検討の限界

- **raw event log がリポジトリに無い**。trial 記録は per-call の出力テキストを持たず
  byte 長のみを保持する。INVALID_INPUT の同定は byte 長による近似であり
  （diff-summary は 63〜64 B と OK 最小 220 B が明確に分離するため信頼できるが）、
  `repo-inspect` は OK 99 B / INVALID_INPUT 61 B と近く、同じ手法では分離できない。
  **`repo-inspect` と `dirty-status` の INVALID_INPUT 件数は本検討では未確定**である。
- 必須 field 保持の再採点は、フリップする trial の**同定**までであり、
  `_required_fields` の再実行は行っていない。確定値は harness 修正後の再採点で得る。
- 本検討は claude（単一モデル）が実施した。測定系の妥当性検証という主題上、
  独立した検証が望ましい。

## 次アクションの候補

1. `SI-FLW-020` / `SI-FLW-021` を裁定し、`SI-FLW-017` を 020 へ統合して閉じる。
   いずれも**再実測なしの再採点**で効果を検証できる。
2. `SI-FLW-019` の必須項目 1〜3 で恒久化する。案3（harness 自己診断）は
   「**常に FAIL している条件**の検出」を含める（発見2 は数値の悪化を伴わなかったため）。
3. 発見3（計装の不均一）を起票するか、`SI-FLW-019` の案1 の一部として吸収するかを裁定する。
4. `FLW-DSN-014` を `FLW-NFR-008` へ追随させる（発見4）。
5. 以上を反映したうえで `SI-FLW-018` の対策を入れ、再実測ラウンドで測る。
