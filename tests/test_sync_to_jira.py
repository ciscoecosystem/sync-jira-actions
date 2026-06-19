import json
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest


@pytest.fixture
def mock_environment(tmp_path, monkeypatch):
    event_file = tmp_path / 'event.json'
    monkeypatch.setenv('GITHUB_REPOSITORY', 'espressif/esp-idf')
    monkeypatch.setenv('GITHUB_TOKEN', 'fake-token')
    monkeypatch.setenv('GITHUB_EVENT_PATH', str(event_file))
    monkeypatch.setenv('JIRA_URL', 'https://jira.example.com')
    monkeypatch.setenv('JIRA_USER', 'user')
    monkeypatch.setenv('JIRA_PASS', 'pass')
    return event_file


@pytest.fixture
def sync_to_jira_main(monkeypatch):
    monkeypatch.setattr('github.Github', MagicMock())
    monkeypatch.setattr('jira.JIRA', MagicMock())

    # Import the main function dynamically after applying mocks
    from sync_jira_actions.sync_to_jira import main as dynamically_imported_main

    return dynamically_imported_main


@pytest.fixture
def mock_jira_client():
    """Patches _JIRA in sync_to_jira to avoid real Jira connections."""
    with patch('sync_jira_actions.sync_to_jira._JIRA') as mock_cls:
        mock_cls.return_value = MagicMock()
        yield mock_cls.return_value


def test_not_running_in_github_action_context(capsys, sync_to_jira_main, monkeypatch):
    monkeypatch.delenv('GITHUB_REPOSITORY', raising=False)
    sync_to_jira_main()
    captured = capsys.readouterr()
    assert 'Not running in GitHub action context, nothing to do' in captured.out


def test_no_jira_url_configured(capsys, sync_to_jira_main, monkeypatch):
    monkeypatch.setenv('GITHUB_REPOSITORY', 'other/repo')
    monkeypatch.delenv('JIRA_URL', raising=False)
    sync_to_jira_main()
    captured = capsys.readouterr()
    assert 'No Jira URL configured, nothing to do' in captured.out


def test_handle_issue_opened_event(mock_environment, sync_to_jira_main, monkeypatch):
    event_data = {
        'action': 'opened',
        'issue': {
            'number': 1,
            'title': 'Test issue',
            'body': 'This is a test issue',
            'user': {'login': 'testuser'},
            'labels': [],
            'html_url': 'https://github.com/espressif/esp-idf/issues/1',
        },
    }
    mock_environment.write_text(json.dumps(event_data))
    monkeypatch.setenv('GITHUB_EVENT_NAME', 'issues')

    with patch('sync_jira_actions.sync_to_jira.handle_issue_opened') as mock_handle_issue_opened:
        sync_to_jira_main()
        mock_handle_issue_opened.assert_called_once()


# ── Token auth ────────────────────────────────────────────────────────────────

def test_token_auth(mock_environment, sync_to_jira_main, monkeypatch):
    event_data = {
        'action': 'opened',
        'issue': {
            'number': 1, 'title': 'Test', 'body': 'body',
            'user': {'login': 'user'}, 'labels': [],
            'html_url': 'https://github.com/espressif/esp-idf/issues/1',
        },
    }
    mock_environment.write_text(json.dumps(event_data))
    monkeypatch.setenv('GITHUB_EVENT_NAME', 'issues')
    monkeypatch.setenv('JIRA_PASS', 'token:my-api-token')

    with patch('sync_jira_actions.sync_to_jira.handle_issue_opened'):
        with patch('sync_jira_actions.sync_to_jira._JIRA') as mock_jira_cls:
            sync_to_jira_main()
    mock_jira_cls.assert_called_once_with('https://jira.example.com', token_auth='my-api-token')


# ── Cron job mode ─────────────────────────────────────────────────────────────

def test_cron_job_mode(mock_environment, mock_jira_client, sync_to_jira_main, monkeypatch):
    monkeypatch.setenv('GITHUB_EVENT_NAME', 'schedule')
    monkeypatch.setenv('INPUT_CRON_JOB', 'true')
    mock_environment.write_text(json.dumps({}))

    with patch('sync_jira_actions.sync_to_jira.sync_remain_prs') as mock_sync:
        sync_to_jira_main()
    mock_sync.assert_called_once()


# ── workflow_dispatch ─────────────────────────────────────────────────────────

def test_workflow_dispatch_no_inputs(mock_environment, mock_jira_client, sync_to_jira_main, monkeypatch, capsys):
    monkeypatch.setenv('GITHUB_EVENT_NAME', 'workflow_dispatch')
    mock_environment.write_text(json.dumps({'action': 'workflow_dispatch'}))

    sync_to_jira_main()
    assert 'without correct inputs' in capsys.readouterr().out


