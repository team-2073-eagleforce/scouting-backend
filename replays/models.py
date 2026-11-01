"""AI match replays + analysis from the hub (replay-web-service). Stored here so the scouting site
never depends on the hub being online."""
from django.db import models


class MatchReplay(models.Model):
    match_key = models.CharField(max_length=64, unique=True)  # e.g. 2026casj_qm12
    event = models.CharField(max_length=40, db_index=True)
    version = models.IntegerField(default=1)
    replay = models.JSONField()   # ef.match-replay/1
    digest = models.JSONField()   # ef.match-digest/1
    teams = models.JSONField(default=list)  # [2073, 254, ...] for lookups
    # Optional: official match video + where the match starts in it (seconds), for synced playback.
    youtube_key = models.CharField(max_length=20, blank=True, default="")
    youtube_offset_s = models.FloatField(null=True, blank=True)
    received_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-received_at"]

    def __str__(self):
        return f"{self.match_key} v{self.version}"


class MatchAnalysis(models.Model):
    match_key = models.CharField(max_length=64, unique=True)
    version = models.IntegerField(default=1)
    model = models.CharField(max_length=80, blank=True, default="")
    prompt_version = models.CharField(max_length=40, blank=True, default="")
    result = models.JSONField()
    received_at = models.DateTimeField(auto_now=True)
