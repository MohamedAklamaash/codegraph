from django.db import models
from pgvector.django import VectorField

from apps.graph.models import FunctionNode

from .client import EMBEDDING_DIM


class FunctionEmbedding(models.Model):
    function = models.OneToOneField(FunctionNode, on_delete=models.CASCADE, related_name="embedding")
    vector = VectorField(dimensions=EMBEDDING_DIM)

    def __str__(self):
        return f"Embedding({self.function})"
