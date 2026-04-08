from django.db import migrations, models
import django.db.models.deletion
import django.contrib.postgres.fields

class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ("repos", "0001_initial"),
        ("files", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="FunctionNode",
            fields=[
                ("id", models.BigAutoField(primary_key=True)),
                ("repository", models.ForeignKey(
                    "repos.Repository", on_delete=django.db.models.deletion.CASCADE, related_name="functions"
                )),
                ("file", models.ForeignKey(
                    "files.RepoFile", on_delete=django.db.models.deletion.CASCADE, related_name="functions"
                )),
                ("name", models.CharField(max_length=255)),
                ("start_line", models.IntegerField()),
                ("end_line", models.IntegerField()),
                ("source", models.TextField()),
                ("summary", models.TextField(blank=True)),
                ("calls", django.contrib.postgres.fields.ArrayField(
                    base_field=models.CharField(max_length=255), default=list
                )),
            ],
            options={"unique_together": {("repository", "file", "name", "start_line")}},
        ),
        migrations.CreateModel(
            name="FunctionEdge",
            fields=[
                ("id", models.BigAutoField(primary_key=True)),
                ("repository", models.ForeignKey(
                    "repos.Repository", on_delete=django.db.models.deletion.CASCADE, related_name="edges"
                )),
                ("source", models.ForeignKey(
                    "graph.FunctionNode", on_delete=django.db.models.deletion.CASCADE, related_name="outgoing"
                )),
                ("target", models.ForeignKey(
                    "graph.FunctionNode", on_delete=django.db.models.deletion.CASCADE, related_name="incoming"
                )),
                ("edge_type", models.CharField(
                    max_length=20, choices=[("CALLS", "Calls"), ("IMPORTS", "Imports")]
                )),
            ],
            options={"unique_together": {("source", "target", "edge_type")}},
        ),
    ]
