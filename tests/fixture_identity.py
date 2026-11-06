"""Load the local userscript without injecting any platform identity.

The compatibility name keeps existing fixtures importable. No test may rely on
a successful fake profile or UUID to get past the mastery task scheduler.
"""
from pathlib import Path

IDENTITY = ''


def userscript(root):
    return IDENTITY + (Path(root) / 'zhihuishu-mastery.user.js').read_text(encoding='utf-8')
