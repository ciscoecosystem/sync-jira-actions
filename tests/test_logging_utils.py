from sync_jira_actions.logging_utils import is_debug, redact


# ── is_debug ──────────────────────────────────────────────────────────────────

def test_is_debug_off_by_default(monkeypatch):
    monkeypatch.delenv('ACTIONS_RUNNER_DEBUG', raising=False)
    assert is_debug() is False


def test_is_debug_on_when_env_set(monkeypatch):
    monkeypatch.setenv('ACTIONS_RUNNER_DEBUG', 'true')
    assert is_debug() is True


def test_is_debug_off_for_other_values(monkeypatch):
    monkeypatch.setenv('ACTIONS_RUNNER_DEBUG', '1')
    assert is_debug() is False
    monkeypatch.setenv('ACTIONS_RUNNER_DEBUG', 'True')
    assert is_debug() is False


# ── redact ────────────────────────────────────────────────────────────────────

def test_redact_github_pat():
    assert redact('token: ghp_abc123XYZ') == 'token=[REDACTED]'


def test_redact_github_fine_grained_token():
    result = redact('Authorization: ghu_ABCDEFGHIJKLMNOP')
    assert 'ghu_' not in result
    assert '[REDACTED_GH_TOKEN]' in result


def test_redact_github_app_token():
    result = redact('Bearer ghs_ABCDEF123456')
    assert 'ghs_' not in result
    assert '[REDACTED_GH_TOKEN]' in result


def test_redact_aws_access_key():
    result = redact('Found credential AKIAIOSFODNN7EXAMPLE in the config file')
    assert 'AKIAIOSFODNN7EXAMPLE' not in result
    assert '[REDACTED_AWS_KEY]' in result


def test_redact_private_key_block():
    text = '-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA\n-----END RSA PRIVATE KEY-----'
    result = redact(text)
    assert 'MIIEowIBAAKCAQEA' not in result
    assert '[REDACTED_PRIVATE_KEY]' in result


def test_redact_generic_token_assignment():
    result = redact('token=supersecret123')
    assert 'supersecret123' not in result
    assert '[REDACTED]' in result


def test_redact_generic_secret_colon():
    result = redact('secret: abc123xyz')
    assert 'abc123xyz' not in result
    assert '[REDACTED]' in result


def test_redact_safe_text_unchanged():
    text = 'Issue #42 synced to JIRA-123'
    assert redact(text) == text


def test_redact_empty_string():
    assert redact('') == ''


def test_redact_none():
    assert redact(None) is None
