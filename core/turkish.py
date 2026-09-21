from __future__ import annotations

import re


_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.I | re.S)
_THINK_OPEN = re.compile(r"</?think>", re.I)
_MULTI_SPACE = re.compile(r"[ \t]{2,}")
_MULTI_NL = re.compile(r"\n{3,}")
_EN_PREFIX = re.compile(
    r"^(sure!?|of course!?|here(?:'s| is)|i am |i'm |let me |okay[,!]?\s)+",
    re.I,
)


def strip_think(text: str) -> str:
    if not text:
        return ""
    cleaned = _THINK_BLOCK.sub("", text)
    cleaned = _THINK_OPEN.sub("", cleaned)
    return cleaned.strip()


def polish_turkish(text: str) -> str:
    """Model çıktısını gösterilebilir Türkçe metne çevir (anlamı uydurmaz)."""
    t = strip_think(text or "")
    t = t.replace("\ufeff", "").strip()
    t = _EN_PREFIX.sub("", t).strip()
    t = t.replace(" ,", ",").replace(" .", ".").replace(" ?", "?").replace(" !", "!")
    t = _MULTI_SPACE.sub(" ", t)
    t = _MULTI_NL.sub("\n\n", t)
    lines = [ln.rstrip() for ln in t.splitlines()]
    t = "\n".join(lines).strip()
    return t


class StreamThinkFilter:
    """Streaming sırasında <think> bloklarını kullanıcıya basma."""

    def __init__(self) -> None:
        self.buf = ""
        self.in_think = False

    def feed(self, token: str) -> str:
        if not token:
            return ""
        self.buf += token
        emitted: list[str] = []
        while self.buf:
            lower = self.buf.lower()
            if self.in_think:
                end = lower.find("</think>")
                if end < 0:
                    if len(self.buf) > 24:
                        self.buf = self.buf[-24:]
                    return "".join(emitted)
                self.buf = self.buf[end + len("</think>"):]
                self.in_think = False
                continue
            start = lower.find("<think>")
            if start < 0:
                emitted.append(self.buf)
                self.buf = ""
                break
            if start > 0:
                emitted.append(self.buf[:start])
            self.buf = self.buf[start + len("<think>"):]
            self.in_think = True
        return "".join(emitted)

    def flush(self) -> str:
        if self.in_think:
            self.buf = ""
            self.in_think = False
            return ""
        leftover = self.buf
        self.buf = ""
        return leftover
