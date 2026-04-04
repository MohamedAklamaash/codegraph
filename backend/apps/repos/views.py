from rest_framework.views import APIView
from rest_framework.response import Response
from .models import Repository
from .serializers import RepositorySerializer
from .tasks import ingest_repository

class RepositoryView(APIView):
    def post(self, request):
        url = request.data.get("url", "").strip().rstrip("/")
        if not url:
            return Response({"error": "url required"}, status=400)

        name = url.split("/")[-1].replace(".git", "")
        repo, created = Repository.objects.get_or_create(url=url, defaults={"name": name})

        if not created:
            # Re-analyze: reset status
            repo.status = "pending"
            repo.status_message = ""
            repo.save(update_fields=["status", "status_message"])

        ingest_repository.delay(str(repo.id))
        return Response(RepositorySerializer(repo).data, status=201 if created else 200)

    def get(self, request, repo_id=None):
        if repo_id:
            repo = Repository.objects.get(id=repo_id)
            return Response(RepositorySerializer(repo).data)
        repos = Repository.objects.all().order_by("-created_at")
        return Response(RepositorySerializer(repos, many=True).data)
