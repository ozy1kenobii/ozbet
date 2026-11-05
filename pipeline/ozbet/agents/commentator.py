"""Yorumcu Ajanı: kural tabanlı Türkçe maç yorumu + OZBET Tercihi + güven yıldızı.

LLM_API_KEY tanımlıysa (opsiyonel) kısa bir LLM yorumu üretilir; hata olursa kural tabanlı metne düşülür.
Hiçbir metinde 'kesin' / 'banko' ifadesi kullanılmaz.
"""
from __future__ import annotations

import json
import logging

from .. import config
from ..markets import LABELS
from .consensus import agreement_for

log = logging.getLogger("ozbet.comment")

SINGLE = ["1", "X", "2", "O2.5", "U2.5", "BTTS_Y", "BTTS_N", "O1.5", "U3.5", "O3.5"]
DOUBLE = ["1X", "X2"]
BANNED = ("kesin", "banko", "garanti")


def has_banned(text: str) -> bool:
    """Türkçe büyük harf (KESİN) ve aksan farklarına dayanıklı yasaklı kelime kontrolü."""
    from ..teams import _ascii
    t = _ascii(text)
    return any(b in t for b in BANNED)


def pct(p):
    return f"%{round(p * 100)}"


def choose_pick(m: dict) -> dict | None:
    model = m.get("model")
    if not model:
        return None
    p = model["probs"]
    odds = m.get("odds") or {}
    if m.get("value"):
        v = m["value"][0]
        return {"market": v["market"], "label": LABELS[v["market"]], "p": v["model_p"],
                "odds": v["odds"], "is_value": True}
    # Değer yoksa: anlamlı tekil marketlerde en yüksek olasılık (1.5 Üst/3.5 Alt çok kolay → elenir eşiği yüksek)
    cands = [(k, p[k]) for k in ["1", "2", "O2.5", "U2.5", "BTTS_Y", "BTTS_N"] if k in p]
    k, pk = max(cands, key=lambda t: t[1])
    if pk < 0.55:
        dk, dp = max(((k2, p[k2]) for k2 in DOUBLE), key=lambda t: t[1])
        if dp >= 0.70 and dp - pk > 0.15:
            k, pk = dk, dp
    return {"market": k, "label": LABELS[k], "p": round(pk, 4), "odds": odds.get(k), "is_value": False}


def stars(m: dict, pick: dict, trust: dict[str, float]) -> int:
    score = 0.0
    p = pick["p"]
    score += 2 if p >= 0.70 else 1.5 if p >= 0.58 else 1 if p >= 0.50 else 0
    if pick["is_value"]:
        score += 1
    ag, tot = agreement_for(m.get("consensus"), pick["market"])
    if tot >= 3:
        r = ag / tot
        score += 1 if r >= 0.75 else 0.5 if r >= 0.6 else (-0.5 if r < 0.4 else 0)
    q = (m.get("model") or {}).get("data_quality")
    score += {"high": 1, "medium": 0.5, "low": -1}.get(q, -1)
    if trust.get(pick["market"], 1.0) < 0.9:
        score -= 1
    s = int(max(1, min(5, round(1 + score))))
    flags = m.get("flags", [])
    if q == "low" or "Lig dışı/düşük kapsam" in flags or any(
            f.startswith(("Model-piyasa farkı", "Kupa/çapraz lig")) for f in flags):
        s = min(s, 2)
    return s


