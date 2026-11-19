"""GTA VI trophy rarity forecast: refresh-aware dilution plus progression.

Model, in one paragraph: an Exophase earn rate is earners divided by players
tracked, and both move. Between refreshes the tracked players keep earning,
so a trophy's rate climbs toward a ceiling that depends on what kind of
trophy it is (an early chapter climbs fast and far, a 250-stunt grind barely
moves, the platinum needs 100% completion). When Exophase refreshes, the
tracked base jumps and the rate falls, because most of the newly tracked
players have not earned anything yet. The one refresh anyone has seen did
exactly that: on launch night the base went 638 -> 3,868 players and every
rate but the 100% one fell, a median of -1.59 logit units (ratios 0.16x to
0.57x). The fall was smallest for the trophies a brand-new player can earn
first (fishing challenge 0.57x, Chapter 1 0.39x, arcade game 0.41x) and
largest for late or grindy ones (about 0.16x, i.e. almost no new-cohort
earners at all). I fetched the live Exophase page on 2026-11-19 ~12:27 UTC
and those are the live rates that pattern comes from; the page text I got
did not show the players-tracked header, so the live denominator itself is
not something I can state from that fetch, only the rates and their fall
from the launch-night read.

So, per trophy, the program does three things:
  1. It sorts the trophy into a kind from its own description (chapter,
     story mission, stranger strand, grind, easy first-hour activity, or
     misc), which fixes a ceiling, a climb time, and a "fresh share": the
     fraction of newly tracked players who have already earned it when a
     refresh lands. The fresh shares are read off that one observed
     refresh (about 0.3-0.5 for first-hour trophies, about 0.05 for story
     missions, about 0.0-0.05 for grinds and the platinum).
  2. It projects the old cohort forward on a saturating curve toward the
     ceiling, and the tracked base forward on a growth curve fitted to the
     case history when the base has actually moved, or on a prior when it
     has not. The forecast rate is then earners over players: old-cohort
     earners plus new-cohort earners at the fresh share, over the grown
     base. That is the dilution, done in counts, not as a fudge factor.
  3. It spreads honestly. For a short horizon the page may or may not
     refresh before the target, and those are two different worlds, so the
     quantiles come from a two-branch mixture (no-refresh branch narrow
     and near the last rate, refresh branch wide and far below it), solved
     numerically. For a long horizon the spread is one wide lognormal-ish
     band that grows with the square root of the horizon, wider still for
     grinds and the platinum.

When a case's history actually moves, the program also fits each trophy's
logit slope and the base's log growth by least squares and blends the
fitted drift half-and-half with the saturating curve, so a flat launch
night does not pretend to know a slope and a busy final week does get
listened to. The 100% trophy stays at 100%.

Python 3.13, standard library only, no network, no randomness, no files
read except the case files. Run: MAKEFUN_INPUT_DIR=input
MAKEFUN_OUTPUT_DIR=out python3 main.py
"""

import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
Z_SCORES = [-1.6448536269514722, -0.6744897501960817, 0.0, 0.6744897501960817, 1.6448536269514722]
RELEASE = datetime(2026, 11, 19, 0, 0, 0, tzinfo=timezone.utc)


def clamp_pct(pct):
    """Keep a percent inside the logit-safe band the contest scores on."""
    return min(99.99, max(0.01, pct))


def pct_to_logit(pct):
    p = clamp_pct(pct) / 100.0
    return math.log(p / (1.0 - p))


def logit_to_pct(lg):
    return 100.0 / (1.0 + math.exp(-lg))


def round4(value):
    """Round to 4 decimals, half up, matching the starter's output style."""
    scaled = value * 10000
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    out = whole / 10000
    return int(out) if float(out).is_integer() else out


def norm_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def least_squares_slope(xs, ys):
    """Slope of the least-squares line through (xs, ys); None if degenerate."""
    n = len(xs)
    if n < 2:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = sum((x - mx) ** 2 for x in xs)
    if den <= 0:
        return None
    return num / den


