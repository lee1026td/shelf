"""Tests for shelf.util helpers."""

from __future__ import annotations

from shelf.util import sha256_hex, slugify


def test_slugify_basic():
    assert slugify("Hello, World!") == "hello-world"


def test_slugify_preserves_unicode():
    assert "로컬" in slugify("로컬 우선 에이전트")


def test_slugify_empty_falls_back():
    assert slugify("!!!") == "item"
    assert slugify("") == "item"


def test_slugify_avoids_windows_reserved_names():
    assert slugify("CON") == "_con"
    assert slugify("nul") == "_nul"
    assert slugify("COM1") == "_com1"
    assert slugify("LPT9") == "_lpt9"


def test_slugify_maxlen():
    assert len(slugify("a" * 200, maxlen=20)) <= 20


def test_sha256_hex_stable():
    assert sha256_hex(b"abc") == sha256_hex(b"abc")
    assert sha256_hex(b"abc") != sha256_hex(b"abd")
