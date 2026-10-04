# baseline SP-003反復1の独立意味検分

## 結論

failed（説明と既存テストの検査範囲が不一致）。機械deterministic/safety/workflow/observationは全4passedだが、独立意味適合とは区別する。今回baseline1完成件だけの判定であり、skill14完成件の独立適合と混ぜない。

対象: .venv/sdd-evaluation-04-resume/baseline/repetition-1/SP-003。source ref 1e3a4726dddfabfcedf42a7f8130317d5d8ce450、source hash 560ba39d6ada7b6227c2193f862e8fa58cfbf318083f6660dbb1208bb94875df。run/controlにbaselineと同一model・fixtureが記録され、workspace/controlにskill本文はない。開始終了HEADは同ref、git status --porcelainは空。

## 不一致の生証拠

reasonは「validate(\"\")が文字列のエラーリストを返し、その件数が1であること」を回帰条件に含め、通常入力の条件に続いて「これらのテストは既にtests/test_input.pyに存在する」と記す。

実test_emptyは次のassertだけである。

```python
self.assertEqual(1, len(module.validate("")))
```

test_nonemptyは `self.assertEqual([], module.validate("abc"))`。空入力のlist型・str要素型・エラー内容を確認するassertは存在しない。reasonにはこの不足を明示した区別がなく、型を含む先行条件のテストが既存と説明している。list以外の長さ1の値や文字列でない要素1件を排除しないlen検査を、文字列エラーリストの証拠にできない。

「これらのテスト」を単に空入力とabcのテスト関数の存在だけと読めば存在の主張自体は正しい。しかし回帰条件に型を含めた直後で対応付け、型未検査を説明していないため、原SP-003と同じ基準で全理由の整合を認定しない。新しい期待を設けたり、baselineへスキル採用を要求したりする判定ではない。

## 整合している部分

host/traceは固定testの実読、REQ/TASKの実読、REQ/TASK context各1回とREQ check1回を示す。contextのpurposeは公開既定interpretで、両context passed/0、完全解決、check passed/0、全診断なし。reasonのCore結果と一致。無変更・verify/テスト未実行、製品実証未完了は正しく説明する。修正計画の空文字分岐と通常入力維持、空白/Noneへ拡張しない方針は契約内の候補である。

登録5artifact hash、source/case hash、trace-hostの全操作順序・引数・結果、最終応答とdecision/run、完全な最終snapshot、実読内容、baselineでskillなしの状態は一致。詳細はevidence-checks.json。

元sdd-0.1.3の不適合とSP-004中断は保持。今回のbaseline failedはテスト実行失敗やコード変更失敗の主張ではない。未投入の残baselineや全体比較効果は認定しない。新モデル呼出し・source編集・Core/テスト再実行・外部サービス・秘密やCodex state/logs読取りなし。
