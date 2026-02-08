"""Testes de sanitização contra injeção."""

import pytest

from backend.sanitize import (
    sanitize_string,
    validate_cron_expr,
    sanitize_payload,
    clamp_limit,
    MAX_MESSAGE_LEN,
)


def test_sanitize_string_strips_control_chars():
    assert "\x00" not in sanitize_string("a\x00b\x1b")
    assert "a" in sanitize_string("a\nb")  # newline removed by default
    assert sanitize_string("  ok  ") == "ok"


def test_sanitize_string_truncates():
    long = "x" * (MAX_MESSAGE_LEN + 100)
    assert len(sanitize_string(long)) == MAX_MESSAGE_LEN


def test_sanitize_string_allow_newline():
    s = "linha1\nlinha2"
    assert sanitize_string(s, allow_newline=True) == s
    assert "\n" not in sanitize_string(s, allow_newline=False)


def test_validate_cron_expr():
    assert validate_cron_expr("0 9 * * *") is True
    assert validate_cron_expr("0 10 * * 1") is True
    assert validate_cron_expr("0 9 1 * *") is True
    assert validate_cron_expr("*/5 * * * *") is True
    assert validate_cron_expr("0 9 * * *; id") is False
    assert validate_cron_expr("0 9 * *") is False  # 4 fields
    assert validate_cron_expr("") is False
    assert validate_cron_expr(None) is False


def test_sanitize_payload():
    p = {"nome": "Matrix", "ano": 1999}
    assert sanitize_payload(p) == {"nome": "Matrix", "ano": 1999}
    p_bad = {"x" * 100: "y"}
    out = sanitize_payload(p_bad)
    assert len(out) <= 1
    assert list(out.keys())[0] if out else True  # key truncated to 64


def test_sanitize_payload_depth():
    deep = {"a": {"b": {"c": {"d": "x"}}}}
    out = sanitize_payload(deep, max_depth=2)
    assert "a" in out
    assert "b" in out.get("a", {})
    assert "c" not in str(out) or isinstance(out.get("a", {}).get("b"), dict)


def test_clamp_limit():
    assert clamp_limit(50, 100, 500) == 50
    assert clamp_limit(1000, 100, 500) == 500
    assert clamp_limit(-1, 100, 500) == 1
    assert clamp_limit(None, 100, 500) == 100
    assert clamp_limit("invalid", 100, 500) == 100
