"""Machine-to-machine ingest: offline scouting events from the stands machine (replay-system
scouting-sync), and the raw material for scout-accuracy comparisons.

Nothing here is displayed by default — it's stored as data. Commits are ALSO written into
Team_Match_Data through scanner.views.process_scan, exactly like a QR scan.
"""
from django.db import models


class IngestKey(models.Model):
    """A pre-shared key for platform-kit psk-hmac auth (one per stands machine / service).

    The secret is stored as-is because HMAC verification needs it (v1 "simple but consistent" auth).
    Create with:  python manage.py create_ingest_key stands1
    """

    key_id = models.CharField(max_length=64, unique=True)
    secret = models.CharField(max_length=128)
    scopes = models.JSONField(default=list)
    description = models.CharField(max_length=200, blank=True, default="")
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.key_id} ({'active' if self.active else 'revoked'})"


class ScoutingEvent(models.Model):
    """Every scouting.delta.v1 / scouting.commit.v1 envelope, exactly once (pk = envelope ULID)."""

    TYPE_DELTA = "scouting.delta.v1"
    TYPE_COMMIT = "scouting.commit.v1"

    id = models.CharField(max_length=26, primary_key=True)
    type = models.CharField(max_length=40, db_index=True)
    source = models.CharField(max_length=64, db_index=True)  # tablet:<deviceId> | qr:<scanner>
    seq = models.IntegerField(null=True)
    event = models.CharField(max_length=20, db_index=True)
    match_type = models.CharField(max_length=16, default="quals")
    match_number = models.IntegerField()
    team = models.IntegerField()
    scout = models.CharField(max_length=64, blank=True, default="")
    field = models.CharField(max_length=64, blank=True, default="")
    op = models.CharField(max_length=8, blank=True, default="")
    value = models.JSONField(null=True, blank=True)
    payload = models.JSONField(default=dict)
    ts_src = models.BigIntegerField()  # tablet clock, epoch ms
    received_at = models.BigIntegerField(null=True)  # stands gateway clock, epoch ms
    gateway = models.CharField(max_length=64, blank=True, default="")
    via = models.CharField(max_length=16, blank=True, default="")
    ingest_key = models.CharField(max_length=64, blank=True, default="")
    ingested_at = models.DateTimeField(auto_now_add=True)
    # commits only: outcome of process_scan()
    team_match_data = models.ForeignKey("teams.Team_Match_Data", null=True, blank=True, on_delete=models.SET_NULL)
    commit_status = models.IntegerField(null=True, blank=True)
    commit_error = models.CharField(max_length=256, blank=True, default="")

    class Meta:
        indexes = [models.Index(fields=["event", "match_number", "team"]), models.Index(fields=["source", "seq"])]
        ordering = ["ts_src"]


class ScoutAccuracy(models.Model):
    """One comparison of scouted values against a reference. Computed offline (management command),
    never on a request path. `method` names the comparison so new ones can be added without migrations:

      delta_vs_commit   live taps (sum of deltas) vs the scout's final submitted value
      alliance_vs_tba   sum of an alliance's scouted metric vs TBA's official score breakdown
      alliance_vs_ocr   same, vs the live scoreboard OCR (once the hub provides it)
    """

    method = models.CharField(max_length=32, db_index=True)
    event = models.CharField(max_length=20, db_index=True)
    match_type = models.CharField(max_length=16, default="quals")
    match_number = models.IntegerField()
    alliance = models.CharField(max_length=4, blank=True, default="")
    team = models.IntegerField(null=True, blank=True)
    scout = models.CharField(max_length=64, blank=True, default="")
    metric = models.CharField(max_length=64)
    scouted = models.FloatField(null=True)
    reference = models.FloatField(null=True)
    error = models.FloatField(null=True)
    details = models.JSONField(default=dict)
    computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("method", "event", "match_type", "match_number", "alliance", "team", "scout", "metric")