def _form_sentence(team: str, st: dict, venue: str) -> str | None:
    vf = st.get("venue_form") or []
    n = len(vf)
    if n < 4:
        return None
    w, d, l = vf.count("W"), vf.count("D"), vf.count("L")
    yer = "iç saha" if venue == "home" else "deplasman"
    cs = st.get("clean_sheets_venue", 0)
    fts = st.get("failed_to_score_venue", 0)
    s = f"{team} son {n} {yer} maçında {w} galibiyet, {d} beraberlik, {l} mağlubiyet aldı"
    if cs >= max(3, n // 2):
        s += f"; bu maçların {cs} tanesinde gol yemedi"
    elif fts >= max(3, n // 2):
        s += f"; {fts} maçta gol atamadı"
    return s + "."


def rule_comment(m: dict) -> str:
    H, A = m["home"]["name"], m["away"]["name"]
    model, stats, squad = m.get("model"), m.get("stats") or {}, m.get("squad") or {}
    out: list[str] = []
    if model:
        p = model["probs"]
        out.append(f"Model ev sahibine {pct(p['1'])}, beraberliğe {pct(p['X'])}, deplasmana {pct(p['2'])} "
                   f"olasılık veriyor; beklenen gol {model['lambda_home']:.1f} - {model['lambda_away']:.1f}.")
    else:
        out.append("Bu maç için yeterli geçmiş veri bulunamadı; model olasılığı üretilmedi.")
    for team, key, ven in ((H, "home", "home"), (A, "away", "away")):
        st = stats.get(key)
        if st:
            s = _form_sentence(team, st, ven)
            if s:
                out.append(s)
    hs, as_ = stats.get("home") or {}, stats.get("away") or {}
    if hs.get("o25_pct") is not None and as_.get("o25_pct") is not None:
        o_avg = (hs["o25_pct"] + as_["o25_pct"]) / 2
        b_avg = ((hs.get("btts_pct") or 0) + (as_.get("btts_pct") or 0)) / 2
        if o_avg >= 0.6 or o_avg <= 0.35:
            out.append(f"İki takımın son maçlarında 2.5 Üst oranı {pct(hs['o25_pct'])} ve {pct(as_['o25_pct'])}"
                       f"{' – gollü bir eğilim var' if o_avg >= 0.6 else ' – düşük skor eğilimi öne çıkıyor'}.")
        elif b_avg >= 0.6:
            out.append(f"KG Var oranları {pct(hs.get('btts_pct') or 0)} ve {pct(as_.get('btts_pct') or 0)} seviyesinde.")
    for team, key in ((H, "home"), (A, "away")):
        sq = squad.get(key) or {}
        keys = [x["name"] for x in sq.get("missing", []) if x.get("key")]
        if keys:
            reasons = {x["name"]: x["reason"] for x in sq["missing"]}
            names = ", ".join(f"{n} ({reasons[n]})" for n in keys[:3])
            out.append(f"{team} tarafında kilit eksik: {names}.")
        elif sq.get("rotation_risk"):
            out.append(f"{team} için Avrupa maçı nedeniyle rotasyon riski var.")
    cons = m.get("consensus") or {}
    ext = [s for s in cons.get("sources", []) if s["source"] not in ("OZBET Model", "Piyasa (oran)")]
    if cons.get("summary") and ext:
        t0 = cons["summary"][0]["text"]
        out.append(t0[:1].upper() + t0[1:] + ".")
    mk = m.get("market") or {}
    if mk.get("drop_alarms"):
        k = mk["drop_alarms"][0]
        out.append(f"{LABELS.get(k, k)} oranı ilk görüldüğünden bu yana {pct(abs(mk['movement'][k]))} düştü.")
    if m.get("value"):
        v = m["value"][0]
        out.append(f"{LABELS[v['market']]} için model olasılığı ({pct(v['model_p'])}) orandan ima edilen "
                   f"olasılığın ({pct(v['implied_p'])}) üzerinde.")
    elif m.get("odds") and model:
        out.append("Oranlarla karşılaştırıldığında belirgin bir değer görünmüyor.")
    # 4-6 cümle
    return " ".join(out[:6])


def llm_comment(m: dict) -> str | None:
    if not config.LLM_API_KEY:
        return None
    try:
        import requests
        brief = {k: m.get(k) for k in ("home", "away", "league_name", "odds", "pick", "value", "flags")}
        brief["model"] = {k: (m.get("model") or {}).get(k) for k in ("probs", "lambda_home", "lambda_away", "top_scores")}
        brief["stats"] = m.get("stats"); brief["squad"] = m.get("squad")
        brief["consensus"] = (m.get("consensus") or {}).get("summary")
        prompt = ("Aşağıdaki futbol maçı verisinden Türkçe, 4-6 cümlelik, tarafsız bir maç yorumu yaz. "
                  "Sadece verideki bilgileri kullan, uydurma. 'kesin', 'banko', 'garanti' kelimelerini kullanma; "
                  "olasılıkları yüzde olarak belirt. Sadece yorum metnini döndür.\n\n"
                  + json.dumps(brief, ensure_ascii=False, default=str)[:6000])
        r = requests.post("https://api.anthropic.com/v1/messages", timeout=30, headers={
            "x-api-key": config.LLM_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": config.LLM_MODEL, "max_tokens": 400, "messages": [{"role": "user", "content": prompt}]})
        r.raise_for_status()
        text = "".join(b.get("text", "") for b in r.json().get("content", [])).strip()
        if not text or has_banned(text):
            return None
        return text
    except Exception as e:  # noqa: BLE001
        log.warning("LLM yorumu başarısız, kural tabanlıya düşülüyor: %s", e)
        return None


def annotate(m: dict, trust: dict[str, float], use_llm: bool = True) -> None:
    pick = choose_pick(m)
    if pick:
        pick["stars"] = stars(m, pick, trust)
    m["pick"] = pick
    if not m.get("value"):
        if any(f.startswith("Kupa/çapraz lig") for f in m.get("flags", [])):
            m["value_note"] = "Kupa maçı – değer etiketi verilmez"
        else:
            m["value_note"] = "Değer yok" if m.get("odds") and m.get("model") else "Oran/model yok – değer hesaplanamadı"
    text = llm_comment(m) if use_llm else None
    m["comment"] = text or rule_comment(m)
    m["comment_source"] = "llm" if text else "kural"
