"""platform-kit psk-hmac auth for Django views (same spec as every other EagleForce service)."""
import functools

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from vendor.ef_platform_kit import AuthError, PskHmacVerifier, has_scope

from .models import IngestKey


def _lookup(key_id):
    k = IngestKey.objects.filter(key_id=key_id, active=True).first()
    if not k:
        return None
    return {"secret": k.secret, "principal": {"sub": k.key_id, "kind": "device", "scopes": list(k.scopes or [])}}


_verifier = PskHmacVerifier(_lookup)


def psk_hmac_required(scope):
    """Authenticate with EF1-HMAC-SHA256 and require `scope`. CSRF-exempt: no cookies involved."""

    def deco(view):
        @csrf_exempt
        @functools.wraps(view)
        def wrapper(request, *args, **kwargs):
            headers = {k: v for k, v in request.headers.items()}
            if not PskHmacVerifier.applies(headers):
                return JsonResponse({"error": "EF1-HMAC-SHA256 signature required"}, status=401)
            try:
                principal = _verifier.authenticate(method=request.method, target=request.get_full_path(),
                                                   headers=headers, raw_body=request.body)
            except AuthError as e:
                return JsonResponse({"error": str(e)}, status=e.status)
            if not has_scope(principal, scope):
                return JsonResponse({"error": f"missing scope {scope}"}, status=403)
            IngestKey.objects.filter(key_id=principal["sub"]).update(last_used_at=timezone.now())
            request.principal = principal
            return view(request, *args, **kwargs)

        return wrapper

    return deco
