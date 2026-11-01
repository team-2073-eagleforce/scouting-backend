"""Test settings: run the suite on SQLite without a Postgres server.

`strategy`'s migrations contain Postgres-only RunSQL (ALTER COLUMN ... TYPE jsonb), so for tests that app's
tables are created straight from the current models instead. Production keeps using real migrations.

    python manage.py test --settings=scouting_backend.settings_test
"""
import os

os.environ.setdefault("SECRET_KEY", "test-only-secret")
os.environ.setdefault("DEBUG", "True")
os.environ.pop("DATABASE_URL", None)

from .settings import *  # noqa: E402,F401,F403

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
MIGRATION_MODULES = {"strategy": None}
