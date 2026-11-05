"""Tahmin Konsensüs Ajanı: dış tahmin siteleri + model + piyasa uzlaşması."""
from __future__ import annotations

from collections import Counter

from ..markets import LABELS

GROUP_OF = {"1": "1X2", "X": "1X2", "2": "1X2", "O2.5": "OU25", "U2.5": "OU25",
            "BTTS_Y": "BTTS", "BTTS_N": "BTTS"}

# Türkçe iyelik eki: "5 kaynaktan 4'ü"
_POSS = {1: "'i", 2: "'si", 3: "'ü", 4: "'ü", 5: "'i", 6: "'sı", 7: "'si", 8: "'i", 9: "'u", 10: "'u"}


def phrase(agree: int, total: int, market: str) -> str:
    lab = LABELS.get(market, market)
    if agree == total:
        return f"{total} kaynağın tümü {lab} diyor"
    return f"{total} kaynaktan {agree}{_POSS.get(agree, '')} {lab} diyor"


def picks_from_probs(p: dict | None) -> dict[str, str]:
    if not p:
        return {}
    out = {}
    if all(k in p for k in ("1", "X", "2")):
        out["1X2"] = max(("1", "X", "2"), key=lambda k: p[k])
    if "O2.5" in p and "U2.5" in p:
        out["OU25"] = "O2.5" if p["O2.5"] >= p["U2.5"] else "U2.5"
    if "BTTS_Y" in p and "BTTS_N" in p:
        out["BTTS"] = "BTTS_Y" if p["BTTS_Y"] >= p["BTTS_N"] else "BTTS_N"
    return out


def build(external: list[dict], model_probs: dict | None, implied: dict | None) -> dict:
    sources = list(external)
    if model_probs:
        sources.append({"source": "OZBET Model", "picks": picks_from_probs(model_probs),
                        "probs": {k: model_probs[k] for k in ("1", "X", "2") if k in model_probs}})
    if implied:
        sources.append({"source": "Piyasa (oran)", "picks": picks_from_probs(implied),
                        "probs": {k: implied[k] for k in ("1", "X", "2") if k in implied}})
    summary = []
    for g in ("1X2", "OU25", "BTTS"):
        votes = [s["picks"][g] for s in sources if s.get("picks", {}).get(g)]
        if len(votes) < 2:
            continue
        mk, c = Counter(votes).most_common(1)[0]
        summary.append({"market": mk, "group": g, "agree": c, "total": len(votes),
                        "text": phrase(c, len(votes), mk)})
    summary.sort(key=lambda s: (-s["agree"] / s["total"], -s["total"]))
    return {"sources": sources, "summary": summary}


def agreement_for(cons: dict | None, market: str) -> tuple[int, int]:
    if not cons:
        return 0, 0
    g = GROUP_OF.get(market)
    votes = [s["picks"].get(g) for s in cons.get("sources", []) if g and s.get("picks", {}).get(g)]
    return sum(1 for v in votes if v == market), len(votes)
