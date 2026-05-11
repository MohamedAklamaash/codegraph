"""Tests for apps.auth_github.crypto (item 1)."""
import pytest
from cryptography.fernet import InvalidToken
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings

from apps.auth_github.crypto import decrypt, encrypt


class TestCryptoRoundTrip:
    def test_encrypt_decrypt_round_trip(self):
        plain = "ghp_AbCdEf123456789_synthetic_token"
        token = encrypt(plain)
        assert token != plain
        assert decrypt(token) == plain

    def test_encrypt_round_trip_unicode(self):
        plain = "tokén-with-üñîçødé"
        assert decrypt(encrypt(plain)) == plain

    def test_decrypt_tampered_ciphertext_raises(self):
        token = encrypt("synthetic_token_for_tamper_test")
        # flip a byte near the end of the ciphertext
        tampered = token[:-3] + ("A" if token[-3:] != "AAA" else "B") + token[-2:]
        with pytest.raises(InvalidToken):
            decrypt(tampered)

    def test_decrypt_garbage_raises(self):
        with pytest.raises(Exception):
            decrypt("not-a-valid-fernet-token")

    def test_missing_enc_key_raises_improperly_configured(self):
        with override_settings(GITHUB_TOKEN_ENC_KEY=""):
            with pytest.raises(ImproperlyConfigured):
                encrypt("anything")
            with pytest.raises(ImproperlyConfigured):
                decrypt("anything")

    def test_none_enc_key_raises_improperly_configured(self):
        with override_settings(GITHUB_TOKEN_ENC_KEY=None):
            with pytest.raises(ImproperlyConfigured):
                encrypt("anything")
