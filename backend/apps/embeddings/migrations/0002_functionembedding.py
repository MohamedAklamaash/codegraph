from django.db import migrations, models
import django.db.models.deletion
from pgvector.django import VectorField

class Migration(migrations.Migration):
    dependencies = [
        ("embeddings", "0001_enable_pgvector"),
        ("graph", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="FunctionEmbedding",
            fields=[
                ("id", models.BigAutoField(primary_key=True)),
                ("function", models.OneToOneField(
                    "graph.FunctionNode", on_delete=django.db.models.deletion.CASCADE, related_name="embedding"
                )),
                ("vector", VectorField(dimensions=3072)),
            ],
        ),
    ]
