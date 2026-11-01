"""Ingest API for the stands machine (replay-system scouting-sync). All endpoints: psk-hmac.

POST /api/ingest/scouting/      {"events": [envelope, ...]}  -> {"accepted", "duplicates", "rejected"}
GET  /api/ingest/game-config/   the active game_config.json, so tablets get the same metric keys offline
"""
import json
import logging

from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from scanner.views import process_scan
from utils import config_loader
from vendor.ef_platform_kit import validate_envelope

from .auth import psk_hmac_required
from .models import ScoutingEvent

logger = logging.getLogger(__name__)
MAX_EVENTS = 1000
TYPES = {ScoutingEvent.TYPE_DELTA, ScoutingEvent.TYPE_COMMIT}


def _payload_errors(env):
    p = env.get("payload")
    if not isinstance(p, dict):
        return ["payload must be an object"]
    errs = []
    if not isinstance(p.get("team"), int) or not 0 < p["team"] < 100000:
        errs.append("team must be a positive integer")
    if not isinstance(p.get("match_number"), int) or not 0 <= p["match_number"] < 1000:
        errs.append("match_number must be an integer 0-999")
    if not isinstance(p.get("event"), str) or not 0 < len(p["event"]) <= 20:
        errs.append("event required")
    if env["type"] == ScoutingEvent.TYPE_COMMIT and not isinstance(p.get("snapshot"), dict):
        errs.append("snapshot must be an object")
    if env["type"] == ScoutingEvent.TYPE_DELTA and not isinstance(p.get("field"), str):
        errs.append("field required")
    return errs


def _commit_to_scan(p):
    """The snapshot IS the QR JSON; fill anchor fields from the envelope if the tablet left them out."""
    snap = dict(p["snapshot"])
    snap.setdefault("teamNumber", p["team"])
    snap.setdefault("matchNumber", p["match_number"])
    snap.setdefault("comp_code", p["event"])
    if p.get("scout"):
        snap.setdefault("name", p["scout"])
    snap.setdefault("quantifier", p.get("match_type") or "quals")
    return snap


@require_POST
@psk_hmac_required("scouting:write")
def ingest_scouting(request):
    try:
        body = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"error": "invalid JSON"}, status=400)
    events = body.get("events") if isinstance(body, dict) else None
    if not isinstance(events, list):
        return JsonResponse({"error": "body must be {\"events\": [...]}"}, status=400)
    if len(events) > MAX_EVENTS:
        return JsonResponse({"error": f"max {MAX_EVENTS} events per request"}, status=413)

    accepted, duplicates, rejected = [], [], []
    key_id = request.principal["sub"]
    for env in events:
        errs = validate_envelope(env)
        if not errs and env.get("type") not in TYPES:
            errs.append(f"type {env.get('type')} not accepted")
        if not errs:
            errs = _payload_errors(env)
        if errs:
            rejected.append({"id": env.get("id") if isinstance(env, dict) else None, "errors": errs})
            continue
        if ScoutingEvent.objects.filter(pk=env["id"]).exists():
            duplicates.append(env["id"])
            continue
        p = env["payload"]
        row = ScoutingEvent(
            id=env["id"], type=env["type"], source=env["source"][:64], seq=env.get("seq"),
            event=p["event"][:20], match_type=str(p.get("match_type") or "quals")[:16], match_number=p["match_number"],
            team=p["team"], scout=str(p.get("scout") or env.get("scout_session") or "")[:64],
            field=str(p.get("field") or "")[:64], op=str(p.get("op") or "")[:8], value=p.get("value"),
            payload=p, ts_src=int(env["ts_src"]), received_at=env.get("received_at"),
            gateway=str(env.get("gateway") or "")[:64], via=str(env.get("via") or "")[:16], ingest_key=key_id,
        )
        if env["type"] == ScoutingEvent.TYPE_COMMIT:
            # Same path as a QR scan. A validation failure is recorded, not retried forever.
            try:
                status, resp = process_scan(_commit_to_scan(p))
            except Exception:  # noqa: BLE001 — never let one bad commit fail the batch
                logger.exception("process_scan failed for %s", env["id"])
                status, resp = 500, {"error": "processing failed"}
            row.commit_status = status
            row.commit_error = str(resp.get("error", ""))[:256]
            if status == 200 and resp.get("id"):
                row.team_match_data_id = resp["id"]
        try:
            with transaction.atomic():
                row.save(force_insert=True)
            accepted.append(env["id"])
        except IntegrityError:
            duplicates.append(env["id"])  # concurrent duplicate upload
    return JsonResponse({"accepted": accepted, "duplicates": duplicates, "rejected": rejected})


@require_GET
@psk_hmac_required("scouting:read")
def game_config(request):
    return JsonResponse(config_loader.get_config())
