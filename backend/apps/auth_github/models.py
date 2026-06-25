from django.conf import settings
from django.db import models


class GitHubIdentity(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="github_identity",
    )
    github_user_id = models.BigIntegerField(unique=True, db_index=True)
    login = models.CharField(max_length=255)
    avatar_url = models.URLField(blank=True, default="")
    access_token_enc = models.TextField()
    scopes = models.TextField(blank=True, default="")
    needs_reauth = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"gh:{self.login}"
