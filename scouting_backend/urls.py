from django.conf.urls.static import static
from django.conf import settings
from django.contrib import admin
from django.urls import path, include

from scouting_backend import settings
from teams import views as team_views
from scanner import views as scanner_views
from strategy import views as strategy_views
from authenticate import views as auth_views
from authenticate import views_admin as admin_views
from plugins import plugin_manager
from replays.urls import ingest_urlpatterns as replay_ingest_urls

urlpatterns = [
    path('admin/', admin.site.urls),
    # ... your other paths ...
]

# This allows Django to serve static files during development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.BASE_DIR / "static")

urlpatterns = [
    # path('admin/', admin.site.urls),  # Disabled Django admin
    path('', team_views.home, name='home'),
    path('scanner/', scanner_views.scanner, name='scanner'),
    path('teams/', team_views.display_teams, name='teams'),
    path('teams/<int:team_number>/', team_views.team_page, name='team_page'),
    path('teams/<int:team_number>/clear-pit/', team_views.clear_pit_data, name='clear_pit_data'),
    path("teams/human-scout/<int:team_number>/", team_views.human_player_submit, name="human-scout"),
    path('get_events/', team_views.get_events),
    path('pit_scouting/<int:team_number>/', team_views.pit_scouting, name='pit_scouting'),
    path('strategy/rankings/', strategy_views.rankings, name='rankings'),
    path('strategy/dashboard/', strategy_views.dashboard, name='dashboard'),
    path('strategy/picklist/', strategy_views.picklist, name='picklist'),
    path('strategy/picklist/submit/', strategy_views.picklist_submit, name='picklist_submit'),
    path('api/get_path_data/<int:team_number>/', strategy_views.get_path_data, name='get_path_data'),
    path('api/team_matches/<int:team_number>/', strategy_views.team_matches_detail, name='team_matches_detail'),
    path('api/team_info/<int:team_number>/', strategy_views.team_info, name='team_info'),
    path('api/toggle_exclude_match/', strategy_views.toggle_exclude_match, name='toggle_exclude_match'),
    path('api/tba_videos/', team_views.tba_videos, name='tba_videos'),
    # Machine ingest (stands machine scouting-sync, platform-kit psk-hmac auth)
    path('api/ingest/', include('ingest.urls')),
    path('api/ingest/', include(replay_ingest_urls)),
    # AI match replays (from the hub) + viewer
    path('replays/', include('replays.urls')),
    path("auth/", include("authenticate.urls")),
    path('admin-panel/', admin_views.admin_panel, name='admin_panel'),
    path('admin-panel/add-user/', admin_views.add_user, name='add_user'),
    path('admin-panel/remove-user/<int:user_id>/', admin_views.remove_user, name='remove_user'),
    path('admin-panel/match-editor/', admin_views.match_data_editor, name='match_editor'),
    path('admin-panel/api/get-teams/', admin_views.get_teams_for_event, name='get_teams'),
    path('admin-panel/api/get-quantifiers/', admin_views.get_quantifiers_for_team, name='get_quantifiers'),
    path('admin-panel/api/get-matches/', admin_views.get_matches_for_team, name='get_matches'),
    path('admin-panel/api/load-match/', admin_views.load_match_data, name='load_match'),
    path('admin-panel/update-match/', admin_views.update_match_data, name='update_match'),
    path('set-theme/', auth_views.set_theme, name='set_theme'),
    # Plugin management
    path('admin-panel/plugins/enable/', admin_views.plugins_enable, name='plugins_enable'),
    path('admin-panel/plugins/upload/', admin_views.plugins_upload, name='plugins_upload'),
    path('admin-panel/plugins/install-deps/', admin_views.plugins_install_deps, name='plugins_install_deps'),
    path('admin-panel/theme/', admin_views.admin_set_theme_color, name='admin_set_theme_color'),
    path('admin-panel/logo/', admin_views.admin_set_logo_url, name='admin_set_logo_url'),
]

# Add plugin URLs
urlpatterns += plugin_manager.get_plugin_urls()