def sort_trophy_into_kind(trophy):
    """Name what kind of trophy this is, with its ceiling, climb time and
    fresh share. Ceilings are long-run judgments for an Exophase-tracked
    base (trophy hunters finish stories far more often than average
    players): Chapter 1 ends near half the base, the final mission near a
    third, a 250-stunt grind near a few percent, the platinum near a few
    percent because it needs 100% completion. Fresh shares come from the
    one observed launch-night refresh (see the module docstring)."""
    desc = (trophy.get("description") or "").lower()
    name = (trophy.get("name") or "").lower()
    tier = trophy.get("tier") or ""
    if tier == "platinum":
        return {"kind": "platinum", "ceiling": 3.0, "tau_days": 21.0, "fresh": 0.0}
    if "100% completion" in desc:
        return {"kind": "completion", "ceiling": 1.2, "tau_days": 30.0, "fresh": 0.02}
    if "complete chapter 1" in desc:
        return {"kind": "chapter1", "ceiling": 50.0, "tau_days": 2.5, "fresh": 0.30}
    if "complete chapter" in desc:
        return {"kind": "chapter", "ceiling": 44.0, "tau_days": 3.0, "fresh": 0.10}
    if "complete the final mission" in desc:
        return {"kind": "finale", "ceiling": 35.0, "tau_days": 5.0, "fresh": 0.06}
    if desc.startswith("complete ") and ("mission" in desc or "run" in desc or "heist" in desc or "takedown" in desc or "play" in desc or "headliners" in desc or "glory" in desc):
        return {"kind": "story", "ceiling": 36.0, "tau_days": 3.5, "fresh": 0.05}
    if "final mission for" in desc:
        return {"kind": "strand", "ceiling": 15.0, "tau_days": 6.0, "fresh": 0.03}
    grind_words = ("250 stunts", "100 locations", "collectible card sets",
                   "50 challenges", "gold medal in all", "8 mission strands",
                   "win 20 different races", "win a top fun drone race")
    if any(w in desc for w in grind_words):
        return {"kind": "grind", "ceiling": 3.0, "tau_days": 14.0, "fresh": 0.02}
    easy_words = ("fishing challenge", "arcade game", "try each type of activity",
                  "discover 100 vehicles", "spend $100,000", "earn $250,000",
                  "register 10 vehicles", "purchase all garage", "explore all of leonida")
    if any(w in desc for w in easy_words):
        return {"kind": "easy", "ceiling": 30.0, "tau_days": 3.5, "fresh": 0.40}
    if tier == "silver":
        return {"kind": "silver", "ceiling": 6.0, "tau_days": 10.0, "fresh": 0.05}
    if tier == "gold":
        return {"kind": "gold", "ceiling": 20.0, "tau_days": 7.0, "fresh": 0.05}
    return {"kind": "misc", "ceiling": 20.0, "tau_days": 5.0, "fresh": 0.08}


def read_clock(text):
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except (ValueError, AttributeError, TypeError):
        return None


def learn_from_history(case):
    """Fit what the case history actually shows: per-trophy logit drift
    and tracked-base growth, plus how stale the last read is. A history
    that never moves returns no fits, and the priors below do the work."""
    history = case.get("history") or []
    trophies = case.get("trophies") or []
    reads = []
    for entry in history:
        when = read_clock(entry.get("at") or entry.get("slot") or "")
        if when is None:
            continue
        rates = entry.get("rates") or []
        players = entry.get("players_tracked")
        reads.append((when, players, rates))
    reads.sort(key=lambda r: r[0])
    info = {"drift": {}, "base_growth_per_day": None, "stale_hours": 0.0,
            "span_hours": 0.0, "last_players": None, "last_rates": None}
    if not reads:
        return info
    info["last_players"] = reads[-1][1]
    info["last_rates"] = reads[-1][2]
    info["span_hours"] = (reads[-1][0] - reads[0][0]).total_seconds() / 3600.0
    last_change = reads[0][0]
    seen_players = reads[0][1]
    for when, players, _rates in reads:
        if players != seen_players:
            seen_players = players
            last_change = when
    info["stale_hours"] = (reads[-1][0] - last_change).total_seconds() / 3600.0
    days = [(when - RELEASE).total_seconds() / 86400.0 for when, _p, _r in reads]
    log_players = [math.log(p) for _w, p, _r in reads
                   if isinstance(p, (int, float)) and p and p > 0]
    day_list = [d for d, (_w, p, _r) in zip(days, reads)
                if isinstance(p, (int, float)) and p and p > 0]
    if len(set(log_players)) >= 3:
        slope = least_squares_slope(day_list, log_players)
        if slope is not None:
            info["base_growth_per_day"] = min(max(slope, 0.0), 1.2)
    for idx in range(len(trophies)):
        xs, ys = [], []
        for d, (_when, _p, rates) in zip(days, reads):
            if idx < len(rates) and isinstance(rates[idx], (int, float)):
                xs.append(math.log1p(max(d, 0.0)))
                ys.append(pct_to_logit(rates[idx]))
        if len(set(ys)) >= 3 and len(xs) >= 4:
            slope = least_squares_slope(xs, ys)
            if slope is not None:
                info["drift"][idx] = slope
    return info


def project_tracked_base(info, horizon_days):
    """How many players will Exophase track at the target? Fitted log
    growth when the history moved; otherwise a prior that grows fast
    early and flattens: (1 + 1.8 * days) ** 0.85, capped at 25x."""
    last = info["last_players"]
    if not isinstance(last, (int, float)) or not last or last <= 0:
        return 1.0
    if info["base_growth_per_day"] is not None:
        factor = math.exp(info["base_growth_per_day"] * horizon_days)
    else:
        factor = (1.0 + 1.8 * horizon_days) ** 0.85
    return min(max(factor, 1.0), 25.0)


