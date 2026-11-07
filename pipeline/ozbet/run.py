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

from . import config, health, validate
from .markets import all_labels, all_probs
from .markets import categories as market_categories
from .model import market_lambda
from .model.simulate import seed_for
from .agents import iddaa_archive, market_map, odds_analysis, bulletin, commentator, consensus, market, scorecard, simulation, squad, standings, stats, trends, value
from .http import PoliteClient
from .sources import football_data as fd
from .sources import archive, news_rss, registry, tff
from .sources.base import Fixture, StatusBoard, now_iso
from .teams import TeamMatcher, team_key

log = logging.getLogger("ozbet.run")
MAX_OTHER = 150   # öncelikli liglerin dışındaki maçlar için üst sınır
STALE = "Önceki çalıştırmadan (kaynak güncellenemedi)"
STARTED = "Maç başladı/bitti – son bülten verisi"
CUP_FLAG = "Kupa/çapraz lig: model düşük güvenli, değer etiketi verilmez"
CUP_FLAG_ELO = "Kupa: Elo tabanlı lig-arası düzeltme"


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
               "football_data_fixtures": "football-data", "clubelo": "clubelo", "soccerstats_tr2": "soccerstats",
               "tff_tr2": "tff", "tff_referees": "tff"}


def dump_debug(client, board):
    """Boş/hatalı dönen kaynakların ham yanıtlarını .cache/debug altına yazar (Actions artifact'ı olarak yüklenir,
    depoya/siteye girmez). Seçici güncellemek için kullanılır."""
    d = config.CACHE_DIR / "debug"
    d.mkdir(parents=True, exist_ok=True)
    for sid, st in board.items.items():
        host = DEBUG_HOSTS.get(sid)
        if not host or st.status == "ok":
            continue
        recent = list(client.recent) + list(getattr(getattr(client, "_tff", None), "recent", []))
        hits = [r for r in recent if host in r[0]]
        for i, (url, code, body) in enumerate(hits[-4:]):
            (d / f"{sid}-{i}.txt").write_text(_skeleton(url, code, body), encoding="utf-8")
    # tff: hafta + maç sayfası yapısı her durumda (ilk canlı çalıştırmada seçici doğrulaması için)
    for kind, (url, code, body) in tff.SAMPLES.items():
        (d / f"tff-{kind}.txt").write_text(_skeleton(url, code, body), encoding="utf-8")


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
        if not lg.fd_code and not lg.fd_extra:
            continue
        try:
            rows = (fd.history(client, lg.fd_code, seasons) if lg.fd_code
                    else fd.history_new(client, lg.fd_extra, seasons))
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


