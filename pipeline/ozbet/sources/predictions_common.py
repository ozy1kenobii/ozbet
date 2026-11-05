"""Tahmin sitelerinin serbest metnini OZBET market anahtarlarına çeviren yardımcılar."""
from __future__ import annotations

import re

from ..teams import normalize


def picks_from_text(text: str, home: str, away: str) -> dict[str, str]:
    """'Galatasaray to win and over 3.5', 'Both teams to score', 'Draw', 'Under 2.5 goals' gibi ifadeler."""
    s = normalize(text)
    h, a = normalize(home), normalize(away)
    picks: dict[str, str] = {}
    if re.search(r"\b(btts|both teams to score)\b", s) and not re.search(r"\b(no|not)\b.*\b(btts|both teams)", s):
        picks["BTTS"] = "BTTS_Y"
    if re.search(r"\b(btts no|both teams not to score|no btts|both teams to score no)\b", s):
        picks["BTTS"] = "BTTS_N"
    m = re.search(r"\b(over|under)\s*(\d)\s*5\b", s)
    if m and m.group(2) == "2":
        picks["OU25"] = "O2.5" if m.group(1) == "over" else "U2.5"
    elif m and m.group(1) == "over" and m.group(2) in ("3", "4"):
        picks["OU25"] = "O2.5"
    elif m and m.group(1) == "under" and m.group(2) in ("0", "1"):
        picks["OU25"] = "U2.5"
    if re.search(r"\bdraw\b", s) and "draw no bet" not in s:
        picks["1X2"] = "X"
    else:
        hw = h and (h in s) and re.search(r"\b(win|to win|victory)\b", s)
        aw = a and (a in s) and re.search(r"\b(win|to win|victory)\b", s)
        if hw and not aw:
            picks["1X2"] = "1"
        elif aw and not hw:
            picks["1X2"] = "2"
        elif hw and aw:
            # hangisi "win" kelimesine daha yakın
            picks["1X2"] = "1" if abs(s.find(h) - s.find("win")) < abs(s.find(a) - s.find("win")) else "2"
    sc = re.search(r"\b(\d)\s*[-:]\s*(\d)\b", text)
    if sc and "1X2" not in picks:
        x, y = int(sc.group(1)), int(sc.group(2))
        picks["1X2"] = "1" if x > y else ("X" if x == y else "2")
    return picks
