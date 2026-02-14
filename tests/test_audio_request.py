"""Tests for audio request detection."""
from backend.audio_request import detects_audio_request


def test_detects_audio_request_pt():
    assert detects_audio_request("responde em áudio") is True
    assert detects_audio_request("manda áudio por favor") is True
    assert detects_audio_request("responde em audio, lembrete amanha") is True
    assert detects_audio_request("fala comigo") is True
    assert detects_audio_request("quero audio") is True
    assert detects_audio_request("em audio por favor") is True


def test_detects_audio_request_en():
    assert detects_audio_request("respond in audio") is True
    assert detects_audio_request("send me an audio") is True


def test_no_false_positives():
    assert detects_audio_request("lembrete amanha") is False
    assert detects_audio_request("manda video") is False
    assert detects_audio_request("ok") is False
