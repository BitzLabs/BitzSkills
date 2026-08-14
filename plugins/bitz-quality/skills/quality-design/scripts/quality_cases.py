#!/usr/bin/env python3
"""quality_cases.py — bitz-quality テストケース・データ設計スクリプト

テスト観点から具象テストケースおよび境界値テストデータを生成し、
テストコード雛形（tests/test_<feature>.py）または設計書を出力する。
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

BOUNDARY_PAYLOADS = {
    "empty_string": '""',
    "whitespace_only": '"   "',
    "null_value": "None",
    "zero_integer": "0",
    "negative_integer": "-1",
    "large_integer": "999999999",
    "long_string_10k": '"a" * 10000',
    "special_characters": '"<>&\\\"\'/\\\\;--"',
    "unicode_emojis": '"🎉🚀🛡️✨"',
    "sql_injection": '"\' OR 1=1 --"',
    "xss_payload": '"<script>alert(1)</script>"',
}

def generate_test_scaffold(feature_id: str, title: str) -> str:
    safe_name = feature_id.lower().replace("-", "_").replace(" ", "_")
    lines = [
        f'"""test_{safe_name}.py — {feature_id} {title} の自動テスト"""',
        f"",
        f"import pytest",
        f"",
        f"def test_{safe_name}_happy_path():",
        f'    """正常系: 基本フローが仕様通りに動作すること"""',
        f"    # TODO: 正常系の実装",
        f"    assert True",
        f"",
        f"def test_{safe_name}_invalid_input_fails():",
        f'    """異常系: 不正な入力で適切に例外または非ゼロを返すこと"""',
        f"    # TODO: 異常系の実装",
        f"    assert True",
        f"",
        f"@pytest.mark.parametrize(",
        f'    "payload",',
        f"    [",
    ]
    for key, val in BOUNDARY_PAYLOADS.items():
        lines.append(f'        pytest.param({val}, id="{key}"),')
    lines.extend([
        f"    ]",
        f")",
        f"def test_{safe_name}_boundary_data(payload):",
        f'    """境界値: 特殊・極端な入力値でもクラッシュしないこと"""',
        f"    # TODO: パラメタライズド境界値テストの実装",
        f"    assert payload is not None or payload is None",
        f"",
    ])
    return "\n".join(lines)

def main() -> int:
    parser = argparse.ArgumentParser(
        description="テスト観点からテストケース雛形・境界値データを生成します。"
    )
    parser.add_argument("feature_id", help="フィーチャーID (例: FEAT-001)")
    parser.add_argument("target", nargs="?", default=".", help="プロジェクトルートパス")
    parser.add_argument("--title", default="機能テスト", help="テストタイトル")
    parser.add_argument("--scaffold", action="store_true", help="tests/test_<feature>.py を直接生成する")
    
    args = parser.parse_args()
    target_path = Path(args.target)
    
    code = generate_test_scaffold(args.feature_id, args.title)
    
    if args.scaffold:
        tests_dir = target_path / "tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        safe_name = args.feature_id.lower().replace("-", "_").replace(" ", "_")
        out_file = tests_dir / f"test_{safe_name}.py"
        if out_file.exists():
            print(f"[WARN] 既存ファイルが存在するため上書きをスキップしました: {out_file}")
        else:
            out_file.write_text(code, encoding="utf-8")
            print(f"[✔] テストスキャフォールドを生成しました: {out_file}")
    else:
        print(code)
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
