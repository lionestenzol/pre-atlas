"""
Crucix Bridge — OSINT integration for Pre Atlas governance.

Polls Crucix (Atlas-stripped, 7 sources) running on localhost:3117.
Extracts signals relevant to governance decisions:
  - Market data (SPY, BTC, VIX, gold via Yahoo Finance)
  - Economic indicators (FRED: CPI, unemployment, rates; BLS; EIA energy prices)
  - News headlines (GDELT)
  - Social sentiment (Reddit)

Writes output to:
  - cycleboard/brain/osint_feed.json (consumed by CycleBoard OSINT screen)
  - Used by governor_daily.py "World Context" section

Graceful degradation: if Crucix is offline, Atlas continues without OSINT data.

Usage:
  python crucix_bridge.py              # one-shot poll
  python crucix_bridge.py --watch      # poll every 15 minutes
"""

import json
import logging
import time
import sys
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

BASE = Path(__file__).parent.resolve()
BRAIN_DIR = BASE / "cycleboard" / "brain"
CRUCIX_URL = "http://localhost:3117/api/data"
POLL_INTERVAL_SECONDS = 900  # 15 minutes


def _fetch_crucix() -> dict[str, Any] | None:
    """Fetch current intelligence data from Crucix. Returns None if offline."""
    try:
        req = urllib.request.Request(CRUCIX_URL, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
        log.warning("Crucix offline or unreachable: %s", e)
        return None
    except Exception as e:
        log.error("Crucix fetch error: %s", e)
        return None


# ── V2 Extraction Functions ─────────────────────────────────────────


def _extract_economic(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract economic indicators from FRED, BLS, EIA, GSCPI.

    Crucix V2 keys:
      data["fred"]  = [{id, label, value, date, momChange, momChangePct}]
      data["bls"]   = [{id, label, value, date}]
      data["energy"] = {wti, brent, natgas, crudeStocks, signals[]}
      data["gscpi"] = {value, date, ...} or null
    """
    indicators: list[dict[str, Any]] = []

    # FRED indicators (22 economic series)
    for item in data.get("fred", []):
        if not isinstance(item, dict):
            continue
        indicators.append({
            "source": "FRED",
            "indicator": item.get("label", item.get("id", "?")),
            "value": item.get("value"),
            "date": item.get("date"),
            "mom_change": item.get("momChange"),
            "mom_change_pct": item.get("momChangePct"),
        })

    # BLS indicators (jobs, wages)
    for item in data.get("bls", []):
        if not isinstance(item, dict):
            continue
        indicators.append({
            "source": "BLS",
            "indicator": item.get("label", item.get("id", "?")),
            "value": item.get("value"),
            "date": item.get("date"),
        })

    # Energy prices (EIA)
    energy = data.get("energy", {})
    if isinstance(energy, dict):
        for key in ("wti", "brent", "natgas"):
            val = energy.get(key)
            if val is not None:
                indicators.append({
                    "source": "EIA",
                    "indicator": key.upper(),
                    "value": val,
                })

    # Supply chain pressure (GSCPI)
    gscpi = data.get("gscpi")
    if isinstance(gscpi, dict) and gscpi.get("value") is not None:
        indicators.append({
            "source": "GSCPI",
            "indicator": "Supply Chain Pressure",
            "value": gscpi["value"],
            "date": gscpi.get("date"),
        })

    return indicators[:15]


def _extract_market(data: dict[str, Any]) -> dict[str, Any]:
    """Extract market data from Yahoo Finance.

    Crucix V2 keys:
      data["markets"] = {
        indexes: [{symbol, name, price, change, changePct}],
        crypto: [{symbol, name, price, change, changePct}],
        commodities: [{symbol, name, price, change, changePct}],
        rates: [{symbol, name, price, change, changePct}],
        vix: {value, change, changePct},
      }
      data["metals"] = {gold, goldChange, goldChangePct, silver, ...}
    """
    markets = data.get("markets", {})
    metals = data.get("metals", {})

    result: dict[str, Any] = {
        "indexes": [],
        "crypto": [],
        "commodities": [],
        "vix": None,
        "gold": None,
        "silver": None,
    }

    # Market arrays
    for category in ("indexes", "crypto", "commodities", "rates"):
        items = markets.get(category, [])
        if isinstance(items, list):
            result[category] = [
                {
                    "symbol": q.get("symbol", "?"),
                    "name": q.get("name", ""),
                    "price": q.get("price"),
                    "change": q.get("change"),
                    "changePct": q.get("changePct"),
                }
                for q in items
                if isinstance(q, dict) and q.get("price") is not None
            ]

    # VIX fear gauge
    vix = markets.get("vix")
    if isinstance(vix, dict):
        result["vix"] = {
            "value": vix.get("value"),
            "change": vix.get("change"),
            "changePct": vix.get("changePct"),
        }

    # Precious metals
    if isinstance(metals, dict):
        result["gold"] = metals.get("gold")
        result["gold_change_pct"] = metals.get("goldChangePct")
        result["silver"] = metals.get("silver")

    return result


def _extract_news(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract news headlines from GDELT and newsFeed.

    Crucix V2 keys:
      data["gdelt"] = {totalArticles, conflicts, economy, health, topTitles[]}
      data["newsFeed"] = [{headline, source, type, urgent, url}]
    """
    headlines: list[dict[str, Any]] = []

    # GDELT top titles
    gdelt = data.get("gdelt", {})
    if isinstance(gdelt, dict):
        for title in gdelt.get("topTitles", [])[:5]:
            if title:
                headlines.append({"source": "GDELT", "headline": str(title)[:120]})

    # News feed (merged RSS + GDELT + social)
    for item in data.get("newsFeed", [])[:10]:
        if isinstance(item, dict) and item.get("headline"):
            headlines.append({
                "source": item.get("source", "?"),
                "headline": str(item["headline"])[:120],
                "urgent": item.get("urgent", False),
            })

    # Dedupe by headline text
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for h in headlines:
        key = h["headline"][:60].lower()
        if key not in seen:
            seen.add(key)
            unique.append(h)

    return unique[:10]


def _extract_sentiment(data: dict[str, Any]) -> dict[str, Any]:
    """Extract social sentiment from Reddit.

    Crucix V2 key: varies by source config. Reddit data may be under
    various keys depending on Crucix version.
    """
    # The newsFeed already captures Reddit posts tagged type='reddit'
    reddit_posts = [
        item for item in data.get("newsFeed", [])
        if isinstance(item, dict) and item.get("type") == "reddit"
    ]
    return {
        "reddit_count": len(reddit_posts),
        "reddit_urgent": sum(1 for p in reddit_posts if p.get("urgent")),
    }


def _generate_highlights(
    economic: list[dict[str, Any]],
    market: dict[str, Any],
    news: list[dict[str, Any]],
) -> list[str]:
    """Generate 3 human-readable highlights for the daily brief."""
    highlights: list[str] = []

    # 1. Market summary — SPY + BTC + VIX
    parts: list[str] = []
    for idx in market.get("indexes", []):
        if idx.get("symbol") in ("SPY", "^GSPC", "QQQ"):
            pct = idx.get("changePct")
            pct_str = f" ({pct:+.1f}%)" if pct is not None else ""
            parts.append(f"{idx['symbol']}: ${idx['price']:.2f}{pct_str}")
    for cry in market.get("crypto", []):
        sym = cry.get("symbol", "")
        if "BTC" in sym.upper():
            pct = cry.get("changePct")
            pct_str = f" ({pct:+.1f}%)" if pct is not None else ""
            parts.append(f"BTC: ${cry['price']:,.0f}{pct_str}")
            break
    vix = market.get("vix")
    if vix and vix.get("value") is not None:
        parts.append(f"VIX: {vix['value']:.1f}")
    if parts:
        highlights.append("Markets: " + ", ".join(parts[:4]))

    # 2. Top economic indicator with month-over-month change
    for econ in economic:
        if econ.get("mom_change_pct") is not None:
            highlights.append(
                f"Economic: {econ['indicator']} = {econ['value']} "
                f"(MoM {econ['mom_change_pct']:+.1f}%)"
            )
            break
    else:
        if economic:
            top = economic[0]
            highlights.append(f"Economic: {top['indicator']} = {top['value']}")

    # 3. Top news headline
    for n in news:
        if n.get("headline"):
            highlights.append(f"News: {n['headline'][:100]}")
            break

    # Pad
    while len(highlights) < 3:
        highlights.append("No additional signals")

    return highlights[:3]


# ── Main Pipeline ────────────────────────────────────────────────────


def poll_and_extract() -> dict[str, Any]:
    """Main function: poll Crucix, extract relevant signals, write output."""
    raw = _fetch_crucix()

    if raw is None:
        result = {
            "generated_at": datetime.now().isoformat(),
            "status": "offline",
            "highlights": [],
            "economic": [],
            "market": {},
            "news": [],
            "sentiment": {},
        }
    else:
        economic = _extract_economic(raw)
        market = _extract_market(raw)
        news = _extract_news(raw)
        sentiment = _extract_sentiment(raw)
        highlights = _generate_highlights(economic, market, news)

        meta = raw.get("meta", {})
        sources_ok = meta.get("sourcesOk", 0)
        sources_total = meta.get("sourcesQueried", 0)

        result = {
            "generated_at": datetime.now().isoformat(),
            "status": "online",
            "sources": f"{sources_ok}/{sources_total}",
            "sweep_ms": meta.get("totalDurationMs"),
            "highlights": highlights,
            "economic": economic,
            "market": market,
            "news": news,
            "sentiment": sentiment,
        }

    # Write to brain dir for CycleBoard
    BRAIN_DIR.mkdir(parents=True, exist_ok=True)
    out_path = BRAIN_DIR / "osint_feed.json"
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("Wrote osint_feed.json (status=%s)", result["status"])

    return result


def main() -> None:
    watch = "--watch" in sys.argv

    if watch:
        log.info("Crucix bridge watch mode (poll every %ds)", POLL_INTERVAL_SECONDS)
        while True:
            try:
                result = poll_and_extract()
                log.info(
                    "Poll: status=%s, highlights=%d",
                    result["status"], len(result["highlights"]),
                )
            except Exception as e:
                log.error("Poll failed: %s", e)
            time.sleep(POLL_INTERVAL_SECONDS)
    else:
        result = poll_and_extract()
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
