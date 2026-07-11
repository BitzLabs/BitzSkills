---
id: ENV-CON-001
version: 1.0
status: approved
domain: guardrail
priority: high
origin: 製作プラン（一般公開の前提条件）
verification_method: manual-check
derived_from:
supersedes:
superseded_by:
confidence: high
---

### ENV-CON-001 deny セットは普遍的最小集合に限定

- **説明**: プラグイン同梱フックの deny 対象は、どのプロジェクトでも無害と言える
  普遍的な破壊的操作の最小集合（rm -rf / git push --force / git reset --hard /
  git clean -f / sudo）に限定する。プロジェクト固有・組織固有の制限は同梱フックに
  足さず、env-init が生成する permissions 側で行う。
- **受入基準 (EARS)**:
  - WHEN env_guard.py の DENY_PATTERNS を変更する THEN 追加パターンは普遍的 破壊的操作であることをレビューで確認 SHALL（一般公開プラグインとして、
    過剰なブロックは他者の環境で邪魔になるため）
  - WHERE プロジェクト固有の制限が必要な場合 THE システムは permissions 生成 （env-init）で対応する SHALL
- **検証手段**: コードレビュー（PR）+ tests/test_env_guard.py の pass ケース維持
- **Revision History**:
  - 1.0 (2026-07-11) 初版
  - 1.0 (2026-07-11) 人間裁定により approved 化（チャット指示）
