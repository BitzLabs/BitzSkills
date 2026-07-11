---
implements: [ENV-NFR-001]
depends_on: []
boundary: tests/test_env_guard.py
status: done
---

### env_guard.py の応答時間ベンチマーク

- **作業内容**: tests/test_env_guard.py に、代表入力（allow / deny / 不正 JSON の各ケース）で
  env_guard.py の1回のフック処理が 200ms 以内に完了することをアサートする
  ベンチマークテストを追加する（ENV-NFR-001。benchmark）。
- **備考**: CI 環境の揺らぎを考慮し、閾値は要件の 200ms を守りつつ flaky にならない計測方法
  （subprocess 起動込みの経過時間）を選ぶ。
- **実施記録**: 2026-07-11 実施（fast-worker 委譲・司令塔検収済み）。allow/deny/不正 JSON の3ケース×7回計測の最小値で 200ms 判定。pytest 全81件 PASS を司令塔が再実行で確認。
