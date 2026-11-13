"""Yorumcu Ajanı: kural tabanlı Türkçe maç yorumu + OZBET Tercihi + güven yıldızı.

LLM_API_KEY tanımlıysa (opsiyonel) kısa bir LLM yorumu üretilir; hata olursa kural tabanlı metne düşülür.
Hiçbir metinde 'kesin' / 'banko' ifadesi kullanılmaz.
"""
from __future__ import annotations

import json
import logging

from .. import config
from ..markets import LABELS, all_labels, all_probs
from .consensus import agreement_for
from .value import MAX_EDGE, calibrated, shrink

ALL_LABELS = all_labels()

log = logging.getLogger("ozbet.comment")

# Tercih adayları: gerçek iddaa oranı olan tekil marketler + kombine marketler. Çifte şans (1X/X2/12) ve deneysel
# korner/kart anahtarları bilerek yok.
PICK_SINGLES = ["1", "X", "2", "O2.5", "U2.5", "BTTS_Y", "BTTS_N", "O1.5", "U1.5", "O3.5", "U3.5"]
PICK_COMBOS = [*[f"{r}&{mk}" for r in "1X2" for mk in ("O2.5", "U2.5", "BTTS_Y", "BTTS_N")],
               "BTTS_Y&O2.5", "BTTS_Y&U2.5", "BTTS_N&O2.5", "BTTS_N&U2.5"]
PICK_MARKETS = PICK_SINGLES + PICK_COMBOS
BANNED = ("kesin", "banko", "garanti")
NOTE_NO_MODEL = "Pas: model olasılığı yok"
NOTE_NO_ODDS = "Pas: iddaa oranı yok, beklenen değer hesaplanamadı"
NOTE_NO_EV = "Pas: oran bandında beklenen değeri yeterli seçim yok"

try:   # lig güven katmanı (A = güvenilir veri, C = zayıf); modül yoksa "B"
    from ..league_profile import league_tier as _league_tier
except Exception:  # noqa: BLE001
    _league_tier = None


def league_tier(league_id: str | None) -> str:
    if _league_tier is None or not league_id:
        return "B"
    try:
        t = _league_tier(league_id)
        return t if t in ("A", "B", "C") else "B"
    except Exception:  # noqa: BLE001
        return "B"


def has_banned(text: str) -> bool:
    """Türkçe büyük harf (KESİN) ve aksan farklarına dayanıklı yasaklı kelime kontrolü."""
    from ..teams import _ascii
    t = _ascii(text)
    return any(b in t for b in BANNED)


def pct(p):
    return f"%{round(p * 100)}"


def pick_candidates(m: dict, trust: dict[str, float] | None = None) -> list[dict]:
    """Oran bandındaki adaylar: kalibre olasılık (piyasa ile harman), gerçek oran ve EV = p·oran − 1."""
    model = m.get("model")
    if not model or model.get("source") == "piyasa":   # piyasa-tabanlı modelden "tercih" üretilmez
        return []
    probs = all_probs(model)
    odds = m.get("odds") or {}
    imp = ((m.get("market") or {}).get("implied")) or {}
    out = []
    for k in (PICK_MARKETS if config.PICK_INCLUDE_COMBOS else PICK_SINGLES):
        o, mp, ip = odds.get(k), probs.get(k), imp.get(k)
        # İma olasılığı (grubun tüm oranları) yoksa harman yapılamaz; ham model olasılığıyla EV hesaplanmaz
        if not (o and mp and ip) or not (config.PICK_MIN_ODDS <= o <= config.PICK_MAX_ODDS):
            continue
        if mp - ip > MAX_EDGE:   # ham fark aşırı → veri/eşleme hatası olabilir; EV seçicisi bunu ödüllendirmemeli
            continue
        p = shrink(calibrated(k, mp, ip, m.get("league")), ip, (trust or {}).get(k, 1.0))
        if p < config.PICK_MIN_PROB:
            continue
        out.append({"market": k, "p": p, "odds": o, "ev": p * o - 1, "implied_p": ip})
    return out


def choose_pick(m: dict, trust: dict[str, float] | None = None) -> dict | None:
    """Beklenen değer seçicisi: oran bandında (PICK_MIN_ODDS–PICK_MAX_ODDS) EV'si en yüksek market.
    EV farkı PICK_EV_TIE'dan küçük adaylarda olasılığı yüksek olan seçilir. En iyi EV < PICK_MIN_EV ise tercih
    yoktur (None) ve m["pick_note"] nedenini söyler — "pas" geçerli ve dürüst bir çıktıdır."""
    m.pop("pick_note", None)
    model = m.get("model")
    if not model or model.get("source") == "piyasa":
        m["pick_note"] = NOTE_NO_MODEL
        return None
    if not m.get("odds"):
        m["pick_note"] = NOTE_NO_ODDS
        return None
    cands = pick_candidates(m, trust)
    best_ev = max((c["ev"] for c in cands), default=None)
    if best_ev is None or best_ev < config.PICK_MIN_EV:
        m["pick_note"] = NOTE_NO_EV
        return None
    c = max((c for c in cands if c["ev"] >= best_ev - config.PICK_EV_TIE), key=lambda c: (c["p"], c["ev"]))
    if c["ev"] < config.PICK_MIN_EV:   # eşitlik bozucu eşiğin altına indiremez
        c = max(cands, key=lambda c: c["ev"])
    k, p, ev = c["market"], round(c["p"], 4), round(c["ev"], 4)
    return {"market": k, "label": ALL_LABELS[k], "p": p, "odds": c["odds"], "ev": ev,
            "fair_odds": round(1 / c["p"], 2), "is_value": any(v["market"] == k for v in (m.get("value") or [])),
            "kind": "deger" if ev > 0 else "denge", "blended": True}