def attach_news(m: dict, f: Fixture, rss: dict | None) -> None:
    """Maça RSS haber bloğunu ekler: {"home":[...], "away":[...], "fetched_at"}; haber yoksa anahtar eklenmez."""
    from .sources import news_rss
    try:
        blk = news_rss.for_match(f.home, f.away, rss)
    except Exception as e:  # noqa: BLE001
        log.warning("Haber iliştirilemedi %s - %s: %s", f.home, f.away, e)
        blk = None
    if blk:
        m["news"] = blk
        m["provenance"]["news"] = {"source": "RSS/Atom haber akışları", "t": blk["fetched_at"]}


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
    vrep = validate.Report()
    for sid, name, note in registry.DISABLED:
        board.skip(sid, name, note)

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
    all_fx = validate.clean_fixtures(all_fx, today, vrep)
    for f in all_fx:
        f.league_id = f.league_id or bulletin.league_for(f.league_name_raw)
    # kaynaklar arası eşleşme: iki ana bülten kaynağının ortak maçlarının ne kadarı birleştirilebildi
    cross = _cross_source(fixture_lists, all_fx, today)
    today_fx = [f for f in all_fx if f.kickoff.date() == today]

    # 2) Geçmiş veri + xG
    # "new" lig dosyaları yalnız bugün bültende maçı olan ligler için indirilir
    present = {f.league_id for f in today_fx}
    needed = [lg.id for lg in config.LEAGUES if lg.fd_code or (lg.fd_extra and lg.id in present)]
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
    # Dünün (ve kaçırılan son 7 günün) sonuçlarını birikimli arşive ekle — extra_history bunu okur
    for src in registry.RESULT_SOURCES:
        if src.archive_feed:
            board.run(f"{src.id}_archive", f"Birikimli sonuç arşivi ({src.name} → data/archive)",
                      lambda s=src: archive.update(data, today, lambda d: s.archive_feed(client, d)),
                      empty_is_partial=False, count=lambda d: sum(d.values()))
    for lid, rows in registry.extra_history(client, board, today).items():
        hist.setdefault(lid, rows)
    # Süper Lig hakemleri (tff.org) → TR1 geçmiş satırları + bugünkü fikstürler (kart modeli hakem etkisi)
    registry.tff_referees(client, board, today, hist, today_fx)
    # ClubElo: günde 1 istek; yoksa simülasyon lig gücü katsayısına düşer
    elo_table = None
    for src in registry.ELO_SOURCES:
        elo_table = board.run(src.id, src.name, lambda s=src: s.elo(client, today))
        if elo_table:
            break

    hist = {lid: validate.clean_history(rows, vrep) for lid, rows in hist.items()}
    try:
        odds_pool = odds_analysis.Pool(hist)
    except Exception as e:  # noqa: BLE001
        log.warning("Oran arşivi kurulamadı: %s", e)
        odds_pool = None
    # 3) Modeller
    models = {}
    for lid, rows in hist.items():
        try:
            m = simulation.build(lid, rows, today)
            if m:
                models[lid] = m
        except Exception as e:  # noqa: BLE001
            log.warning("Model %s kurulamadı: %s", lid, e)

    # 3b) Belirsiz iddaa marketlerinin veriyle çözülmesi (İY/2Y, ev/dep gol, handikap yönü, MS&KG)
    map_report = {}
    try:
        samples = []
        for f in today_fx:
            raw = f.extra.get("iddaa_raw")
            if not raw or f.league_id not in models or len(samples) >= 60:
                continue
            sm = simulation.predict(f.home, f.away, f.league_id, models, None, "map-" + bulletin.match_id(f))
            if sm:
                samples.append((raw, sm))
        decisions, map_report = market_map.resolve(samples)
        added = 0
        for f in all_fx:
            if f.extra.get("iddaa_raw"):
                added += market_map.apply(f.extra["iddaa_raw"], f.odds, decisions)
                f.odds = validate.clean_odds(f.odds, vrep)
        map_report["added_odds"] = added
        log.info("Market eşleme kararları: %s", decisions)
    except Exception as e:  # noqa: BLE001
        log.warning("Market eşleme çözümleyicisi hata verdi: %s", e)
        map_report = {"error": f"{type(e).__name__}: {e}"}

    # 4) Kadro/haber ve dış tahminler
    news = {}
    for src in registry.NEWS_SOURCES:
        got = board.run(src.id, src.name, lambda s=src: s.team_news(client, today, today_fx)) or {}
        for k, v in got.items():
            news.setdefault(k, v)
    prio_fx = [f for f in today_fx if f.league_id]
    rss = registry.rss_news(client, board, prio_fx)
    try:
        squad.add_coach_signals(news, news_rss.coach_change_keys(rss), prio_fx)
    except Exception as e:  # noqa: BLE001
        log.warning("TD sinyali eklenemedi: %s", e)
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
    tables: dict[str, dict | None] = {}     # lig → puan durumu (yalnız bugün maçı olan ligler)
    lg_avgs: dict[str, dict] = {}
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
            if odds_pool is not None and mk:
                try:
                    m["odds_analysis"] = odds_pool.analyze(mk.get("implied"), f.league_id)
                except Exception as e:  # noqa: BLE001
                    log.info("Oran analizi %s: %s", mid, e)
            # istatistik
            M = models.get(f.league_id or "")
            th = ta = None
            if M and rows_l:
                th, ta = M.team(f.home), M.team(f.away)
                if th and ta:
                    m["stats"] = {"home": stats.team_stats(rows_l, th, today, "home"),
                                  "away": stats.team_stats(rows_l, ta, today, "away"),
                                  "h2h": stats.h2h(rows_l, th, ta, today),
                                  "h2h_summary": stats.h2h_summary(rows_l, th, ta, today)}
                    if lg and not lg.cup:
                        try:
                            if f.league_id not in tables:
                                tables[f.league_id] = standings.build(rows_l, today)
                            tb = tables[f.league_id]
                            ph, pa = standings.position(tb, th), standings.position(tb, ta)
                            if ph and pa:
                                m["table"] = {"home": ph, "away": pa}
                        except Exception as e:  # noqa: BLE001
                            log.info("Puan durumu %s: %s", mid, e)
                    src_name = (rows_l[-1].get("src") or "football-data.co.uk") if rows_l else "football-data.co.uk"
                    if src_name == tff.SOURCE:
                        src_name = tff.ATTRIBUTION
                    st_item = board.items.get("football_data_history")
                    m["provenance"]["stats"] = {"source": src_name + (" + xG" if M.xg else ""),
                                                "t": st_item.fetched_at if st_item else now_iso()}
            m.setdefault("stats", None)
            # haberler (RSS) — yorumdan önce
            attach_news(m, f, rss)
            # kadro
            m["squad"] = squad.build(f.home, f.away, f.kickoff, f.league_id, news, all_fx)
            if m["squad"]:
                m["provenance"]["squad"] = {"source": m["squad"]["source"] or "takvim", "t": m["squad"]["fetched_at"]}
            # Elo (ClubElo) — veri varsa her maça
            elo = None
            if elo_table:
                try:
                    elo = elo_table.pair(f.home, f.away, None if (not lg or lg.cup) else f.league_id)
                except Exception as e:  # noqa: BLE001
                    log.info("Elo eşleme %s: %s", mid, e)
            if elo:
                m["elo"] = {k: elo[k] for k in ("home", "away", "source", "date")}
            if f.extra.get("referee"):
                m["referee"] = f.extra["referee"]
                if f.extra.get("referee_source"):
                    m["provenance"]["referee"] = {"source": f.extra["referee_source"], "t": f.fetched_at}
            # model
            try:
                m["model"] = simulation.predict(f.home, f.away, f.league_id, models, m["squad"], mid, elo=elo,
                                                  referee=f.extra.get("referee"))
            except Exception as e:  # noqa: BLE001
                log.warning("Simülasyon %s: %s", mid, e); m["model"] = None
            # piyasa-tabanlı model: lig modeli yoksa m.model, varsa kıyas için m.market_model
            try:
                mm = market_lambda.build_model(f.odds, seed_for("mkt-" + mid), config.MC_SIMS)
            except Exception as e:  # noqa: BLE001
                log.info("Piyasa modeli %s: %s", mid, e); mm = None
            if mm and not m["model"]:
                m["model"] = mm
            elif mm:
                m["market_model"] = {k: mm[k] for k in ("lambda_home", "lambda_away", "rho", "ht_share",
                                                        "probs", "extra", "htft", "fit_kl", "source")}
            try:
                m["consistency"] = market_lambda.consistency(m["odds"], mm)
            except Exception as e:  # noqa: BLE001
                log.info("Tutarlılık %s: %s", mid, e); m["consistency"] = []
            if m["model"] and m["model"].get("source") == "piyasa":
                m["provenance"]["model"] = {"source": "iddaa oranları (Shin) → Dixon-Coles + 10.000 MC", "t": now_iso()}
                m["flags"].append("Piyasa modeli")
            elif m["model"]:
                m["provenance"]["model"] = {"source": "OZBET Dixon-Coles + 10.000 MC", "t": now_iso()}
                if m["model"]["data_quality"] == "low":
                    m["flags"].append("Düşük veri")
            else:
                m["flags"].append("Veri yetersiz")
            if not lg:
                m["flags"].append("Lig dışı/düşük kapsam")
            # konsensüs + değer + yorum
            ext = find_prediction(preds, f)
            m["consensus"] = consensus.build(ext, None if (m["model"] or {}).get("source") == "piyasa"
                                       else (m["model"] or {}).get("probs"), (mk or {}).get("implied"))
            if ext:
                m["provenance"]["predictions"] = {"source": ", ".join(e["source"] for e in ext),
                                                  "t": ext[0]["fetched_at"]}
            if m["model"] and m["model"].get("source") != "piyasa" and mk and "1" in mk["implied"] and max(
                    abs(m["model"]["probs"][k] - mk["implied"][k]) for k in ("1", "X", "2")) > value.MAX_EDGE:
                m["flags"].append("Model-piyasa farkı çok büyük (veri hatası olabilir)")
            if th and ta and rows_l:
                try:
                    if f.league_id not in lg_avgs:
                        lg_avgs[f.league_id] = trends.league_averages(rows_l)
                    tr = trends.build(rows_l, th, ta, f.home, f.away, today, all_probs(m["model"]), m["odds"],
                                      lg_avgs[f.league_id])
                    if tr:
                        m["trends"] = tr
                except Exception as e:  # noqa: BLE001
                    log.info("Trend %s: %s", mid, e)
            cup = bool(lg and lg.cup) or not lg
            if cup and m["model"] and m["model"].get("source") != "piyasa":
                m["flags"].append(CUP_FLAG_ELO if m["model"].get("method") == "elo" else CUP_FLAG)
            m["value"] = [] if (cup or (m["model"] or {}).get("source") == "piyasa") else value.find_value(all_probs(m["model"]), m["odds"], (mk or {}).get("implied"), trust)
            commentator.annotate(m, trust, use_llm=not args.no_llm and lg is not None)
            if f.result:
                m["status"] = "finished"
            matches.append(m)
        except Exception as e:  # noqa: BLE001 — tek maçtaki beklenmeyen veri tüm çalıştırmayı düşürmesin
            log.warning("Maç %s - %s işlenemedi: %s", f.home, f.away, e)
            bad_matches.append(f"{f.home} - {f.away}: {type(e).__name__}")

    # iddaa oran arşivi: yalnız bu çalıştırmada kaynaktan gelen maçlar (açılış bir kez, kapanış ko öncesi)
    arch_info = None
    try:
        arch_info = _update_iddaa_archive(data, today, now, matches, hist, hist_results)
    except Exception as e:  # noqa: BLE001
        log.warning("iddaa arşivi güncellenemedi: %s", e)
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
    matches = validate.dedupe_matches(matches, vrep)
    matches.sort(key=lambda m: (m["league_priority"], m["kickoff"], m["home"]["name"]))
    quality = _quality(prio, models, matches, unknown_leagues=sorted(
        {f.league_name_raw for f in today_fx if not f.league_id and f.league_name_raw}), cross=cross,
        validation=vrep.as_dict())
    quality["market_map"] = map_report

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
        "standings": {l: tables[l] for l in leagues_present if tables.get(l)},
        "iddaa_archive": arch_info,
        "market_labels": all_labels(),
        "market_categories": market_categories(),
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
    try:
        hsum = health.update(data / "health.json", now_iso(), doc["run_label"], board.as_list(), quality)
    except Exception as e:  # noqa: BLE001
        log.warning("Sağlık geçmişi yazılamadı: %s", e)
        hsum = {"sources": {}, "alerts": [], "runs": 0}
    _write(data / "status.json", {"generated_at": now_iso(), "run_label": doc["run_label"], "sources": board.as_list(),
                                  "health": hsum, "quality": quality})
    n_model = sum(1 for m in matches if m.get("model"))
    log.info("Bitti: %d maç (%d modelli), %d kaynak ok", len(matches), n_model,
             sum(1 for s in board.as_list() if s["status"] == "ok"))
    return doc


