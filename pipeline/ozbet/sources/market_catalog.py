"""Teşhis: bültenlerde gerçekte hangi marketlerin, hangi çizgilerle ve hangi seçenek adlarıyla geldiğini döker.

Çıktı .cache/debug/market-catalog-*.txt → Actions 'teshis' dalına (siteye girmez). Market eşlemeleri
tahminle değil bu katalogla yapılır; yanlış eşleme yanlış oranı yanlış markete yazar.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict

from .. import config


def nesine(doc: dict) -> str:
    sg = doc.get("sg") or {}
    cnt: Counter = Counter()
    sov: dict[int, Counter] = defaultdict(Counter)
    opts: dict[int, Counter] = defaultdict(Counter)
    sample: dict[int, dict] = {}
    for e in sg.get("EA") or []:
        if e.get("GT") not in (None, 1):
            continue
        for m in e.get("MA") or []:
            mt = m.get("MTID")
            cnt[mt] += 1
            sov[mt][str(m.get("SOV"))] += 1
            opts[mt][len(m.get("OCA") or [])] += 1
            sample.setdefault(mt, {k: v for k, v in m.items() if k != "OCA"} | {"OCA": (m.get("OCA") or [])[:12]})
    lines = [f"Nesine market kataloğu — {sum(cnt.values())} market, {len(cnt)} tür"]
    for mt, n in cnt.most_common():
        lines.append(f"MTID={mt} n={n} SOV={dict(sov[mt].most_common(8))} secenek_sayisi={dict(opts[mt])}")
        lines.append("   örnek: " + json.dumps(sample[mt], ensure_ascii=False)[:600])
    return "\n".join(lines)


def iddaa(events: list[dict], config_doc: dict | None) -> str:
    names = {}
    for key, v in ((config_doc or {}).get("data", {}).get("m") or {}).items():
        try:
            names[int(v.get("st"))] = v.get("n") or v.get("mn") or key
        except (TypeError, ValueError):
            continue
    cnt: Counter = Counter()
    sov: dict[int, Counter] = defaultdict(Counter)
    opts: dict[int, Counter] = defaultdict(Counter)
    for e in events:
        for m in e.get("m") or []:
            st = m.get("st")
            cnt[st] += 1
            sov[st][str(m.get("sov"))] += 1
            opts[st][" | ".join(str(o.get("n")) for o in m.get("o") or [])] += 1
    lines = [f"iddaa market kataloğu — {sum(cnt.values())} market, {len(cnt)} tür"]
    for st, n in cnt.most_common():
        lines.append(f"st={st} ad={names.get(st, '?')!r} n={n} sov={dict(sov[st].most_common(8))}")
        lines.append(f"   seçenekler: {dict(opts[st].most_common(3))}")
    return "\n".join(lines)


def dump(name: str, text: str):
    try:
        d = config.CACHE_DIR / "debug"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"market-catalog-{name}.txt").write_text(text, encoding="utf-8")
    except OSError:
        pass