def project_old_cohort_rate(last_rate, kind, horizon_days, fitted_drift):
    """Where the already-tracked cohort's rate goes: a saturating climb
    toward the kind ceiling, blended half-and-half with the fitted logit
    drift when the history earned one."""
    ceiling = kind["ceiling"]
    tau = kind["tau_days"]
    # Saturate in logit space, not in rate space: a rate-space curve
    # front-loads the climb and would add over a point to Chapter 1 in
    # 90 minutes, which no cohort of players can actually do.
    grown_logit = pct_to_logit(ceiling) + (
        pct_to_logit(last_rate) - pct_to_logit(ceiling)
    ) * math.exp(-horizon_days / tau)
    drift_curve = grown_logit - pct_to_logit(last_rate)
    drift = drift_curve
    if fitted_drift is not None:
        drift_fit = fitted_drift * math.log1p(horizon_days)
        drift_fit = min(max(drift_fit, -2.5), 2.5)
        drift = 0.5 * drift_curve + 0.5 * drift_fit
    drift = min(max(drift, -3.0), 3.0)
    return logit_to_pct(pct_to_logit(last_rate) + drift)


def refresh_jump_factor(last_players):
    """Size of one Exophase refresh jump in tracked players. The launch
    catch-up was about 6x from a tiny base; later jumps shrink as the
    base grows, roughly like 1 + 2500 / players."""
    if not isinstance(last_players, (int, float)) or not last_players or last_players <= 0:
        return 6.0
    if last_players < 1500:
        return 6.0
    return 1.0 + 2500.0 / last_players


def dilute_by_newcomers(old_rate, growth_factor, fresh, late_horizon):
    """Earners over players after the base grows: old earners plus
    newcomers who arrive already holding the trophy at the fresh share.
    Late in the week newcomers are less fresh than on launch night, so
    the fresh share is pulled halfway toward 1 for long horizons."""
    f = fresh if not late_horizon else 0.45 + 0.55 * fresh
    return old_rate * (1.0 + (growth_factor - 1.0) * f) / growth_factor


def mixture_quantile(centers, spreads, weights, tau):
    """The tau quantile of a mixture of normals on the logit scale,
    found by bisection. Centers, spreads and weights line up branch by
    branch; weights must sum to 1."""
    lo = min(c - 6.0 * s for c, s in zip(centers, spreads))
    hi = max(c + 6.0 * s for c, s in zip(centers, spreads))
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        cdf = sum(w * norm_cdf((mid - c) / s)
                  for c, s, w in zip(centers, spreads, weights))
        if cdf < tau:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def forecast_trophy(last_rate, kind, info, horizon_days, idx):
    """Five quantiles for one trophy, in percent, non-decreasing."""
    if last_rate is not None and last_rate >= 99.99:
        return [100, 100, 100, 100, 100]
    base = last_rate if isinstance(last_rate, (int, float)) else 0.0
    base = min(max(base, 0.0), 100.0)
    fitted = info["drift"].get(idx)
    old_rate = project_old_cohort_rate(base, kind, horizon_days, fitted)
    if horizon_days <= 0.25:
        # Short horizon: the page may or may not refresh before the
        # target. No-refresh branch sits near the last rate; refresh
        # branch sits a jump below it. The longer the page has sat
        # unchanged, the more weight the refresh branch gets.
        jump = refresh_jump_factor(info["last_players"])
        refreshed = dilute_by_newcomers(old_rate, jump, kind["fresh"], False)
        stale = info["stale_hours"]
        p_refresh = 0.75 if stale >= 2.0 else (0.5 if stale >= 0.5 else 0.35)
        centers = [pct_to_logit(old_rate), pct_to_logit(refreshed)]
        spreads = [0.30, 0.55]
        weights = [1.0 - p_refresh, p_refresh]
        logits = [mixture_quantile(centers, spreads, weights, tau)
                  for tau in LEVELS]
    else:
        growth = project_tracked_base(info, horizon_days)
        median = dilute_by_newcomers(old_rate, growth, kind["fresh"], True)
        sigma = 0.85 + 0.30 * math.sqrt(horizon_days)
        if kind["kind"] in ("grind", "platinum", "completion"):
            sigma += 0.25
        center = pct_to_logit(median)
        logits = [center + z * sigma for z in Z_SCORES]
    quantiles = []
    prev = 0.0
    for lg in logits:
        q = logit_to_pct(lg)
        q = min(max(q, 0.0), 100.0)
        q = max(q, prev)
        quantiles.append(round4(q))
        prev = q
    return quantiles


def forecast_case(case):
    if not case.get("history"):
        raise ValueError("case has no history")
    info = learn_from_history(case)
    last_rates = info["last_rates"] or []
    horizon_days = case.get("horizon_minutes", 0) / 1440.0
    rows = []
    for idx, trophy in enumerate(case.get("trophies") or []):
        kind = sort_trophy_into_kind(trophy)
        rate = last_rates[idx] if idx < len(last_rates) else None
        rows.append({"id": trophy["id"],
                     "q": forecast_trophy(rate, kind, info, horizon_days, idx)})
    return {"trophies": rows}


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        forecast = forecast_case(case)
        out = OUTPUT_DIR / (path.stem + ".out")
        out.write_text(json.dumps(forecast, separators=(",", ":")) + "\n",
                       encoding="utf-8")


if __name__ == "__main__":
    main()