def _update_iddaa_archive(data: Path, today: date, now: datetime, matches: list[dict], hist: dict,
                          hist_results: dict) -> dict:
    """Arşive birleştir, son 7 günün sonuçlarını doldur, manifesti yaz; sonuçlu satır ≥30 ise iddaa eşleşmesi."""
    iddaa_archive.update(data, matches, {}, now)
    by_src: dict[str, dict[str, list[dict]]] = {}
    for lid, rows in hist.items():
        for r in rows:
            by_src.setdefault(r.get("src") or "football-data.co.uk", {}).setdefault(lid, []).append(r)
    sources = [(name, registry.results_from_history(h)) for name, h in by_src.items()]
    sources.append(("diğer", hist_results))
    filled = iddaa_archive.fill_results(data, today, now, sources, registry.lookup_result)
    idx = iddaa_archive.write_index(data, now)
    info = {"rows": idx["rows"], "resulted": idx["resulted"], "filled_now": filled,
            "min_n": odds_analysis.IDDAA_MIN_N, "months": sorted(idx["months"])}
    if idx["resulted"] >= odds_analysis.IDDAA_MIN_N:
        pool = odds_analysis.Pool(odds_analysis.rows_from_iddaa(iddaa_archive.all_rows(data)))
        for m in matches:
            imp = (m.get("market") or {}).get("implied")
            a = pool.analyze(imp, m.get("league"), min_n=odds_analysis.IDDAA_MIN_N) if imp else None
            if a and a.get("status") != "az_ornek":
                m["odds_analysis_iddaa"] = a
    return info


