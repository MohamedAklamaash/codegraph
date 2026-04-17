import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ("repos", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="RepoFile",
            fields=[
                ("id", models.BigAutoField(primary_key=True)),
                ("repository", models.ForeignKey(
                    "repos.Repository", on_delete=django.db.models.deletion.CASCADE, related_name="files"
                )),
                ("path", models.CharField(max_length=1024)),
                ("language", models.CharField(max_length=50, blank=True)),
            ],
            options={"unique_together": {("repository", "path")}},
        ),
    ]
