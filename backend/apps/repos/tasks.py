import os
import shutil
import git
from celery import shared_task
from django.conf import settings
from .models import Repository

def _set_status(repo, status, msg=""):
    repo.status = status
    repo.status_message = msg
    repo.save(update_fields=["status", "status_message"])

@shared_task
def ingest_repository(repo_id):
    from apps.parser.tasks import parse_repository
    from apps.graph.tasks import build_graph
    from apps.embeddings.tasks import generate_embeddings

    repo = Repository.objects.get(id=repo_id)
    repo_path = os.path.join(settings.REPOS_DIR, str(repo_id))

    try:
        # Step 1: Clone
        _set_status(repo, "cloning", "Cloning repo...")
        if os.path.exists(repo_path):
            shutil.rmtree(repo_path)
        git.Repo.clone_from(repo.url, repo_path, depth=1)

        # Step 2: Parse
        _set_status(repo, "parsing", "Parsing files...")
        parse_repository(repo_id, repo_path)

        # Step 3: Graph
        _set_status(repo, "graphing", "Building graph...")
        build_graph(repo_id)

        # Step 4: Embeddings
        _set_status(repo, "embedding", "Generating embeddings...")
        generate_embeddings(repo_id)

        _set_status(repo, "ready", "Done")

    except Exception as e:
        _set_status(repo, "failed", str(e))
        raise
