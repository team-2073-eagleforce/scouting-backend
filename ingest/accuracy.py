"""Scout accuracy comparisons. Offline/batch only (management command) — never on a request path.

Results go to ScoutAccuracy as plain data; nothing renders them yet. Two methods ship now:

1. delta_vs_commit (no external data needed)
   Replays a scout's live BLE taps (scouting.delta.v1, set/inc) up to their commit and compares the
   result with the numbers they finally submitted. Large gaps mean the totals were typed in at the end
   instead of tapped live — or the live taps were wrong.

2. alliance_vs_tba (needs TBA + a mapping)
   Sums an alliance's scouted metric (latest commit per team; several scouts on one team are averaged)
   and compares it with TBA's official score_breakdown. The mapping lives in game_config.json, because
   it's per season:

     "accuracy": {"tba": [
        {"metric": "autoScore", "breakdown_field": "autoFuelCount"},
        {"metric": "teleScore", "breakdown_field": "teleopFuelCount", "scale": 1.0}
     ]}

   No mapping → this method is skipped (reported, not an error).

Adding OCR later (alliance_vs_ocr) = another function writing rows with a different `method`.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from statistics import mean

from .models import ScoutAccuracy, ScoutingEvent

logger = logging.getLogger(__name__)

TBA_COMP_LEVEL = {"quals": "qm", "qual": "qm", "qm": "qm", "playoff": "sf", "playoffs": "sf", "sf": "sf",
                  "final": "f", "finals": "f", "f": "f", "prac": "pr", "practice": "pr"}


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _save(method, *, event, match_type, match_number, metric, alliance="", team=None, scout="",
          scouted=None, reference=None, details=None):
    err = None if scouted is None or reference is None else scouted - reference
    ScoutAccuracy.objects.update_or_create(
        method=method, event=event, match_type=match_type, match_number=match_number,
        alliance=alliance, team=team, scout=scout, metric=metric,
        defaults={"scouted": scouted, "reference": reference, "error": err, "details": details or {}},
    )


def delta_vs_commit(event: str) -> int:
    """Returns number of rows written."""
    rows = 0
    commits = ScoutingEvent.objects.filter(event=event, type=ScoutingEvent.TYPE_COMMIT)
    for c in commits:
        deltas = ScoutingEvent.objects.filter(
            event=event, type=ScoutingEvent.TYPE_DELTA, source=c.source,
            match_number=c.match_number, team=c.team, ts_src__lte=c.ts_src,
        ).order_by("ts_src", "seq")
        if not deltas.exists():
            continue  # QR-only / non-live scout: nothing to compare
        live = {}
        for d in deltas:
            if d.op == "inc":
                live[d.field] = (live.get(d.field) or 0) + (_num(d.value) or 0)
            else:
                live[d.field] = d.value
        snapshot = (c.payload or {}).get("snapshot") or {}
        mismatches = 0
        for field, live_val in live.items():
            s, l = _num(snapshot.get(field)), _num(live_val)
            if s is None or l is None:
                continue
            if s != l:
                mismatches += 1
            _save("delta_vs_commit", event=event, match_type=c.match_type, match_number=c.match_number,
                  team=c.team, scout=c.scout, metric=field, scouted=s, reference=l,
                  details={"source": c.source, "deltas": deltas.count()})
            rows += 1
        _save("delta_vs_commit", event=event, match_type=c.match_type, match_number=c.match_number,
              team=c.team, scout=c.scout, metric="__summary__", scouted=float(mismatches), reference=0.0,
              details={"fields_compared": len(live), "source": c.source})
        rows += 1
    return rows


def alliance_vs_tba(event: str, mapping: list[dict], fetch_match) -> dict:
    """fetch_match(match_key) -> TBA /match/{key} JSON (alliances + score_breakdown) or None."""
    if not mapping:
        return {"skipped": "no accuracy.tba mapping in game_config.json", "rows": 0}
    by_match = defaultdict(lambda: defaultdict(list))  # (type, num) -> team -> [snapshot]
    for c in ScoutingEvent.objects.filter(event=event, type=ScoutingEvent.TYPE_COMMIT).order_by("ts_src"):
        by_match[(c.match_type, c.match_number)][c.team].append((c.scout, (c.payload or {}).get("snapshot") or {}))
    rows, missing = 0, []
    for (mtype, mnum), teams in by_match.items():
        level = TBA_COMP_LEVEL.get(str(mtype).lower(), "qm")
        key = f"{event.lower()}_{level}{mnum}" if level == "qm" else f"{event.lower()}_{level}{mnum}m1"
        m = fetch_match(key)
        if not m or not m.get("score_breakdown"):
            missing.append(key)
            continue
        for alliance in ("red", "blue"):
            team_keys = (m.get("alliances", {}).get(alliance, {}) or {}).get("team_keys", [])
            nums = [int(t[3:]) for t in team_keys if t.startswith("frc")]
            breakdown = m["score_breakdown"].get(alliance) or {}
            for spec in mapping:
                metric, field, scale = spec["metric"], spec["breakdown_field"], float(spec.get("scale", 1.0))
                per_team, covered = {}, []
                for t in nums:
                    vals = [_num(s.get(metric)) for _, s in teams.get(t, [])]
                    vals = [v for v in vals if v is not None]
                    if vals:
                        per_team[t] = mean(vals)
                        covered.append(t)
                ref = _num(breakdown.get(field))
                if not covered or ref is None:
                    continue
                _save("alliance_vs_tba", event=event, match_type=mtype, match_number=mnum, alliance=alliance,
                      metric=metric, scouted=sum(per_team.values()), reference=ref * scale,
                      details={"teams": nums, "covered": covered, "per_team": per_team, "breakdown_field": field,
                               "scouts": sorted({sc for t in covered for sc, _ in teams.get(t, [])})})
                rows += 1
    return {"rows": rows, "missing_tba": missing}
