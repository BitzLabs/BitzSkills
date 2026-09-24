"""text出力向けの文字列無害化ユーティリティ。

`結果・Diagnostic・終了コード仕様 §7` に従い、C0（U+0000〜U+001F）、DEL（U+007F）、
C1（U+0080〜U+009F）を ``\\uXXXX`` （backslash 1文字 + 'u' + 小文字16進4桁）へ置換する。
この変換はtext表示だけに適用し、JSON結果やsort順序を変えない。
"""

from __future__ import annotations


def sanitize_control_chars(value: str) -> str:
    out: list[str] = []
    for ch in value:
        code = ord(ch)
        if code <= 0x1F or code == 0x7F or 0x80 <= code <= 0x9F:
            out.append(f"\\u{code:04x}")
        else:
            out.append(ch)
    return "".join(out)
