import secrets

from django.core.management.base import BaseCommand, CommandError

from ingest.models import IngestKey


class Command(BaseCommand):
    help = "Create (or rotate) a psk-hmac ingest key for a stands machine. Prints the secret once."

    def add_arguments(self, parser):
        parser.add_argument("key_id")
        parser.add_argument("--scopes", default="scouting:write,scouting:read")
        parser.add_argument("--description", default="")
        parser.add_argument("--rotate", action="store_true", help="replace the secret of an existing key")
        parser.add_argument("--revoke", action="store_true")

    def handle(self, key_id, scopes, description, rotate, revoke, **_):
        existing = IngestKey.objects.filter(key_id=key_id).first()
        if revoke:
            if not existing:
                raise CommandError("no such key")
            existing.active = False
            existing.save()
            self.stdout.write(f"revoked {key_id}")
            return
        if existing and not rotate:
            raise CommandError(f"{key_id} exists; use --rotate to replace its secret")
        secret = secrets.token_urlsafe(32)
        key = existing or IngestKey(key_id=key_id)
        key.secret, key.scopes, key.active = secret, [s.strip() for s in scopes.split(",") if s.strip()], True
        if description:
            key.description = description
        key.save()
        self.stdout.write(self.style.SUCCESS(f"key id: {key_id}\nsecret: {secret}\nscopes: {key.scopes}"))
        self.stdout.write("Enter these in the stands machine: Settings → Tablet Sync → Upload to scouting backend.")
