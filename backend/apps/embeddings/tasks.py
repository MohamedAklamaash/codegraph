from apps.graph.models import FunctionNode
from apps.repos.models import Repository

from .client import embed_texts
from .models import FunctionEmbedding


def generate_embeddings(repo_id):
    repo = Repository.objects.get(id=repo_id)
    FunctionEmbedding.objects.filter(function__repository=repo).delete()

    functions = list(FunctionNode.objects.filter(repository=repo))
    if not functions:
        return

    texts = [f"{fn.name}\n{fn.source}" for fn in functions]
    vectors = embed_texts(texts)

    FunctionEmbedding.objects.bulk_create([
        FunctionEmbedding(function=fn, vector=vec)
        for fn, vec in zip(functions, vectors)
    ])
