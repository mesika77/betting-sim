"""ESPN public API utilities — score fetching and event matching.

Used by both fetch_odds.py (morning pre-validation) and resolve_bets.py
(evening resolution).
"""

import requests

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports"

ESPN_ENDPOINTS: dict[str, list[tuple[str, str]]] = {
    "football": [
        ("soccer", "eng.1"),           # EPL
        ("soccer", "esp.1"),           # La Liga
        ("soccer", "ger.1"),           # Bundesliga
        ("soccer", "ita.1"),           # Serie A
        ("soccer", "fra.1"),           # Ligue 1
        ("soccer", "uefa.champions"),  # UCL
        ("soccer", "uefa.europa"),     # UEL
    ],
    "basketball": [("basketball", "nba")],
    "baseball": [("baseball", "mlb")],
    "ice-hockey": [("hockey", "nhl")],
    "tennis": [],
}


def _normalise(s: str) -> str:
    return s.strip().lower()


def _names_match(a: str, b: str) -> bool:
    """Loose team-name match: exact after normalisation, or one contains the other."""
    a_n, b_n = _normalise(a), _normalise(b)
    return a_n == b_n or a_n in b_n or b_n in a_n


def _fetch_espn_scoreboard(sport: str, league: str, date_str: str) -> list[dict]:
    """Fetch one ESPN scoreboard endpoint and return normalised event dicts."""
    url = f"{ESPN_BASE}/{sport}/{league}/scoreboard"
    try:
        resp = requests.get(url, params={"dates": date_str.replace("-", "")}, timeout=15)
    except requests.RequestException as exc:
        print(f"[espn] WARNING — network error ({sport}/{league}): {exc}")
        return []

    if resp.status_code != 200:
        print(f"[espn] WARNING — HTTP {resp.status_code} ({sport}/{league})")
        return []

    normalised: list[dict] = []
    for ev in resp.json().get("events", []):
        competitions = ev.get("competitions", [])
        if not competitions:
            continue
        competitors = competitions[0].get("competitors", [])

        home_name = away_name = home_score = away_score = None
        for c in competitors:
            name = c.get("team", {}).get("displayName", "")
            score = c.get("score")
            if c.get("homeAway") == "home":
                home_name, home_score = name, score
            elif c.get("homeAway") == "away":
                away_name, away_score = name, score

        if not home_name or not away_name:
            continue

        completed = ev.get("status", {}).get("type", {}).get("completed", False)
        scores: dict = {}
        if home_score is not None and away_score is not None:
            try:
                scores = {"home": float(home_score), "away": float(away_score)}
            except (ValueError, TypeError):
                pass

        normalised.append({
            "home": home_name,
            "away": away_name,
            "status": "finished" if completed else "scheduled",
            "scores": scores,
        })

    return normalised


def fetch_scores_for_date(
    sport_slug: str, date_str: str, log_prefix: str = "[espn]"
) -> list[dict]:
    """Fetch all events for a sport slug on a given date via ESPN."""
    endpoints = ESPN_ENDPOINTS.get(sport_slug, [])
    if not endpoints:
        return []

    all_events: list[dict] = []
    for sport, league in endpoints:
        events = _fetch_espn_scoreboard(sport, league, date_str)
        print(f"{log_prefix} {sport}/{league} on {date_str}: {len(events)} event(s)")
        all_events.extend(events)

    return all_events


def find_score_event(event_name: str, events: list[dict]) -> dict | None:
    """Find the ESPN event matching 'Home vs Away' event_name.

    Tries both orderings — home/away may differ between the odds provider
    and ESPN (e.g. neutral venues, different data conventions).
    """
    lower = event_name.lower()
    sep = " vs "
    if sep not in lower:
        return None
    idx = lower.index(sep)
    norm_a = event_name[:idx].strip()
    norm_b = event_name[idx + len(sep):].strip()

    for event in events:
        h = event.get("home", "")
        a = event.get("away", "")
        if (
            (_names_match(h, norm_a) and _names_match(a, norm_b))
            or (_names_match(h, norm_b) and _names_match(a, norm_a))
        ):
            return event
    return None


def determine_h2h_winner(score_event: dict) -> str | None:
    """Return winning team displayName, or None on draw / missing scores."""
    scores = score_event.get("scores") or {}
    try:
        h = float(scores["home"])
        a = float(scores["away"])
    except (KeyError, TypeError, ValueError):
        return None
    if h == a:
        return None
    return score_event["home"] if h > a else score_event["away"]


def determine_totals_result(score_event: dict, selection: str) -> str:
    """Determine won/lost for a totals bet. Selection format: 'Over 5.5'."""
    parts = selection.strip().split()
    if len(parts) != 2:
        return "void"
    direction = parts[0].lower()
    try:
        line = float(parts[1])
    except ValueError:
        return "void"
    if direction not in ("over", "under"):
        return "void"

    scores = score_event.get("scores") or {}
    try:
        total = float(scores["home"]) + float(scores["away"])
    except (KeyError, TypeError, ValueError):
        return "void"

    if direction == "over":
        return "won" if total > line else "lost"
    return "won" if total < line else "lost"
