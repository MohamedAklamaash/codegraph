from apps.graph.models import FunctionNode
from apps.repos.models import Repository
from .models import FunctionEmbedding
from .client import embed_texts

BATCH_SIZE = 100

def generate_embeddings(repo_id):
    repo = Repository.objects.get(id=repo_id)
    FunctionEmbedding.objects.filter(function__repository=repo).delete()

    functions = list(FunctionNode.objects.filter(repository=repo))
    for i in range(0, len(functions), BATCH_SIZE):
        batch = functions[i:i + BATCH_SIZE]
        texts = [f"{fn.name}\n{fn.source}" for fn in batch]
        vectors = embed_texts(texts)
        FunctionEmbedding.objects.bulk_create([
            FunctionEmbedding(function=fn, vector=vec)
            for fn, vec in zip(batch, vectors)
        ])
