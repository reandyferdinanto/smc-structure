from __future__ import annotations

from src.alerts.commands import Commands
from src.utils import mute


def test_help_lists_commands(tmp_path):
    commands = Commands(state_dir=tmp_path)
    text = commands._handle("/help", "/help")
    assert text is not None
    assert "/status" in text
    assert "/reentry" in text
    assert "/mute" in text


def test_unknown_command(tmp_path):
    commands = Commands(state_dir=tmp_path)
    assert "tidak dikenal" in commands._handle("/foo", "/foo")


def test_mute_and_unmute(tmp_path):
    commands = Commands(state_dir=tmp_path)
    commands._handle("/mute 5", "/mute 5")
    assert mute.is_muted(tmp_path) is True
    commands._handle("/unmute", "/unmute")
    assert mute.is_muted(tmp_path) is False


def test_last_without_signal(tmp_path):
    commands = Commands(state_dir=tmp_path)
    assert "Belum ada sinyal" in commands._last()