def test_workflow_dispatch_wrong_action(mock_environment, mock_jira_client, sync_to_jira_main, monkeypatch, capsys):
    monkeypatch.setenv('GITHUB_EVENT_NAME', 'workflow_dispatch')
    mock_environment.write_text(json.dumps({'inputs': {'action': 'other-action', 'issue-numbers': '1'}}))

    sync_to_jira_main()
    assert 'mirror-issues' in capsys.readouterr().out


def test_workflow_dispatch_no_issue_numbers(mock_environment, mock_jira_client, sync_to_jira_main, monkeypatch, capsys):
    monkeypatch.setenv('GITHUB_EVENT_NAME', 'workflow_dispatch')
    mock_environment.write_text(json.dumps({'inputs': {'action': 'mirror-issues'}}))

    sync_to_jira_main()
    assert 'issue-numbers' in capsys.readouterr().out


def test_workflow_dispatch_mirror_issues(mock_environment, mock_jira_client, sync_to_jira_main, monkeypatch):
    monkeypatch.setenv('GITHUB_EVENT_NAME', 'workflow_dispatch')
    mock_environment.write_text(json.dumps({'inputs': {'action': 'mirror-issues', 'issue-numbers': '1 2'}}))

    with patch('sync_jira_actions.sync_to_jira.sync_issues_manually') as mock_sync:
        sync_to_jira_main()
    mock_sync.assert_called_once()


# ── pull_request event ────────────────────────────────────────────────────────

def test_pull_request_event(mock_environment, mock_jira_client, sync_to_jira_main, monkeypatch):
    event_data = {
        'action': 'opened',
        'pull_request': {
            'number': 10, 'title': 'My PR', 'body': 'PR body',
            'user': {'login': 'contributor'}, 'labels': [],
            'html_url': 'https://github.com/espressif/esp-idf/pull/10',
            'state': 'open',
        },
    }
    mock_environment.write_text(json.dumps(event_data))
    monkeypatch.setenv('GITHUB_EVENT_NAME', 'pull_request')

    with (
        patch('sync_jira_actions.sync_to_jira.handle_issue_opened'),
        patch('sync_jira_actions.sync_to_jira.find_jira_issue', return_value=None),
        patch('sync_jira_actions.sync_to_jira.Github') as mock_gh,
    ):
        mock_gh.return_value.get_repo.return_value.has_in_collaborators.return_value = False
        sync_to_jira_main()


# ── pull_request_target event ─────────────────────────────────────────────────

def test_pull_request_target_event(mock_environment, mock_jira_client, sync_to_jira_main, monkeypatch):
    issue_data = {
        'number': 11, 'title': 'External PR', 'body': 'body',
        'user': {'login': 'external'}, 'labels': [],
        'html_url': 'https://github.com/espressif/esp-idf/issues/11',
        'state': 'open',
    }
    event_data = {
        'action': 'opened',
        'pull_request': {
            'number': 11,
            '_links': {'issue': {'href': 'https://api.github.com/repos/espressif/esp-idf/issues/11'}},
        },
    }
    mock_environment.write_text(json.dumps(event_data))
    monkeypatch.setenv('GITHUB_EVENT_NAME', 'pull_request_target')

    with (
        patch('requests.get') as mock_get,
        patch('sync_jira_actions.sync_to_jira.handle_issue_opened'),
        patch('sync_jira_actions.sync_to_jira.find_jira_issue', return_value=None),
        patch('sync_jira_actions.sync_to_jira.Github') as mock_gh,
    ):
        mock_get.return_value.json.return_value = issue_data
        mock_gh.return_value.get_repo.return_value.has_in_collaborators.return_value = False
        sync_to_jira_main()


# ── workflow_run event ────────────────────────────────────────────────────────

def test_workflow_run_pull_request_review(mock_environment, mock_jira_client, sync_to_jira_main, monkeypatch):
    issue_data = {
        'number': 12, 'title': 'PR', 'body': 'body',
        'user': {'login': 'user'}, 'labels': [],
        'html_url': 'https://github.com/espressif/esp-idf/issues/12',
        'state': 'open', 'pull_request': True,
    }
    event_data = {
        'action': 'completed',
        'workflow_run': {'event': 'pull_request_review'},
    }
    mock_environment.write_text(json.dumps(event_data))
    monkeypatch.setenv('GITHUB_EVENT_NAME', 'workflow_run')

    with (
        patch('sync_jira_actions.sync_to_jira.get_recently_updated_pr_url', return_value='https://api.github.com/repos/r/r/issues/12'),
        patch('requests.get') as mock_get,
        patch('sync_jira_actions.sync_to_jira.find_jira_issue', return_value=None),
        patch('sync_jira_actions.sync_to_jira.check_pr_approval_and_move'),
        patch('sync_jira_actions.sync_to_jira.Github') as mock_gh,
    ):
        mock_get.return_value.json.return_value = issue_data
        mock_gh.return_value.get_repo.return_value.has_in_collaborators.return_value = False
        sync_to_jira_main()


