---
id: ADR-069
title: 適合試験のCIをdigestで固定したコンテナで実行する
status: accepted
relations:
  requires:
    - ADR-056
---

# ADR-069 適合試験のCIをdigestで固定したコンテナで実行する

## Context

ADR-056は、適合試験の分割の間で実行環境（`host_tool_versions()`のPython・uv・Gitの版）が完全に一致することを求める。
CIのジョブは`runs-on: ubuntu-24.04`で動くが、このラベルはrunnerのイメージの版を固定しない。GitHubはイメージを
段階的に入れ替えるので、同じrunの中でも版が混在する。2026-10-27には、PR BitzLabs/BitzSkills#384、mainへのpush、
PR BitzLabs/BitzSkills#386で、分割1だけが新しいイメージ（Git 2.56.0）に当たり、集約が
`分割間で実行環境が一致しません`で失敗した。適合試験そのものは全件`passed`だった。
対策の案と比較は提案33にある。

## Decision

1. **一致の要求は変えない**: ADR-056の、分割と独立2組の間の実行環境の完全一致を維持する。比較から項目を外したり、
   版の違いを許したりしない。
2. **分割と集約をコンテナで実行する**: 適合試験の分割のジョブ（`conformance-shards`）と集約のジョブ
   （`conformance`）は、CI用のイメージをdigestで指定したコンテナの中で実行する。イメージの定義は
   `.github/ci-image/Dockerfile`に置き、基底のイメージをdigestで、uvを版とSHA-256で、Pythonを版で固定する。
   PythonとuvとGitはイメージに焼き込み、ジョブの中で入れたりダウンロードしたりしない。GitはUbuntu 24.04の
   配布物の版になり、buildのたびに変わりうるので、固定はpushしたイメージのdigestで行う。
   コンテナのジョブはsetup-uvを使わず、GHCRから読むための`packages: read`と認証情報を持つ。
3. **置き場所と更新**: イメージは`.github/workflows/ci-image.yml`でbuildし、GHCR（`ghcr.io/bitzlabs/bitzskills-ci`）へ
   pushする。ci.ymlはpushしたイメージをdigestで参照する。定義の変更と、ci.ymlのdigestの更新は別のPRで行う
   （digestはpushの後でしか決まらないため）。digestを更新するPRでは、Coreの単体試験・適合試験を通し、
   mainへの統合の後にGate AとGate Bの認定が通ることを確かめる。
4. **更新の時期**: Python・uv・Gitのいずれかを上げる必要が生じたとき（他のジョブのsetup-uvの版を上げるとき、
   Coreの対象環境の変更、セキュリティの修正）に更新する。定期の更新はしない。
5. **失敗の文言**: 集約が実行環境の不一致で失敗したときは、違った項目と値を文言に出す。1組の中の分割の間の
   不一致は分割ごとの値を、独立した組の間の不一致は組ごとの値を示し、2組のときは不一致が起きた組も示す。

## Consequences

- runnerのイメージの入れ替えの間も、分割の間の実行環境が一致する。
- 適合試験の実行環境のGitはUbuntu 24.04の配布物の版になり、runnerのGitより古くなる。CoreはGit 2.30以上を
  要求する（`gitutil.MIN_GIT_MINOR`）ので、イメージのbuildのたびに`.github/ci-image/check-versions.sh`で
  Gitが下限以上であること、uvとPythonが固定した版であることを判定する。
- 他のジョブ（監査、単体試験、分割計画、Gate Aの認定）は、分割の間の一致を求めないので、runnerのまま実行する。
  Gate Bは集約のジョブの中で判定するので、コンテナで実行する。
- イメージの更新は、定義の変更とdigestの更新の2つのPRになる。

## Alternatives

- **Gitを各ジョブで入れる**: 配布元の版の固定が難しく、uvやOSのライブラリの差は残る。
- **Gitのパッチ番号の違いを許す**: ADR-056の目的（独立した実行の一致）と衝突し、Gitに依存するfixtureの違いを見落とす。
- **運用で回避する（Re-run all jobs）**: 入れ替えの期間はCIが失敗し続け、「Re-run failed jobs」では必ず失敗する。

## Notes

- この決定は2026-10-27に提案33の推奨（案Aと失敗の文言の改善）として起票し、利用者が判断を委任した。
- 根拠となる記録: 提案33、PR BitzLabs/BitzSkills#386 の run 40511612002 の各分割のログ。

## Revision History

| 日付 | 変更 |
|---|---|
| 2026-10-27 | 起票し、利用者の委任により`accepted`とする |