def stars(m: dict, pick: dict, trust: dict[str, float]) -> int:
    """Güven yıldızı: ham olasılığa değil, beklenen değere ve piyasaya karşı olasılık payına dayanır;
    düşük oranlı favori sırf olasılığı yüksek diye yıldız toplamaz."""
    score = 0.0
    ev = pick.get("ev")
    if ev is None:   # eski şema (ev alanı yok): orandan hesapla
        ev = pick["p"] * pick["odds"] - 1 if pick.get("odds") else -1.0
    score += 2 if ev >= 0.03 else 1.5 if ev >= 0 else 1 if ev >= -0.03 else 0.5 if ev >= -0.06 else 0
    ip = ((m.get("market") or {}).get("implied") or {}).get(pick["market"])
    if ip is not None:   # kalibre olasılığın marjsız piyasa olasılığına göre payı
        edge = pick["p"] - ip
        score += 1 if edge >= 0.03 else 0.5 if edge >= 0.01 else (-0.5 if edge < 0 else 0)
    if pick.get("is_value"):
        score += 0.5
    ag, tot = agreement_for(m.get("consensus"), pick["market"])
    if tot >= 3:
        r = ag / tot
        score += 1 if r >= 0.75 else 0.5 if r >= 0.6 else (-0.5 if r < 0.4 else 0)
    q = (m.get("model") or {}).get("data_quality")
    score += {"high": 1, "medium": 0.5, "low": -1}.get(q, -1)
    if trust.get(pick["market"], 1.0) < 0.9:
        score -= 1
    s = int(max(1, min(5, int(1 + score + 0.5))))   # yarım puan yukarı yuvarlanır (banker yuvarlaması değil)
    if ev < 0:   # beklenen değeri negatif ("denge") seçim en çok 3 yıldız alır
        s = min(s, 3)
    flags = m.get("flags", [])
    if q == "low" or "Lig dışı/düşük kapsam" in flags or league_tier(m.get("league")) == "C" or any(
            f.startswith(("Model-piyasa farkı", "Kupa/çapraz lig", "Kupa:")) for f in flags):
        s = min(s, 2)
    return s


def pick_sentence(m: dict) -> str | None:
    """Yorumun son cümlesi: tercih ve beklenen değeri ya da neden pas geçildiği. Kâr vaadi içermez."""
    pk = m.get("pick")
    if not pk:
        note = m.get("pick_note")
        return f"OZBET tercihi yok ({note[5:] if note.startswith('Pas: ') else note})." if note else None
    s = (f"OZBET tercihi {pk['label']} ({pk['odds']:.2f} oran): hesaplanan olasılık {pct(pk['p'])}, "
         f"adil oran {pk['fair_odds']:.2f}, beklenen değer {pk['ev'] * 100:+.0f}%")
    if pk.get("kind") == "deger":
        return s + " – oran adil değerin üzerinde görünüyor, yine de sonuç olasılıksaldır."
    return s + " – oran adil değerin altında; bantta marj kaybı en düşük seçenek, kâr beklentisi değil."


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


NEWS_TAG_WORD = {"td": "teknik direktör", "sakat": "sakatlık", "ceza": "ceza"}


def news_sentence(m: dict) -> str | None:
    """RSS haberlerinden en fazla 1 cümle: takım başına en sık geçen önemli etiket (td > sakat > ceza)."""
    news = m.get("news") or {}
    parts = []
    for side in ("home", "away"):
        items = news.get(side) or []
        best = None
        for t in ("td", "sakat", "ceza"):
            c = sum(1 for it in items if t in (it.get("tags") or []))
            if c and (best is None or c > best[1]):
                best = (t, c)
        if best:
            parts.append(f"{m[side]['name']} ile ilgili {best[1]} {NEWS_TAG_WORD[best[0]]}")
    if not parts:
        return None
    return f"Son 3 günde {' ve '.join(parts)} haberi var."


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
    ns = news_sentence(m)
    if ns:
        out.append(ns)
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
        out.append(f"{ALL_LABELS[v['market']]} için model olasılığı ({pct(v['model_p'])}) orandan ima edilen "
                   f"olasılığın ({pct(v['implied_p'])}) üzerinde.")
    # 4-6 cümle; sonuncusu tercih (ya da pas) cümlesi
    tail = pick_sentence(m)
    return " ".join(out[:5] + [tail]) if tail else " ".join(out[:6])


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
    pick = choose_pick(m, trust)   # tercih yoksa m["pick_note"] nedeni taşır
    if pick:
        pick["stars"] = stars(m, pick, trust)
    m["pick"] = pick
    if not m.get("value"):
        if any(f.startswith(("Kupa/çapraz lig", "Kupa:")) for f in m.get("flags", [])):
            m["value_note"] = "Kupa maçı – değer etiketi verilmez"
        else:
            m["value_note"] = "Değer yok" if m.get("odds") and m.get("model") else "Oran/model yok – değer hesaplanamadı"
    text = llm_comment(m) if use_llm else None
    m["comment"] = text or rule_comment(m)
    m["comment_source"] = "llm" if text else "kural"