# ── Collaborator skip ─────────────────────────────────────────────────────────

def test_pr_from_collaborator_skipped(mock_environment, mock_jira_client, sync_to_jira_main, monkeypatch, capsys):
    event_data = {
        'action': 'opened',
        'issue': {
            'number': 20, 'title': 'Collab PR', 'body': 'body',
            'user': {'login': 'collaborator'}, 'labels': [],
            'html_url': 'https://github.com/espressif/esp-idf/pull/20',
            'state': 'open', 'pull_request': True,
        },
    }
    mock_environment.write_text(json.dumps(event_data))
    monkeypatch.setenv('GITHUB_EVENT_NAME', 'issues')

    with (
        patch('sync_jira_actions.sync_to_jira.handle_issue_opened') as mock_handler,
        patch('sync_jira_actions.sync_to_jira.Github') as mock_gh,
    ):
        mock_gh.return_value.get_repo.return_value.has_in_collaborators.return_value = True
        sync_to_jira_main()
    mock_handler.assert_not_called()
    assert 'collaborator' in capsys.readouterr().out


# ── sync label skip ───────────────────────────────────────────────────────────

def test_issue_without_sync_label_skipped(mock_environment, mock_jira_client, sync_to_jira_main, monkeypatch, capsys):
    event_data = {
        'action': 'opened',
        'issue': {
            'number': 21, 'title': 'Issue', 'body': 'body',
            'user': {'login': 'user'}, 'labels': [],
            'html_url': 'https://github.com/espressif/esp-idf/issues/21',
            'state': 'open',
        },
    }
    mock_environment.write_text(json.dumps(event_data))
    monkeypatch.setenv('GITHUB_EVENT_NAME', 'issues')
    monkeypatch.setenv('INPUT_SYNC_LABEL', 'sync-to-jira')

    with (
        patch('sync_jira_actions.sync_to_jira.handle_issue_opened') as mock_handler,
        patch('sync_jira_actions.sync_to_jira.Github') as mock_gh,
    ):
        mock_gh.return_value.get_repo.return_value.has_in_collaborators.return_value = False
        sync_to_jira_main()
    mock_handler.assert_not_called()


# ── no handler ────────────────────────────────────────────────────────────────

def test_no_handler_for_event(mock_environment, mock_jira_client, sync_to_jira_main, monkeypatch, capsys):
    event_data = {
        'action': 'ping',
        'issue': {
            'number': 30, 'title': 'Test', 'body': 'body',
            'user': {'login': 'user'}, 'labels': [],
            'html_url': 'https://github.com/espressif/esp-idf/issues/30', 'state': 'open',
        },
    }
    mock_environment.write_text(json.dumps(event_data))
    monkeypatch.setenv('GITHUB_EVENT_NAME', 'unknown_event')

    with patch('sync_jira_actions.sync_to_jira.Github') as mock_gh:
        mock_gh.return_value.get_repo.return_value.has_in_collaborators.return_value = False
        sync_to_jira_main()
    assert 'No handler for event' in capsys.readouterr().out


def test_no_handler_for_action(mock_environment, mock_jira_client, sync_to_jira_main, monkeypatch, capsys):
    event_data = {
        'action': 'unknown_action',
        'issue': {
            'number': 31, 'title': 'Test', 'body': 'body',
            'user': {'login': 'user'}, 'labels': [],
            'html_url': 'https://github.com/espressif/esp-idf/issues/31', 'state': 'open',
        },
    }
    mock_environment.write_text(json.dumps(event_data))
    monkeypatch.setenv('GITHUB_EVENT_NAME', 'issues')

    with patch('sync_jira_actions.sync_to_jira.Github') as mock_gh:
        mock_gh.return_value.get_repo.return_value.has_in_collaborators.return_value = False
        sync_to_jira_main()
    assert "No handler" in capsys.readouterr().out


# ── issue_comment event ───────────────────────────────────────────────────────

def test_issue_comment_created(mock_environment, mock_jira_client, sync_to_jira_main, monkeypatch):
    event_data = {
        'action': 'created',
        'issue': {
            'number': 40, 'title': 'Issue', 'body': 'body',
            'user': {'login': 'user'}, 'labels': [],
            'html_url': 'https://github.com/espressif/esp-idf/issues/40', 'state': 'open',
        },
        'comment': {'body': 'A comment', 'html_url': 'https://url', 'user': {'login': 'commenter'}},
    }
    mock_environment.write_text(json.dumps(event_data))
    monkeypatch.setenv('GITHUB_EVENT_NAME', 'issue_comment')

    with (
        patch('sync_jira_actions.sync_to_jira.handle_comment_created') as mock_handler,
        patch('sync_jira_actions.sync_to_jira.Github') as mock_gh,
    ):
        mock_gh.return_value.get_repo.return_value.has_in_collaborators.return_value = False
        sync_to_jira_main()
    mock_handler.assert_called_once()


