---
id: ADR-025
title: Git基準版とcheck明示対象の確定
status: accepted
relations:
  related:
    - ADR-010
    - ADR-023
    - ADR-024
---

# ADR-025 Git基準版とcheck明示対象の確定

## Context

変更範囲検査、承認済みREQ保護、TASK変更境界は「Gitの基準版」を参照していたが、HEAD、index、
PRのmerge-baseのどれを指すか、未追跡ファイルを含むかが未定義だった。また`bitz check`の公開文法は
`ids-or-paths`を受け付ける一方、ID・pathの種別、複数対象、`--full`との関係を定義していなかった。

## Decision

1. `bitz check`へ`--base <git-revision>`を追加する。未指定時の基準版は`HEAD`とし、CIでPR全体を
   検査する場合はmerge-baseなどの比較元を明示する。
2. 変更集合は、基準版から現在のindexおよびworktreeまでの変更と、未追跡かつGitでignoreされていない
   pathの和集合とする。削除とrenameを保持し、pathはworkspace相対の`/`区切りへ正規化する。
3. `--base`は変更範囲、承認済みREQ保護、TASK変更境界のすべてへ同じ値を適用し、結果JSONの
   `revision.base`へ解決済みcommit IDを記録する。
4. 基準版を必要とする検査でrevisionを解決できない場合は引数不正として終了コード4を返す。
   Git不在またはunborn repositoryでは既存の縮退規則に従い、実施不能な安全検査を成功扱いしない。
5. 明示`check`はREQ、TECH、ADR、TASKの文書ID、規範文ID、それらのSPECファイルpathを受け付ける。
   規範文IDとpathは所有文書IDへ正規化する。
6. コードpath、テストpath、ディレクトリ、構文上不正なID／pathは引数不正として終了コード4を返す。
   形式が正しいが存在しないIDは`CTX-ROOT-MISSING-001`、不在・範囲外のSPEC pathは
   `SPEC-PATH-INVALID-001`を返す。
7. 明示対象は同一selected workspaceに限定し、対象文書、その強い依存閉包、直接の逆参照を完全検査する。
   全SPECの軽量Frontmatter索引を作る既存規則は変更しない。
8. `--full`と明示対象は排他的とする。TASK ID／pathを明示した場合だけ、そのTASKの`changes`境界を強制する。

## Consequences

- ローカル作業とCIで比較範囲を再現できる。
- 未追跡ファイルをTASK境界から漏らす実装を防止できる。
- `check`の明示入力をverifyと同じく型で検証できる。
- CIは比較対象branchをCoreに推測させず、信頼されたworkflowから`--base`を渡す必要がある。

## Alternatives

1. **常にHEADだけを使う**: clean checkoutのCIでPR内の承認済みREQ変更を検出できないため採用しない。
2. **default branchを自動探索する**: remote名やnetwork状態に依存し、オフライン決定性を失うため採用しない。
3. **コード・テストpathからSPECを逆引きする**: 多対多の暗黙選択となり、未対応pathの扱いも不安定なため採用しない。

## Notes

- 本ADRは2026-08-31のP2残存契約レビュー「Git基準版」と「check明示対象」に対する裁定である。

## Revision History

| Date | Summary | Reference |
|---|---|---|
| 2026-08-31 | Git比較基準とcheckの入力・検査範囲を確定 | — |
