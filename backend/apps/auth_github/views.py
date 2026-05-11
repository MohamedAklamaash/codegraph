import logging
import secrets
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import IntegrityError
from django.http import HttpResponseRedirect
from django.utils.crypto import constant_time_compare
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .crypto import encrypt
from .github_api import decrypt_token_or_reauth, get_identity_or_reauth, github_get
from .models import GitHubIdentity

logger = logging.getLogger(__name__)


class _CsrfExemptSessionAuthentication(SessionAuthentication):
    """SessionAuthentication that does not perform DRF's CSRF check.

    DRF's `SessionAuthentication.enforce_csrf` runs even when the Django
    `csrf_exempt` decorator is applied, so we need a dedicated auth class
    on the views we genuinely want exempt. Used for `LogoutView` only.
    """

    def enforce_csrf(self, request):  # noqa: ARG002
        return


GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"
GITHUB_REPOS_URL = "https://api.github.com/user/repos"
GITHUB_SCOPE = "read:user repo"


@method_decorator(csrf_exempt, name="dispatch")
class GithubOAuthStartView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        if not request.session.session_key:
            request.session.create()
        state = secrets.token_urlsafe(32)
        request.session["gh_oauth_state"] = state
        request.session.modified = True

        params = {
            "client_id": settings.GITHUB_CLIENT_ID,
            "redirect_uri": settings.GITHUB_OAUTH_REDIRECT_URI,
            "scope": GITHUB_SCOPE,
            "state": state,
        }
        authorize_url = f"{GITHUB_AUTHORIZE_URL}?{urlencode(params)}"
        return Response({"authorize_url": authorize_url})


@method_decorator(csrf_exempt, name="dispatch")
class GithubOAuthCallbackView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        code = request.GET.get("code", "")
        state = request.GET.get("state", "")
        expected_state = request.session.get("gh_oauth_state")

        # `constant_time_compare` avoids leaking the state via response-time
        # differences. `expected_state or ""` keeps the comparison length-stable
        # when no state was set in session.
        if (
            not code
            or not state
            or not expected_state
            or not constant_time_compare(state, expected_state or "")
        ):
            logger.warning(
                "GitHub OAuth state mismatch: code=%s url_state=%s session_state=%s session_key=%s",
                bool(code),
                state[:8] + "..." if state else "<empty>",
                (expected_state[:8] + "...") if expected_state else "<missing>",
                request.session.session_key,
            )
            return HttpResponseRedirect(f"{settings.FRONTEND_BASE_URL}/?login_error=1")

        request.session.pop("gh_oauth_state", None)

        try:
            token_resp = requests.post(
                GITHUB_TOKEN_URL,
                headers={"Accept": "application/json"},
                data={
                    "client_id": settings.GITHUB_CLIENT_ID,
                    "client_secret": settings.GITHUB_CLIENT_SECRET,
                    "code": code,
                    "redirect_uri": settings.GITHUB_OAUTH_REDIRECT_URI,
                    "state": state,
                },
                timeout=15,
            )
            token_resp.raise_for_status()
            token_data = token_resp.json()
            access_token = token_data.get("access_token")
            scopes = token_data.get("scope", "")
            if not access_token:
                logger.warning("GitHub OAuth: no access_token in response")
                return HttpResponseRedirect(f"{settings.FRONTEND_BASE_URL}/?login_error=1")

            # The "repo" scope is required to clone private repos (and to
            # exchange tokens against the user/repos endpoint with private
            # results). If GitHub silently downgraded the scope, redirect
            # the user back to retry rather than persisting a useless token.
            granted_scopes = {s.strip() for s in (scopes or "").split(",") if s.strip()}
            if "repo" not in granted_scopes:
                logger.warning("GitHub OAuth missing 'repo' scope; got %s", scopes)
                return HttpResponseRedirect(
                    f"{settings.FRONTEND_BASE_URL}/?login_error=missing_scope"
                )

            user_resp = requests.get(
                GITHUB_USER_URL,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github+json",
                },
                timeout=15,
            )
            user_resp.raise_for_status()
            gh = user_resp.json()
            gh_id = gh["id"]
            gh_login = gh.get("login", "")
            gh_avatar = gh.get("avatar_url", "") or ""

            # `gh__` (double underscore) reduces the chance of colliding
            # with a hand-created username. Django's User.username max_length
            # is 150, and User.first_name is 150 in 4.2 — match that.
            user, _ = User.objects.get_or_create(
                username=f"gh__{gh_id}",
                defaults={"first_name": (gh_login or "")[:150]},
            )

            GitHubIdentity.objects.update_or_create(
                user=user,
                defaults={
                    "github_user_id": gh_id,
                    "login": gh_login,
                    "avatar_url": gh_avatar,
                    "access_token_enc": encrypt(access_token),
                    "scopes": scopes,
                    "needs_reauth": False,
                },
            )
        except IntegrityError:
            logger.exception("GitHub OAuth integrity error")
            return HttpResponseRedirect(f"{settings.FRONTEND_BASE_URL}/?login_error=1")
        except Exception:
            logger.exception("GitHub OAuth callback error")
            return HttpResponseRedirect(f"{settings.FRONTEND_BASE_URL}/?login_error=1")

        auth_login(request, user)
        return HttpResponseRedirect(settings.FRONTEND_BASE_URL)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            identity = request.user.github_identity
        except GitHubIdentity.DoesNotExist:
            return Response(
                {
                    "id": request.user.id,
                    "login": request.user.username,
                    "avatar_url": "",
                    "needs_reauth": False,
                }
            )
        return Response(
            {
                "id": request.user.id,
                "login": identity.login,
                "avatar_url": identity.avatar_url,
                "needs_reauth": identity.needs_reauth,
            }
        )


