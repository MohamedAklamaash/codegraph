from django.db import migrations, models
import uuid

class Migration(migrations.Migration):
    initial = True
    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Repository",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)),
                ("url", models.URLField(unique=True)),
                ("name", models.CharField(max_length=255)),
                ("status", models.CharField(
                    max_length=20,
                    choices=[
                        ("pending", "Pending"), ("cloning", "Cloning"), ("parsing", "Parsing"),
                        ("graphing", "Graphing"), ("embedding", "Embedding"),
                        ("ready", "Ready"), ("failed", "Failed"),
                    ],
                    default="pending",
                )),
                ("status_message", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
