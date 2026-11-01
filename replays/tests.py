import json

from django.test import TestCase

from ingest.models import IngestKey
from replays.models import MatchAnalysis, MatchReplay
from vendor.ef_platform_kit import sign_request

REPLAY = {"schema": "ef.match-replay/1", "match": {"key": "2026casj_qm12", "alliances": {"red": [2073, 254, 1678], "blue": [118, 971, 1323]}},
          "timebase": {"t0_ms": 0, "t1_ms": 1000}, "robots": [], "coverage": [], "events": [], "provenance": {"version": 2}}
DIGEST = {"schema": "ef.match-digest/1", "caveats": [], "robots": [], "events": []}


class ReplayIngestTests(TestCase):
    def setUp(self):
        IngestKey.objects.create(key_id="hub", secret="s", scopes=["replay:write"])
        IngestKey.objects.create(key_id="stands", secret="t", scopes=["scouting:write"])

    def post(self, path, body, key="hub", secret="s"):
        raw = json.dumps(body).encode()
        h = sign_request(key_id=key, secret=secret, method="POST", target=path, body=raw)
        return self.client.post(path, data=raw, content_type="application/json", headers=h)

    def test_replay_and_analysis_ingest_versions_and_scopes(self):
        r = self.post("/api/ingest/replay/", {"matchKey": "2026casj_qm12", "replay": REPLAY, "digest": DIGEST})
        self.assertEqual(r.status_code, 200, r.content)
        row = MatchReplay.objects.get(match_key="2026casj_qm12")
        self.assertEqual((row.version, row.teams[:2]), (2, [2073, 254]))
        older = dict(REPLAY, provenance={"version": 1})
        self.assertEqual(self.post("/api/ingest/replay/", {"matchKey": "2026casj_qm12", "replay": older, "digest": DIGEST}).status_code, 409)
        self.assertEqual(self.post("/api/ingest/replay/", {"matchKey": "2026casj_qm12", "replay": REPLAY, "digest": DIGEST}, key="stands", secret="t").status_code, 403)
        self.assertEqual(self.post("/api/ingest/replay/", {"matchKey": "bad key!", "replay": REPLAY, "digest": DIGEST}).status_code, 400)
        a = self.post("/api/ingest/analysis/", {"matchKey": "2026casj_qm12", "version": 1, "model": "m", "result": {"summary": "s", "teams": []}})
        self.assertEqual(a.status_code, 200)
        self.assertEqual(MatchAnalysis.objects.get().result["summary"], "s")

    def test_pages_require_login_and_render(self):
        self.post("/api/ingest/replay/", {"matchKey": "2026casj_qm12", "replay": REPLAY, "digest": DIGEST})
        self.assertEqual(self.client.get("/replays/").status_code, 302)
        s = self.client.session; s["email"] = "scout@example.com"; s.save()
        self.assertContains(self.client.get("/replays/?team=2073"), "2026casj_qm12")
        self.assertNotContains(self.client.get("/replays/?team=9999"), "2026casj_qm12")
        self.assertContains(self.client.get("/replays/2026casj_qm12/"), "replay v2")
        self.assertEqual(self.client.get("/replays/2026casj_qm12/data/").json()["replay"]["schema"], "ef.match-replay/1")
        r = self.client.post("/replays/2026casj_qm12/video/", data=json.dumps({"youtube_key": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "youtube_offset_s": 6.5}),
                             content_type="application/json")
        self.assertEqual(r.json()["youtube_key"], "dQw4w9WgXcQ")
        self.assertEqual(MatchReplay.objects.get().youtube_offset_s, 6.5)