@method_decorator(csrf_exempt, name="dispatch")
class LogoutView(APIView):
    """Sign the user out.

    CSRF-exempt because the worst case for a CSRF attack on logout is a
    forced sign-out (DoS), not credential theft. Logout still requires a
    valid session cookie via `IsAuthenticated`. Without the exemption a
    stale `csrftoken` cookie can wedge the frontend into an unrecoverable
    "can't log in / can't log out" state.
    """

    authentication_classes = [_CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        auth_logout(request)
        return Response(status=204)


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response(status=204)


class GithubReposView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Cap `q` length to keep cache keys bounded and avoid wasting upstream
        # request budget on absurd inputs. The colon would otherwise alias
        # different users' cache keys (`gh_repos:{user_id}:{page}:{q}`).
        q_raw = (request.query_params.get("q") or "").strip()[:100]
        q_cache_key = q_raw.replace(":", "_")
        q = q_raw
        try:
            page = int(request.query_params.get("page", 1))
        except ValueError:
            page = 1
        page = max(1, min(10, page))

        identity, err = get_identity_or_reauth(request.user)
        if err is not None:
            return err

        cache_key = f"gh_repos:{request.user.id}:{page}:{q_cache_key}"
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        token, err = decrypt_token_or_reauth(identity)
        if err is not None:
            return err

        params = {
            "affiliation": "owner,collaborator,organization_member",
            "sort": "pushed",
            "direction": "desc",
            "per_page": 50,
            "page": page,
        }
        result = github_get(token, GITHUB_REPOS_URL, params=params)
        if isinstance(result, tuple):
            key, status = result[0], result[1]
            r = Response({"error": key}, status=status)
            if key == "rate_limited" and len(result) > 2 and result[2]:
                r["Retry-After"] = result[2]
            return r
        resp = result

        if resp.status_code == 401:
            identity.needs_reauth = True
            identity.save(update_fields=["needs_reauth", "updated_at"])
            return Response({"needs_reauth": True}, status=401)

        repos = resp.json() or []
        if q:
            ql = q.lower()
            repos = [r for r in repos if ql in (r.get("full_name") or "").lower()]

        trimmed = [
            {
                "id": r["id"],
                "name": r["name"],
                "full_name": r["full_name"],
                "html_url": r["html_url"],
                "private": r.get("private", False),
                "pushed_at": r.get("pushed_at"),
                "default_branch": r.get("default_branch", "main"),
            }
            for r in repos
        ]

        cache.set(cache_key, trimmed, 300)
        return Response(trimmed)
