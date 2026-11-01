import os

import requests
from django.core.management.base import BaseCommand

from ingest import accuracy
from utils import config_loader


def tba_fetcher():
    key = os.environ.get("X_TBA_AUTH_KEY") or os.environ.get("X_TBA_Auth_Key")
    if not key:
        return None

    def fetch(match_key):
        r = requests.get(f"https://www.thebluealliance.com/api/v3/match/{match_key}",
                         headers={"X-TBA-Auth-Key": key}, timeout=15)
        return r.json() if r.status_code == 200 else None

    return fetch


class Command(BaseCommand):
    help = "Compute scout-accuracy comparisons for an event (stored in ingest.ScoutAccuracy, not displayed)."

    def add_arguments(self, parser):
        parser.add_argument("event", help="comp code as scouted, e.g. 2026casj")
        parser.add_argument("--no-tba", action="store_true", help="only run comparisons that need no internet")

    def handle(self, event, no_tba, **_):
        n = accuracy.delta_vs_commit(event)
        self.stdout.write(f"delta_vs_commit: {n} rows")
        if no_tba:
            return
        fetch = tba_fetcher()
        if not fetch:
            self.stdout.write("alliance_vs_tba: skipped (X_TBA_AUTH_KEY not set)")
            return
        mapping = (config_loader.get_config().get("accuracy") or {}).get("tba") or []
        self.stdout.write(f"alliance_vs_tba: {accuracy.alliance_vs_tba(event, mapping, fetch)}")
