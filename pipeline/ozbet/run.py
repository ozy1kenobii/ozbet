"""Günlük OZBET çalıştırması.

    python -m ozbet.run                 # bugün (Türkiye saati)
    python -m ozbet.run --date 2026-11-05
    python -m ozbet.run --offline       # ağ yok; sadece önbellek/var olan veri (test)

Her kaynak StatusBoard ile sarılır: biri çökerse işaretlenir, akış devam eder.
"""
from __future__ import annotations

import argparse
import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path

from . import config
from .agents import bulletin, commentator, consensus, market, scorecard, simulation, squad, stats, value
from .http import PoliteClient
from .sources import football_data as fd
from .sources import registry
from .sources.base import Fixture, StatusBoard, now_iso
from .teams import TeamMatcher, team_key

log = logging.getLogger("ozbet.run")
MAX_OTHER = 150   # öncelikli liglerin dışındaki maçlar için üst sınır
STALE = "Önceki çalıştırmadan (kaynak güncellenemedi)"
STARTED = "Maç başladı/bitti – son bülten verisi"


# ---------------- yardımcılar ----------------
def _read(p: Path, default=None):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _write(p: Path, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    tmp.replace(p)


DEBUG_HOSTS = {"flashscore": "flashscore", "flashscore_results": "flashscore", "forebet": "forebet",
               "sportytrader": "sportytrader", "freesupertips": "freesupertips", "soccerstats": "soccerstats",
               "understat": "understat", "transfermarkt": "transfermarkt", "nesine": "nesine", "iddaa": "iddaa",
               "football_data_fixtures": "football-data"}


def dump_debug(client, board):
    """Boş/hatalı dönen kaynakların ham yanıtlarını .cache/debug altına yazar (Actions artifact'ı olarak yüklenir,
    depoya/siteye girmez). Seçici güncellemek için kullanılır."""
    d = config.CACHE_DIR / "debug"
    d.mkdir(parents=True, exist_ok=True)
    for sid, st in board.items.items():
        host = DEBUG_HOSTS.get(sid)
        if not host or st.status == "ok":
            continue
        hits = [r for r in client.recent if host in r[0]]
        for i, (url, code, body) in enumerate(hits[-4:]):
            (d / f"{sid}-{i}.txt").write_text(_skeleton(url, code, body), encoding="utf-8")


def _skeleton(url: str, code: int, body: str) -> str:
    """Sayfa içeriğini değil yapısını özetler: HTTP kodu, boyut, CSS sınıf/id sıklıkları, JSON anahtarları, kısa baş."""
    import re as _re
    from collections import Counter
    lines = [f"URL: {url}", f"HTTP: {code}", f"Uzunluk: {len(body)}"]
    s = body.lstrip()
    if s[:1] in "{[":
        try:
            obj = json.loads(body)
            def keys(o, depth=0):
                if depth > 3:
                    return []
                if isinstance(o, dict):
                    return [f"{'  '*depth}{k}: {type(v).__name__}" + ("" if not isinstance(v, (dict, list)) else "")
                            for k, v in list(o.items())[:25]] + sum((keys(v, depth + 1) for v in list(o.values())[:3]), [])
                if isinstance(o, list) and o:
                    return [f"{'  '*depth}[{len(o)} öğe]"] + keys(o[0], depth + 1)
                return []
            lines += ["JSON yapısı:"] + keys(obj)[:120]
        except ValueError:
            pass
    classes = Counter(c for grp in _re.findall(r'class="([^"]{1,200})"', body) for c in grp.split())
    ids = Counter(_re.findall(r'id="([^"]{1,60})"', body))
    if classes:
        lines.append("En sık CSS sınıfları: " + ", ".join(f"{c}({n})" for c, n in classes.most_common(80)))
    if ids:
        lines.append("id'ler: " + ", ".join(list(ids)[:60]))
    feed_keys = Counter(_re.findall(r"(?:^|¬|~)([A-Z]{2,3})÷", body))
    if feed_keys:
        lines.append("Feed anahtarları: " + ", ".join(f"{k}({n})" for k, n in feed_keys.most_common(60)))
    for kw in ("Prediction", "prediction", "<h1", "Tip", "forepr", "ld+json", "Bet of the day"):
        allpos = [m.start() for m in _re.finditer(_re.escape(kw), body)]
        pos = allpos[:2] + [p for p in allpos if p > 12000][:4]
        for p in pos:
            lines.append(f"--- '{kw}' @{p}: " + body[max(0, p - 150):p + 350].replace("\n", " "))
    lines += ["", "Baş (2500 karakter):", body[:2500]]
    return "\n".join(lines)


def run_label(now: datetime) -> str:
    h = now.hour + now.minute / 60
    return "08:30" if h < 11 else ("13:30" if h < 16 else "18:30")


# ---------------- ana akış ----------------
def collect_history(client, board, today, leagues_needed) -> dict[str, list[dict]]:
    seasons = config.season_codes(today)
    hist: dict[str, list[dict]] = {}
    ok, fail = 0, []
    for lid in leagues_needed:
        lg = config.LEAGUE_BY_ID[lid]
        if not lg.fd_code:
            continue
        try:
            rows = fd.history(client, lg.fd_code, seasons)
            if rows:
                hist[lid] = rows; ok += 1
            else:
                fail.append(lid)
        except Exception as e:  # noqa: BLE001
            fail.append(f"{lid}({type(e).__name__})")
    from .sources.base import SourceStatus
    board.items["football_data_history"] = SourceStatus(
        "football_data_history", "football-data.co.uk (geçmiş sonuçlar + oranlar)",
        "ok" if ok and not fail else ("partial" if ok else "missing"), now_iso(),
        (f"Eksik ligler: {', '.join(fail)}" if fail else None), sum(len(v) for v in hist.values()))
    return hist


def attach_xg(hist: dict[str, list[dict]], xg_rows: dict[str, list[dict]] | None):
    """understat/fbref maç xG'lerini geçmiş satırlara iliştirir (tarih ±1 gün + takım eşleme)."""
    if not xg_rows:
        return
    for lid, rows in xg_rows.items():
        base = hist.get(lid)
        if not base:
            continue
        tm = TeamMatcher(sorted({r["home"] for r in base} | {r["away"] for r in base}))
        idx = {}
        for r in base:
            idx[(r["date"], r["home"], r["away"])] = r
        for x in rows:
            h, a = tm.match(x["home"]), tm.match(x["away"])
            if not h or not a:
                continue
            for dd in (0, -1, 1):
                r = idx.get((x["date"] + timedelta(days=dd), h, a))
                if r is not None:
                    r["hxg"], r["axg"] = x["hxg"], x["axg"]
                    break


def find_prediction(preds, f: Fixture):
    out = []
    for p in preds or []:
        pf = Fixture(None, "", f.kickoff, p.home, p.away, p.source, p.fetched_at)
        if p.date == f.kickoff.date().isoformat() and bulletin.same_match(f, pf):
            out.append({"source": p.source, "picks": p.picks, "probs": p.probs, "fetched_at": p.fetched_at,
                        **({"note": p.note} if p.note else {})})
    # aynı kaynaktan birden fazla eşleşme varsa ilkini al
    seen, uniq = set(), []
    for o in out:
        if o["source"] not in seen:
            seen.add(o["source"]); uniq.append(o)
    return uniq


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--date")
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--no-llm", action="store_true")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    now = datetime.now(config.TZ)
    today = date.fromisoformat(args.date) if args.date else now.date()
    data = config.DATA_DIR
    client = PoliteClient(delay=0 if args.offline else None)
    if args.offline:
        client.get = _offline_get(client.get)  # type: ignore[assignment]
    board = StatusBoard()

    # 1) Bülten
    fixture_lists = {}
    for src in registry.FIXTURE_SOURCES:
        fixture_lists[src.id] = board.run(src.id, src.name, lambda s=src: s.fixtures(client, today)) or []
    fixture_lists["football_data_fixtures"] = board.run(
        "football_data_fixtures", "football-data.co.uk fixtures.csv (oran yedeği)",
        lambda: fd.fixtures(client, today)) or []
    order = [s.id for s in registry.FIXTURE_SOURCES] + ["football_data_fixtures"]
    nonempty = [fixture_lists[k] for k in order if fixture_lists.get(k)]
    try:
        all_fx = bulletin.merge(nonempty[0], *nonempty[1:]) if nonempty else []
    except Exception as e:  # noqa: BLE001
        log.warning("Bülten birleştirme hatası, yalnız birincil kaynak kullanılıyor: %s", e)
        all_fx = list(nonempty[0]) if nonempty else []
    for f in all_fx:
        f.league_id = f.league_id or bulletin.league_for(f.league_name_raw)
    today_fx = [f for f in all_fx if f.kickoff.date() == today]

    # 2) Geçmiş veri + xG
    needed = [lg.id for lg in config.LEAGUES if lg.fd_code]
    hist = collect_history(client, board, today, needed)
    xg_rows = {}
    for src in registry.XG_SOURCES:
        got = board.run(src.id, src.name, lambda s=src: s.league_xg(client, today),
                        count=lambda d: sum(len(v) for v in d.values()))
        for lid, rows in (got or {}).items():
            xg_rows.setdefault(lid, rows)
    try:
        attach_xg(hist, xg_rows)
    except Exception as e:  # noqa: BLE001
        log.warning("xG iliştirme hatası: %s", e)
    for lid, rows in registry.extra_history(client, board, today).items():
        hist.setdefault(lid, rows)

    # 3) Modeller
    models = {}
    for lid, rows in hist.items():
        try:
            m = simulation.build(lid, rows, today)
            if m:
                models[lid] = m
        except Exception as e:  # noqa: BLE001
            log.warning("Model %s kurulamadı: %s", lid, e)

    # 4) Kadro/haber ve dış tahminler
    news = {}
    for src in registry.NEWS_SOURCES:
        got = board.run(src.id, src.name, lambda s=src: s.team_news(client, today, today_fx)) or {}
        for k, v in got.items():
            news.setdefault(k, v)
    preds = []
    for src in registry.PREDICTION_SOURCES:
        preds += board.run(src.id, src.name, lambda s=src: s.predictions(client, today, today_fx)) or []

    # 5) Karne (geçmiş günler) → trust
    hist_results = registry.results_from_history(hist)
    for src in registry.RESULT_SOURCES:
        got = board.run(src.id, src.name, lambda s=src: s.results(client, today - timedelta(days=1))) or {}
        hist_results.update(got)
    try:
        _grade_past(data, today, hist_results)
    except Exception as e:  # noqa: BLE001
        log.warning("Karne puanlama hatası: %s", e)
    rows = scorecard.load_history(data)
    card = scorecard.build_scorecard(rows, today)
    card["generated_at"] = now_iso()
    trust = card["trust"]

    # 6) Oran geçmişi (sabah → akşam)
    snap_path = data / "odds" / f"{today.isoformat()}.json"
    snaps = _read(snap_path, {}) or {}

    # 7) Maçları kur
    prev_doc = _read(data / f"{today.isoformat()}.json", {}) or {}
    prev = {m["id"]: m for m in prev_doc.get("matches", [])}
    matches, bad_matches = [], []
    prio = [f for f in today_fx if f.league_id]
    other = sorted((f for f in today_fx if not f.league_id), key=lambda f: f.kickoff)[:MAX_OTHER]
    for f in prio + other:
        try:
            mid = bulletin.match_id(f)
            lg = config.LEAGUE_BY_ID.get(f.league_id or "")
            rows_l = hist.get(f.league_id or "", [])
            m = {
                "id": mid, "code": f.code, "mbs": f.mbs,
                "league": f.league_id or "OTHER", "league_name": lg.name if lg else f.league_name_raw,
                "league_priority": lg.priority if lg else 99,
                "kickoff": f.kickoff.isoformat(), "home": {"name": f.home}, "away": {"name": f.away},
                "status": f.status, "result": f.result, "flags": [], "provenance": {},
            }
            m["provenance"]["fixture"] = {"source": f.source, "t": f.fetched_at}
            # oranlar + oran geçmişi
            if f.odds:
                m["odds"] = {k: round(v, 2) for k, v in f.odds.items()}
                srcs = sorted({f.source, *f.extra.get("odds_sources", {}).values()})
                m["provenance"]["odds"] = {"source": ", ".join(srcs), "t": f.fetched_at}
                h = snaps.setdefault(mid, [])
                snap = {"t": now_iso(), **{k: m["odds"][k] for k in ("1", "X", "2", "O2.5", "U2.5") if k in m["odds"]}}
                if not h or any(h[-1].get(k) != v for k, v in snap.items() if k != "t"):
                    h.append(snap)
                m["odds_history"] = h
            else:
                m["odds"] = None; m["odds_history"] = snaps.get(mid, [])
                m["flags"].append("Oran yok")
            mk = market.implied(m["odds"])
            if mk:
                mv, alarms = market.movement(m["odds_history"])
                mk["movement"], mk["drop_alarms"] = mv, alarms
            m["market"] = mk
            # istatistik
            M = models.get(f.league_id or "")
            if M and rows_l:
                th, ta = M.team(f.home), M.team(f.away)
                if th and ta:
                    m["stats"] = {"home": stats.team_stats(rows_l, th, today, "home"),
                                  "away": stats.team_stats(rows_l, ta, today, "away"),
                                  "h2h": stats.h2h(rows_l, th, ta, today)}
                    m["provenance"]["stats"] = {"source": "football-data.co.uk" + (" + xG" if M.xg else ""),
                                                "t": board.items["football_data_history"].fetched_at}
            m.setdefault("stats", None)
            # kadro
            m["squad"] = squad.build(f.home, f.away, f.kickoff, f.league_id, news, all_fx)
            if m["squad"]:
                m["provenance"]["squad"] = {"source": m["squad"]["source"] or "takvim", "t": m["squad"]["fetched_at"]}
            # model
            try:
                m["model"] = simulation.predict(f.home, f.away, f.league_id, models, m["squad"], mid)
            except Exception as e:  # noqa: BLE001
                log.warning("Simülasyon %s: %s", mid, e); m["model"] = None
            if m["model"]:
                m["provenance"]["model"] = {"source": "OZBET Dixon-Coles + 10.000 MC", "t": now_iso()}
                if m["model"]["data_quality"] == "low":
                    m["flags"].append("Düşük veri")
            else:
                m["flags"].append("Veri yetersiz")
            if not lg:
                m["flags"].append("Lig dışı/düşük kapsam")
            # konsensüs + değer + yorum
            ext = find_prediction(preds, f)
            m["consensus"] = consensus.build(ext, (m["model"] or {}).get("probs"), (mk or {}).get("implied"))
            if ext:
                m["provenance"]["predictions"] = {"source": ", ".join(e["source"] for e in ext),
                                                  "t": ext[0]["fetched_at"]}
            if m["model"] and mk and "1" in mk["implied"] and max(
                    abs(m["model"]["probs"][k] - mk["implied"][k]) for k in ("1", "X", "2")) > value.MAX_EDGE:
                m["flags"].append("Model-piyasa farkı çok büyük (veri hatası olabilir)")
            cup = bool(lg and lg.cup) or not lg
            if cup and m["model"]:
                m["flags"].append("Kupa/çapraz lig: model düşük güvenli, değer etiketi verilmez")
            m["value"] = [] if cup else value.find_value((m["model"] or {}).get("probs"), m["odds"], (mk or {}).get("implied"), trust)
            commentator.annotate(m, trust, use_llm=not args.no_llm and lg is not None)
            if f.result:
                m["status"] = "finished"
            matches.append(m)
        except Exception as e:  # noqa: BLE001 — tek maçtaki beklenmeyen veri tüm çalıştırmayı düşürmesin
            log.warning("Maç %s - %s işlenemedi: %s", f.home, f.away, e)
            bad_matches.append(f"{f.home} - {f.away}: {type(e).__name__}")

    # Önceki çalıştırmada olup bu sefer kaynaktan düşen maçları koru (kaynak geçici çöktüyse)
    ids = {m["id"] for m in matches}
    for mid, pm in prev.items():
        if mid not in ids:
            fl = pm.setdefault("flags", [])
            started = datetime.fromisoformat(pm["kickoff"]) <= now
            tag = STARTED if started else STALE
            for old in (STALE, STARTED):
                if old in fl and old != tag:
                    fl.remove(old)
            if tag not in fl:
                fl.append(tag)
            matches.append(pm)
    matches.sort(key=lambda m: (m["league_priority"], m["kickoff"], m["home"]["name"]))

    unknown = sorted({f.league_name_raw for f in today_fx if not f.league_id and f.league_name_raw})
    from .sources.base import SourceStatus
    board.items["pipeline"] = SourceStatus(
        "pipeline", "OZBET işleme", "partial" if bad_matches else "ok", now_iso(),
        "; ".join(([f"İşlenemeyen maçlar: {', '.join(bad_matches[:5])}"] if bad_matches else []) +
                  ([f"Eşlenemeyen lig adları (ilk 15): {', '.join(unknown[:15])}"] if unknown else [])) or None,
        len(matches))
    leagues_present = sorted({m["league"] for m in matches},
                             key=lambda l: config.LEAGUE_BY_ID[l].priority if l in config.LEAGUE_BY_ID else 99)
    doc = {
        "schema_version": 1, "date": today.isoformat(), "generated_at": now_iso(), "run_label": run_label(now),
        "sources": board.as_list(),
        "leagues": [{"id": l, "name": config.LEAGUE_BY_ID[l].name, "country": config.LEAGUE_BY_ID[l].country,
                     "priority": config.LEAGUE_BY_ID[l].priority} if l in config.LEAGUE_BY_ID else
                    {"id": "OTHER", "name": "Diğer ligler", "country": "", "priority": 99} for l in leagues_present],
        "matches": matches,
    }
    try:
        dump_debug(client, board)
    except Exception as e:  # noqa: BLE001
        log.info("debug dökümü yazılamadı: %s", e)
    _write(snap_path, snaps)
    _write(data / f"{today.isoformat()}.json", doc)
    idx = _read(data / "index.json", {"dates": []}) or {"dates": []}
    latest_date = max([today.isoformat(), *idx.get("dates", [])])
    if latest_date == today.isoformat():
        _write(data / "latest.json", doc)
    dates = sorted({*idx.get("dates", []), today.isoformat()}, reverse=True)
    _write(data / "index.json", {"dates": dates, "latest": dates[0]})
    _write(data / "scorecard.json", card)
    _write(data / "status.json", {"generated_at": now_iso(), "run_label": doc["run_label"], "sources": board.as_list()})
    n_model = sum(1 for m in matches if m.get("model"))
    log.info("Bitti: %d maç (%d modelli), %d kaynak ok", len(matches), n_model,
             sum(1 for s in board.as_list() if s["status"] == "ok"))
    return doc


def _grade_past(data: Path, today: date, results_by_key: dict):
    """Son 10 günün dosyalarını puanlar ve history/ altına yazar."""
    for k in range(1, 11):
        d = today - timedelta(days=k)
        p = data / f"{d.isoformat()}.json"
        doc = _read(p)
        if not doc:
            continue
        res = {}
        for m in doc.get("matches", []):
            if m.get("result"):
                continue
            r = registry.lookup_result(results_by_key, m["kickoff"], m["home"]["name"], m["away"]["name"])
            if r:
                res[m["id"]] = r
        graded = scorecard.grade_day(doc, res)
        _write(p, doc)
        if graded:
            _write(data / "history" / f"{d.isoformat()}.json", {"date": d.isoformat(), "rows": graded})


def _offline_get(orig):
    def get(url, **kw):
        kw["ttl"] = 10 ** 9
        kw["check_robots"] = False
        return orig(url, **kw)
    return get


if __name__ == "__main__":
    main()
