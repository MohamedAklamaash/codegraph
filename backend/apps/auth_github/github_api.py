import logging

import requests
from rest_framework.response import Response

from .crypto import decrypt
from .models import GitHubIdentity

logger = logging.getLogger(__name__)


def get_identity_or_reauth(user):
    try:
        identity = user.github_identity
    except GitHubIdentity.DoesNotExist:
        return None, Response({"needs_reauth": True}, status=401)
    if identity.needs_reauth:
        return None, Response({"needs_reauth": True}, status=401)
    return identity, None


def decrypt_token_or_reauth(identity):
    try:
        return decrypt(identity.access_token_enc), None
    except Exception:
        logger.warning("Failed to decrypt GitHub token for user %s", identity.user_id)
        identity.needs_reauth = True
        identity.save(update_fields=["needs_reauth", "updated_at"])
        return None, Response({"needs_reauth": True}, status=401)


def github_get(token, url, params=None, timeout=20):
    """Call GitHub's REST API with standard error mapping.

    Returns either the raw `requests.Response` (on 2xx / 401 / 404, where the
    caller wants to inspect status semantically) or a stable 3-tuple of
    `(error_key, http_status, retry_after)` for error mappings. `retry_after`
    is the `Retry-After` header value for `rate_limited` and `None` for every
    other error key. Callers can destructure unconditionally:
        key, status, retry_after = result

    Error keys:
        - ("github_unreachable", 503, None)   — network/timeout failure
        - ("rate_limited",        503, retry_after) — 403/429
        - ("github_error",        502, None)  — other 4xx/5xx upstream
    """
    try:
        resp = requests.get(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
            },
            params=params,
            timeout=timeout,
        )
    except requests.RequestException as e:
        logger.warning("GitHub network error on %s: %s", url, type(e).__name__)
        return ("github_unreachable", 503, None)

    if resp.status_code in (403, 429):
        return ("rate_limited", 503, resp.headers.get("Retry-After"))

    if resp.status_code >= 400 and resp.status_code != 401 and resp.status_code != 404:
        # 401 and 404 carry semantic meaning the caller handles — bubble the
        # response up. Other 4xx/5xx are folded into a generic upstream error.
        logger.warning("GitHub upstream error %s on %s", resp.status_code, url)
        return ("github_error", 502, None)

    return resp
