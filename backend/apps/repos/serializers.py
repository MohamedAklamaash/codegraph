from rest_framework import serializers
from .models import Repository

class RepositorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Repository
        fields = ["id", "url", "name", "status", "status_message", "created_at"]
        read_only_fields = ["id", "name", "status", "status_message", "created_at"]