def _cross_source(fixture_lists: dict, merged: list, today: date) -> dict:
    """Nesine ve iddaa'nın ikisinde de olması gereken maçların kaçı tek maç olarak birleştirilebildi.
    Düşük oran = takım/saat eşlemesi bozuluyor (aynı maç iki kez görünür ya da oran yanlış maça gider)."""
    a = [f for f in fixture_lists.get("nesine") or [] if f.kickoff.date() == today]
    b = [f for f in fixture_lists.get("iddaa") or [] if f.kickoff.date() == today]
    if not a or not b:
        return {"pct": None, "note": "İki bülten kaynağından biri yok"}
    joined = sum(1 for f in merged if f.source == "nesine" and f.kickoff.date() == today
                 and "iddaa.com" in f.extra.get("also_in", []))
    base = min(len(a), len(b))
    return {"pct": round(joined / base, 3) if base else None, "joined": joined, "nesine": len(a), "iddaa": len(b)}


def _quality(prio, models, matches, unknown_leagues, cross, validation) -> dict:
    """Günlük eşleşme kalitesi raporu (status.json → Kaynaklar sayfası)."""
    unmatched: dict[str, list[str]] = {}
    tried = hit = 0
    for f in prio:
        M = models.get(f.league_id or "")
        if not M:
            continue
        for name in (f.home, f.away):
            tried += 1
            if M.team(name):
                hit += 1
            else:
                unmatched.setdefault(f.league_id, []).append(name)
    n = len(matches)
    known = [m for m in matches if m["league"] != "OTHER"]
    pct = lambda a, b: round(a / b, 3) if b else None  # noqa: E731
    return {
        "matches": n,
        "league_mapped_pct": pct(len(known), n),
        "team_match_pct": pct(hit, tried),
        "odds_coverage_pct": pct(sum(1 for m in known if m.get("odds")), len(known)),
        "model_coverage_pct": pct(sum(1 for m in known if m.get("model")), len(known)),
        "cross_source_match_pct": cross.get("pct"),
        "cross_source": cross,
        "unmatched_teams": {k: sorted(set(v))[:20] for k, v in unmatched.items()},
        "unknown_leagues": unknown_leagues[:40],
        "validation": validation,
    }


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
