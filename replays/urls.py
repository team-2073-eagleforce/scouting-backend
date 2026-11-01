from django.urls import path

from . import views

urlpatterns = [
    path("", views.replay_list, name="replay_list"),
    path("<str:match_key>/", views.replay_detail, name="replay_detail"),
    path("<str:match_key>/data/", views.replay_json, name="replay_json"),
    path("<str:match_key>/video/", views.replay_video, name="replay_video"),
]

ingest_urlpatterns = [
    path("replay/", views.ingest_replay, name="ingest_replay"),
    path("analysis/", views.ingest_analysis, name="ingest_analysis"),
]
