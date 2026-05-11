from rest_framework.response import Response

from .models import Repository


def normalize_or_400(raw_url, normalize_fn):
    try:
        return normalize_fn(raw_url), None
    except ValueError as e:
        return None, Response({"error": "invalid_url", "detail": str(e)}, status=400)


def get_user_repo_or_404_response(user, repo_id):
    repo = Repository.objects.filter(id=repo_id, accesses__user=user).first()
    if not repo:
        return None, Response({"error": "not found"}, status=404)
    return repo, None
