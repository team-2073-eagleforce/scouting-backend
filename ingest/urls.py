from django.urls import path

from . import views

urlpatterns = [
    path("scouting/", views.ingest_scouting, name="ingest_scouting"),
    path("game-config/", views.game_config, name="ingest_game_config"),
]
