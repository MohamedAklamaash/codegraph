import uuid

from django.conf import settings
from django.db import models


class RepoStatus(models.TextChoices):
    # Mirror these keys in frontend/src/constants/repoStatus.ts when adding states.
    PENDING = "pending", "Pending"
    CLONING = "cloning", "Cloning"
    PARSING = "parsing", "Parsing"
    EMBEDDING = "embedding", "Embedding"
    READY = "ready", "Ready"
    FAILED = "failed", "Failed"


class Repository(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    url = models.URLField(unique=True)
    name = models.CharField(max_length=255)
    status = models.CharField(
        max_length=20,
        choices=RepoStatus.choices,
        default=RepoStatus.PENDING,
    )
    status_message = models.TextField(blank=True)
    first_ingested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    is_private = models.BooleanField(null=True, default=None)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class RepositoryAccess(models.Model):
    ROLE_CHOICES = [("owner", "owner"), ("member", "member")]
    SOURCE_CHOICES = [("github", "github"), ("public_url", "public_url")]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="repo_accesses",
    )
    repository = models.ForeignKey(
        Repository,
        on_delete=models.CASCADE,
        related_name="accesses",
    )
    role = models.CharField(max_length=16, choices=ROLE_CHOICES, default="owner")
    source = models.CharField(max_length=16, choices=SOURCE_CHOICES, default="public_url")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (("user", "repository"),)
