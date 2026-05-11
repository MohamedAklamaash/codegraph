"""Tests for apps.repos.tasks._redact (item 2)."""
from apps.repos.tasks import _redact

SYNTHETIC_TOKEN = "ghp_TESTSyntheticTokenABCDEF1234567890XYZ"


class TestRedact:
    def test_removes_raw_token_from_message(self):
        msg = f"git clone failed: stderr contained {SYNTHETIC_TOKEN} oops"
        out = _redact(msg, SYNTHETIC_TOKEN)
        assert SYNTHETIC_TOKEN not in out
        assert "***" in out

    def test_strips_x_access_token_url_form(self):
        url = f"https://x-access-token:{SYNTHETIC_TOKEN}@github.com/x/y.git"
        msg = f"fatal: could not clone {url} -- access denied"
        out = _redact(msg, SYNTHETIC_TOKEN)
        assert SYNTHETIC_TOKEN not in out
        assert "x-access-token" not in out
        assert "https://***@github.com/x/y.git" in out

    def test_strips_generic_userinfo_url_even_without_known_token(self):
        msg = "Cloning into 'repo'... fatal: https://someuser:somepass@host.example.org/x.git failed"
        out = _redact(msg, token=None)
        assert "somepass" not in out
        assert "someuser" not in out
        assert "https://***@host.example.org/x.git" in out

    def test_empty_message_returns_empty_string(self):
        assert _redact("", SYNTHETIC_TOKEN) == ""
        assert _redact(None, SYNTHETIC_TOKEN) == ""

    def test_token_none_leaves_plain_text_alone(self):
        msg = "no secrets here, just a normal error"
        assert _redact(msg, None) == msg

    def test_does_not_partial_match_other_strings(self):
        # The token only redacts its own substring; unrelated text passes through.
        msg = "branch main not found"
        out = _redact(msg, SYNTHETIC_TOKEN)
        assert out == msg

    def test_redacts_git_command_error_attributes_in_place(self):
        """`_redact(GitCommandError)` should redact .command, .stdout, .stderr
        AND fold them into the returned string. This guards against Celery
        serializing the original exception attributes into a task result."""

        class _FakeGitCommandError(Exception):
            def __init__(self):
                super().__init__("clone failed")
                self.command = [
                    "git", "clone",
                    f"https://x-access-token:{SYNTHETIC_TOKEN}@github.com/x/y.git",
                ]
                self.stdout = b""
                self.stderr = (
                    f"fatal: could not read Username for "
                    f"https://x-access-token:{SYNTHETIC_TOKEN}@github.com"
                )

        e = _FakeGitCommandError()
        out = _redact(e, SYNTHETIC_TOKEN)

        # Returned text is clean of token AND of x-access-token@host blob.
        assert SYNTHETIC_TOKEN not in out
        assert "x-access-token" not in out
        # Mutated-in-place attributes are also clean for downstream serializers.
        assert SYNTHETIC_TOKEN not in str(e.stderr)
        assert SYNTHETIC_TOKEN not in str(e.command)
        assert "x-access-token" not in str(e.stderr)
