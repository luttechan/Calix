"""Bounded desktop diagnostics with authentication values redacted."""

import logging
import re


class SecretSafeFormatter(logging.Formatter):
    def format(self, record):
        message = super().format(record)
        secret = r"(?:password|passwd|[a-z0-9_-]*(?:token|session)[a-z0-9_-]*)"
        quoted = r"""(?:"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')"""
        for pattern, replacement in (
            (
                rf"""(?i)(['"](?:authorization|cookie|set-cookie|{secret})['"]\s*:\s*){quoted}""",
                r'\1"[숨김]"',
            ),
            (
                r"(?im)(\b(?:authorization|cookie|set-cookie)\s*:\s*)[^\r\n]*",
                r"\1[숨김]",
            ),
            (rf"(?i)(\b(?:cookie|{secret})\s*[=:]\s*){quoted}", r'\1"[숨김]"'),
            (rf"(?i)(\b(?:cookie|{secret})\s*[=:]\s*)[^\s;,&]+", r"\1[숨김]"),
        ):
            message = re.sub(pattern, replacement, message)
        return message


def configure(folder):
    # Normal operation neither collects diagnostics nor opens a log file.
    logger = logging.getLogger()
    logger.setLevel(logging.WARNING)
    logger.addHandler(logging.NullHandler())
