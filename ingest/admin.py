from django.contrib import admin

from .models import IngestKey, ScoutAccuracy, ScoutingEvent


@admin.register(IngestKey)
class IngestKeyAdmin(admin.ModelAdmin):
    list_display = ("key_id", "active", "scopes", "last_used_at", "created_at")
    exclude = ("secret",)


@admin.register(ScoutingEvent)
class ScoutingEventAdmin(admin.ModelAdmin):
    list_display = ("id", "type", "source", "seq", "event", "match_number", "team", "scout", "field", "value", "commit_status")
    list_filter = ("type", "event")
    search_fields = ("source", "scout")


@admin.register(ScoutAccuracy)
class ScoutAccuracyAdmin(admin.ModelAdmin):
    list_display = ("method", "event", "match_number", "alliance", "team", "scout", "metric", "scouted", "reference", "error")
    list_filter = ("method", "event")
