from django.contrib import admin

from .models import MatchAnalysis, MatchReplay


@admin.register(MatchReplay)
class MatchReplayAdmin(admin.ModelAdmin):
    list_display = ("match_key", "version", "teams", "youtube_key", "received_at")
    exclude = ("replay", "digest")


@admin.register(MatchAnalysis)
class MatchAnalysisAdmin(admin.ModelAdmin):
    list_display = ("match_key", "version", "model", "received_at")
