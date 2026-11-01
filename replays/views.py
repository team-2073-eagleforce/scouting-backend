"""Replays: machine ingest (hub → here, psk-hmac) + pages for the team."""
import json
import re

from django.http import Http404, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from helpers import login_required
from ingest.auth import psk_hmac_required

from .models import MatchAnalysis, MatchReplay

KEY_RE = re.compile(r"^[a-z0-9]{1,30}_[a-z]{1,3}\d{1,3}(m\d)?$")
YT_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def _body(request):
    try:
        return json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None


@require_POST
@psk_hmac_required("replay:write")
def ingest_replay(request):
    b = _body(request)
    if not isinstance(b, dict) or not KEY_RE.match(str(b.get("matchKey", ""))):
        return JsonResponse({"error": "matchKey required"}, status=400)
    replay, digest = b.get("replay"), b.get("digest")
    if not isinstance(replay, dict) or replay.get("schema") != "ef.match-replay/1" or not isinstance(digest, dict):
        return JsonResponse({"error": "replay (ef.match-replay/1) and digest required"}, status=400)
    version = int(replay.get("provenance", {}).get("version", 1))
    existing = MatchReplay.objects.filter(match_key=b["matchKey"]).first()
    if existing and existing.version > version:
        return JsonResponse({"status": "older version ignored", "have": existing.version}, status=409)
    alliances = (replay.get("match") or {}).get("alliances") or {}
    teams = [int(t) for t in (alliances.get("red") or []) + (alliances.get("blue") or []) if str(t).isdigit()]
    MatchReplay.objects.update_or_create(match_key=b["matchKey"], defaults={
        "event": b["matchKey"].split("_")[0], "version": version, "replay": replay, "digest": digest, "teams": teams})
    return JsonResponse({"status": "stored", "version": version})


@require_POST
@psk_hmac_required("replay:write")
def ingest_analysis(request):
    b = _body(request)
    if not isinstance(b, dict) or not KEY_RE.match(str(b.get("matchKey", ""))) or not isinstance(b.get("result"), dict):
        return JsonResponse({"error": "matchKey and result required"}, status=400)
    MatchAnalysis.objects.update_or_create(match_key=b["matchKey"], defaults={
        "version": int(b.get("version", 1)), "model": str(b.get("model", ""))[:80],
        "prompt_version": str(b.get("promptVersion", ""))[:40], "result": b["result"]})
    return JsonResponse({"status": "stored"})


@login_required
@require_GET
def replay_list(request):
    qs = MatchReplay.objects.only("match_key", "event", "version", "teams", "received_at")
    team = request.GET.get("team")
    rows = [r for r in qs[:500] if not team or (team.isdigit() and int(team) in r.teams)]
    return render(request, "replays/list.html", {"replays": rows, "team": team or ""})


@login_required
@require_GET
def replay_detail(request, match_key):
    r = MatchReplay.objects.filter(match_key=match_key).first()
    if not r:
        raise Http404("No replay for that match yet")
    analysis = MatchAnalysis.objects.filter(match_key=match_key).first()
    return render(request, "replays/detail.html", {"r": r, "analysis": analysis.result if analysis else None,
                                                   "analysis_model": analysis.model if analysis else ""})


@login_required
@require_GET
def replay_json(request, match_key):
    r = MatchReplay.objects.filter(match_key=match_key).first()
    if not r:
        raise Http404()
    return JsonResponse({"replay": r.replay, "digest": r.digest, "youtube_key": r.youtube_key, "youtube_offset_s": r.youtube_offset_s})


@login_required
@require_POST
def replay_video(request, match_key):
    """Set the official video + where the match starts in it (any signed-in scout can fix the sync)."""
    r = MatchReplay.objects.filter(match_key=match_key).first()
    if not r:
        raise Http404()
    b = _body(request) or {}
    key = str(b.get("youtube_key", "")).strip()
    m = re.search(r"(?:v=|youtu\.be/|embed/)([A-Za-z0-9_-]{11})", key)
    key = m.group(1) if m else key
    if key and not YT_RE.match(key):
        return JsonResponse({"error": "not a YouTube video id/URL"}, status=400)
    try:
        offset = float(b["youtube_offset_s"]) if b.get("youtube_offset_s") not in (None, "") else None
    except (TypeError, ValueError):
        return JsonResponse({"error": "offset must be seconds"}, status=400)
    r.youtube_key, r.youtube_offset_s = key, offset
    r.save(update_fields=["youtube_key", "youtube_offset_s"])
    return JsonResponse({"ok": True, "youtube_key": key, "youtube_offset_s": offset})
