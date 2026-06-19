import subprocess
from unittest.mock import MagicMock, call
from unittest.mock import patch

import pytest
from jira import JIRAError


@pytest.fixture(autouse=True)
def setup_env(monkeypatch):
    monkeypatch.setenv('GITHUB_TOKEN', 'fake-token')
    monkeypatch.setenv('GITHUB_REPOSITORY', 'fake/repo')
    monkeypatch.setenv('JIRA_PROJECT', 'FAKE')


@pytest.fixture(scope='module')
def github_client_mock():
    with patch('github.Github') as MockGithub:
        mock_github = MockGithub.return_value
        mock_repo = MagicMock()
        mock_github.get_repo.return_value = mock_repo
        yield mock_github, mock_repo


# Correct fixture to mock JIRA client
@pytest.fixture(scope='module')
def mock_jira_client():
    with patch('jira.JIRA') as MockJIRA:
        mock_jira = MockJIRA.return_value
        yield mock_jira


@pytest.fixture
def sync_issue_module(github_client_mock):
    import sys
    from importlib import reload
    sys.path.insert(0, 'sync_jira_actions')  # Ensure bare-name modules (e.g. logging_utils) are importable on reload
    from sync_jira_actions import sync_issue

    reload(sync_issue)  # Reload to apply the mocked Github client
    return sync_issue


# Example test function
def test_handle_issue_opened_creates_jira_issue(sync_issue_module, github_client_mock):
    _, mock_repo = github_client_mock
    mock_jira_client = MagicMock()
    mock_event = {
        'issue': {
            'number': 123,
            'title': 'New Issue',
            'body': 'Issue description here.',
            'user': {'login': 'user123'},
            'labels': [],
            'html_url': 'https://github.com/user/repo/issues/123',
            'state': 'open',
        },
        'repository': {
            'full_name': 'fake/repo',
            'name': 'repo',
            'owner': {'login': 'fake'},
        },
    }

    with (
        patch('sync_jira_actions.sync_issue._find_jira_issue', return_value=None) as mock_find_jira_issue,
        patch('sync_jira_actions.sync_issue._create_jira_issue') as mock_create_jira_issue,
    ):
        sync_issue_module.handle_issue_opened(mock_jira_client, mock_event)

        mock_find_jira_issue.assert_called_once()
        mock_create_jira_issue.assert_called_once()


def test_handle_issue_labeled_adds_label(sync_issue_module, github_client_mock, mock_jira_client):
    # Setup
    mock_github, mock_repo = github_client_mock

    mock_event = {
        'issue': {
            'number': 123,
            'title': 'Issue for Labeling',
            'body': 'Label me!',
            'user': {'login': 'user456'},
            'labels': [{'name': 'bug'}],
            'html_url': 'https://github.com/user/repo/issues/123',
            'state': 'open',
        },
        'label': {'name': 'bug'},
        'repository': {
            'full_name': 'fake/repo',
            'name': 'repo',
            'owner': {'login': 'fake'},
        },
    }

    # Adjusting the mock to behave more like a list that can be appended to
    mock_jira_issue = MagicMock()
    labels_list = ['existing-label']  # Starting with an existing label for demonstration
    mock_jira_issue.fields.labels = labels_list

    def update_labels(fields=None):
        if fields and 'labels' in fields:
            labels_list.extend(fields['labels'])  # Simulate adding new labels

    mock_jira_issue.update = MagicMock(side_effect=update_labels)

    with (
        patch('sync_jira_actions.sync_issue._find_jira_issue', return_value=mock_jira_issue),
        patch('sync_jira_actions.sync_issue._get_jira_label', side_effect=lambda x: x['name']),
    ):
        sync_issue_module.handle_issue_labeled(mock_jira_client, mock_event)

    assert 'bug' in labels_list, "Label 'bug' was not added to the JIRA issue labels"


# ── Helper fixtures ────────────────────────────────────────────────────────────

@pytest.fixture
def base_event():
    return {
        'issue': {
            'number': 42,
            'title': 'Test issue',
            'body': 'Test body',
            'user': {'login': 'testuser', 'html_url': 'https://github.com/testuser'},
            'labels': [],
            'html_url': 'https://github.com/fake/repo/issues/42',
            'state': 'open',
            'comments': 0,
        },
        'repository': {
            'full_name': 'fake/repo',
            'name': 'repo',
            'owner': {'login': 'fake'},
        },
        'sender': {'login': 'testuser'},
    }


# ── handle_issue_opened ────────────────────────────────────────────────────────

def test_handle_issue_opened_already_exists(sync_issue_module, base_event):
    mock_jira = MagicMock()
    existing_issue = MagicMock()
    with patch('sync_jira_actions.sync_issue._find_jira_issue', return_value=existing_issue):
        sync_issue_module.handle_issue_opened(mock_jira, base_event)
    mock_jira.create_issue.assert_not_called()


# ── handle_issue_edited ────────────────────────────────────────────────────────

def test_handle_issue_edited(sync_issue_module, base_event):
    mock_jira = MagicMock()
    mock_jira_issue = MagicMock()
    with (
        patch('sync_jira_actions.sync_issue._find_jira_issue', return_value=mock_jira_issue),
        patch('sync_jira_actions.sync_issue._get_description', return_value='desc'),
        patch('sync_jira_actions.sync_issue._get_summary', return_value='summary'),
        patch('sync_jira_actions.sync_issue._update_components_field'),
        patch('sync_jira_actions.sync_issue._update_link_resolved'),
        patch('sync_jira_actions.sync_issue._leave_jira_issue_comment'),
    ):
        sync_issue_module.handle_issue_edited(mock_jira, base_event)
    mock_jira_issue.update.assert_called_once()


# ── handle_issue_closed ────────────────────────────────────────────────────────

def test_handle_issue_closed_with_issue(sync_issue_module, base_event):
    mock_jira = MagicMock()
    mock_jira_issue = MagicMock()
    with (
        patch('sync_jira_actions.sync_issue._leave_jira_issue_comment', return_value=mock_jira_issue),
        patch('sync_jira_actions.sync_issue._set_issue_status_field') as mock_set_status,
        patch('sync_jira_actions.sync_issue._update_link_resolved') as mock_update_link,
    ):
        sync_issue_module.handle_issue_closed(mock_jira, base_event)
    mock_set_status.assert_called_once_with(mock_jira_issue, 'Closed')
    mock_update_link.assert_called_once()


def test_handle_issue_closed_no_issue(sync_issue_module, base_event):
    mock_jira = MagicMock()
    with (
        patch('sync_jira_actions.sync_issue._leave_jira_issue_comment', return_value=None),
        patch('sync_jira_actions.sync_issue._set_issue_status_field') as mock_set_status,
    ):
        sync_issue_module.handle_issue_closed(mock_jira, base_event)
    mock_set_status.assert_not_called()


# ── handle_issue_labeled ───────────────────────────────────────────────────────

def test_handle_issue_labeled_no_jira_issue(sync_issue_module, base_event):
    mock_jira = MagicMock()
    base_event['issue']['labels'] = [{'name': 'bug'}]
    base_event['label'] = {'name': 'bug'}
    with patch('sync_jira_actions.sync_issue._find_jira_issue', return_value=None):
        sync_issue_module.handle_issue_labeled(mock_jira, base_event)  # should return early


def test_handle_issue_labeled_ignored_label(sync_issue_module, base_event):
    mock_jira = MagicMock()
    mock_jira_issue = MagicMock()
    mock_jira_issue.fields.labels = []
    base_event['issue']['labels'] = [{'name': 'Status: In Progress'}]
    base_event['label'] = {'name': 'Status: In Progress'}
    with patch('sync_jira_actions.sync_issue._find_jira_issue', return_value=mock_jira_issue):
        sync_issue_module.handle_issue_labeled(mock_jira, base_event)
    mock_jira_issue.update.assert_not_called()


def test_handle_issue_labeled_label_already_present(sync_issue_module, base_event):
    mock_jira = MagicMock()
    mock_jira_issue = MagicMock()
    mock_jira_issue.fields.labels = ['bug']
    base_event['issue']['labels'] = [{'name': 'bug'}]
    base_event['label'] = {'name': 'bug'}
    with patch('sync_jira_actions.sync_issue._find_jira_issue', return_value=mock_jira_issue):
        sync_issue_module.handle_issue_labeled(mock_jira, base_event)
    mock_jira_issue.update.assert_not_called()


# ── handle_issue_unlabeled ─────────────────────────────────────────────────────

def test_handle_issue_unlabeled(sync_issue_module, base_event):
    mock_jira = MagicMock()
    mock_jira_issue = MagicMock()
    mock_jira_issue.fields.labels = ['bug', 'enhancement']
    base_event['issue']['labels'] = [{'name': 'enhancement'}]
    base_event['label'] = {'name': 'bug'}
    with patch('sync_jira_actions.sync_issue._find_jira_issue', return_value=mock_jira_issue):
        sync_issue_module.handle_issue_unlabeled(mock_jira, base_event)
    mock_jira_issue.update.assert_called_once()


def test_handle_issue_unlabeled_no_jira_issue(sync_issue_module, base_event):
    mock_jira = MagicMock()
    base_event['label'] = {'name': 'bug'}
    with patch('sync_jira_actions.sync_issue._find_jira_issue', return_value=None):
        sync_issue_module.handle_issue_unlabeled(mock_jira, base_event)  # returns early


def test_handle_issue_unlabeled_ignored_label(sync_issue_module, base_event):
    mock_jira = MagicMock()
    mock_jira_issue = MagicMock()
    mock_jira_issue.fields.labels = []
    base_event['label'] = {'name': 'Resolution: fixed'}
    with patch('sync_jira_actions.sync_issue._find_jira_issue', return_value=mock_jira_issue):
        sync_issue_module.handle_issue_unlabeled(mock_jira, base_event)
    mock_jira_issue.update.assert_not_called()


def test_handle_issue_unlabeled_label_not_in_list(sync_issue_module, base_event):
    mock_jira = MagicMock()
    mock_jira_issue = MagicMock()
    mock_jira_issue.fields.labels = []
    base_event['label'] = {'name': 'nonexistent'}
    with patch('sync_jira_actions.sync_issue._find_jira_issue', return_value=mock_jira_issue):
        sync_issue_module.handle_issue_unlabeled(mock_jira, base_event)  # ValueError silently caught


# ── handle_issue_deleted / reopened ───────────────────────────────────────────

def test_handle_issue_deleted(sync_issue_module, base_event):
    mock_jira = MagicMock()
    with patch('sync_jira_actions.sync_issue._leave_jira_issue_comment') as mock_comment:
        sync_issue_module.handle_issue_deleted(mock_jira, base_event)
    mock_comment.assert_called_once_with(mock_jira, base_event, 'deleted', False)


def test_handle_issue_reopened(sync_issue_module, base_event):
    mock_jira = MagicMock()
    mock_jira_issue = MagicMock()
    with (
        patch('sync_jira_actions.sync_issue._leave_jira_issue_comment', return_value=mock_jira_issue),
        patch('sync_jira_actions.sync_issue._set_issue_status_field') as mock_set,
        patch('sync_jira_actions.sync_issue._update_link_resolved') as mock_link,
    ):
        sync_issue_module.handle_issue_reopened(mock_jira, base_event)
    mock_set.assert_called_once_with(mock_jira_issue, 'Open')
    mock_link.assert_called_once()


# ── handle_comment_* ──────────────────────────────────────────────────────────

def test_handle_comment_created(sync_issue_module, base_event):
    mock_jira = MagicMock()
    mock_jira_issue = MagicMock()
    base_event['comment'] = {
        'body': 'A comment',
        'html_url': 'https://github.com/fake/repo/issues/42#comment-1',
        'user': {'login': 'commenter'},
    }
    with (
        patch('sync_jira_actions.sync_issue._find_jira_issue', return_value=mock_jira_issue),
        patch('sync_jira_actions.sync_issue._get_jira_comment_body', return_value='formatted comment'),
    ):
        sync_issue_module.handle_comment_created(mock_jira, base_event)
    mock_jira.add_comment.assert_called_once()


def test_handle_comment_edited_found(sync_issue_module, base_event):
    mock_jira = MagicMock()
    mock_jira_issue = MagicMock()
    old_body = 'old body text'
    base_event['comment'] = {
        'body': 'new body',
        'html_url': 'https://github.com/fake/repo/issues/42#comment-1',
        'user': {'login': 'commenter'},
    }
    base_event['changes'] = {'body': {'from': old_body}}

    mock_comment = MagicMock()
    # The old body as stored in Jira — must match what _get_jira_comment_body returns with old_body
    mock_comment.body = old_body
    mock_jira.comments.return_value = [mock_comment]

    with (
        patch('sync_jira_actions.sync_issue._find_jira_issue', return_value=mock_jira_issue),
        patch('sync_jira_actions.sync_issue._markdown2wiki', side_effect=lambda x: x),
        patch('sync_jira_actions.sync_issue._get_jira_comment_body', side_effect=lambda c, b=None: b if b else 'new formatted'),
    ):
        sync_issue_module.handle_comment_edited(mock_jira, base_event)
    mock_comment.update.assert_called_once()


def test_handle_comment_edited_not_found(sync_issue_module, base_event):
    mock_jira = MagicMock()
    mock_jira_issue = MagicMock()
    base_event['comment'] = {
        'body': 'new body',
        'html_url': 'https://github.com/fake/repo/issues/42#comment-1',
        'user': {'login': 'commenter'},
    }
    base_event['changes'] = {'body': {'from': 'old body'}}
    mock_jira.comments.return_value = []  # no matching comment

    with (
        patch('sync_jira_actions.sync_issue._find_jira_issue', return_value=mock_jira_issue),
        patch('sync_jira_actions.sync_issue._markdown2wiki', side_effect=lambda x: x),
        patch('sync_jira_actions.sync_issue._get_jira_comment_body', return_value='formatted'),
    ):
        sync_issue_module.handle_comment_edited(mock_jira, base_event)
    mock_jira.add_comment.assert_called_once()


def test_handle_comment_deleted(sync_issue_module, base_event):
    mock_jira = MagicMock()
    mock_jira_issue = MagicMock()
    base_event['comment'] = {
        'body': 'deleted',
        'html_url': 'https://github.com/fake/repo/issues/42#comment-1',
        'user': {'login': 'commenter'},
    }
    with patch('sync_jira_actions.sync_issue._find_jira_issue', return_value=mock_jira_issue):
        sync_issue_module.handle_comment_deleted(mock_jira, base_event)
    mock_jira.add_comment.assert_called_once()


# ── sync_issues_manually ──────────────────────────────────────────────────────

def test_sync_issues_manually(sync_issue_module, github_client_mock):
    _, mock_repo = github_client_mock
    mock_gh_issue = MagicMock()
    mock_gh_issue.raw_data = {
        'number': 1, 'title': 'Issue 1', 'labels': [], 'state': 'open',
        'html_url': 'https://github.com/fake/repo/issues/1',
        'user': {'login': 'user', 'html_url': 'https://github.com/user'},
        'body': 'body', 'comments': 0,
    }
    mock_repo.get_issue.return_value = mock_gh_issue
    mock_jira = MagicMock()
    event = {
        'inputs': {'issue-numbers': '1 2'},
        'repository': {'full_name': 'fake/repo', 'name': 'repo', 'owner': {'login': 'fake'}},
    }
    with patch('sync_jira_actions.sync_issue.handle_issue_opened') as mock_open:
        sync_issue_module.sync_issues_manually(mock_jira, event)
    assert mock_open.call_count == 2


def test_sync_issues_manually_skips_non_numeric(sync_issue_module, github_client_mock):
    mock_jira = MagicMock()
    event = {
        'inputs': {'issue-numbers': 'abc 5 xyz'},
        'repository': {'name': 'repo', 'owner': {'login': 'fake'}},
    }
    with patch('sync_jira_actions.sync_issue.handle_issue_opened') as mock_open:
        sync_issue_module.sync_issues_manually(mock_jira, event)
    assert mock_open.call_count == 1  # only '5' is numeric


# ── _set_issue_status_field ───────────────────────────────────────────────────

def test_set_issue_status_field_success(sync_issue_module, monkeypatch):
    monkeypatch.setenv('INPUT_STATUS_FIELD_ID', '12345')
    mock_issue = MagicMock()
    sync_issue_module._set_issue_status_field(mock_issue, 'Open')
    mock_issue.update.assert_called_once_with(fields={'customfield_12345': {'value': 'Open'}})


def test_set_issue_status_field_jira_error(sync_issue_module, monkeypatch):
    monkeypatch.setenv('INPUT_STATUS_FIELD_ID', '12345')
    mock_issue = MagicMock()
    mock_issue.update.side_effect = JIRAError('Update failed')
    sync_issue_module._set_issue_status_field(mock_issue, 'Closed')  # should not raise


# ── _check_issue_label ────────────────────────────────────────────────────────

def test_check_issue_label_valid(sync_issue_module):
    assert sync_issue_module._check_issue_label('bug') == 'bug'


def test_check_issue_label_status_prefix(sync_issue_module):
    assert sync_issue_module._check_issue_label('Status: In Progress') is None


def test_check_issue_label_resolution_prefix(sync_issue_module):
    assert sync_issue_module._check_issue_label('Resolution: Fixed') is None


# ── _update_link_resolved ─────────────────────────────────────────────────────

def test_update_link_resolved_matching_link(sync_issue_module):
    mock_jira = MagicMock()
    mock_jira_issue = MagicMock()
    mock_link = MagicMock()
    mock_link.globalId = 'https://github.com/fake/repo/issues/42'
    mock_link.raw = {'object': {'title': 'old title', 'status': {'resolved': False}}}
    mock_link.relationship = 'synced from'
    mock_jira.remote_links.return_value = [mock_link]

    gh_issue = {'html_url': 'https://github.com/fake/repo/issues/42', 'title': 'New title', 'state': 'closed'}
    sync_issue_module._update_link_resolved(mock_jira, gh_issue, mock_jira_issue)
    mock_link.update.assert_called_once()


def test_update_link_resolved_no_matching_link(sync_issue_module):
    mock_jira = MagicMock()
    mock_jira_issue = MagicMock()
    mock_link = MagicMock()
    mock_link.globalId = 'https://github.com/different/issue'
    mock_jira.remote_links.return_value = [mock_link]

    gh_issue = {'html_url': 'https://github.com/fake/repo/issues/42', 'title': 'Title', 'state': 'open'}
    sync_issue_module._update_link_resolved(mock_jira, gh_issue, mock_jira_issue)
    mock_link.update.assert_not_called()


# ── _markdown2wiki ────────────────────────────────────────────────────────────

def test_markdown2wiki_none_input(sync_issue_module):
    assert sync_issue_module._markdown2wiki(None) == '\n'


def test_markdown2wiki_success(sync_issue_module):
    def mock_check_call(cmd):
        conf_path = cmd[2]
        with open(conf_path, 'w', encoding='utf-8') as f:
            f.write('converted wiki content')

    with patch('subprocess.check_call', side_effect=mock_check_call):
        result = sync_issue_module._markdown2wiki('# Hello')
    assert result == 'converted wiki content'


def test_markdown2wiki_subprocess_error(sync_issue_module):
    with patch('subprocess.check_call', side_effect=subprocess.CalledProcessError(1, 'markdown2confluence')):
        result = sync_issue_module._markdown2wiki('# Hello')
    assert result == '# Hello'


# ── _get_summary ──────────────────────────────────────────────────────────────

def test_get_summary_issue(sync_issue_module):
    gh_issue = {'number': 5, 'title': 'My issue', 'labels': []}
    gh_repo = {'name': 'myrepo'}
    result = sync_issue_module._get_summary(gh_issue, gh_repo)
    assert 'myrepo' in result
    assert '#5' in result
    assert 'My issue' in result


def test_get_summary_pr(sync_issue_module):
    gh_issue = {'number': 10, 'title': 'My PR (PROJ-123)', 'labels': [], 'pull_request': True}
    gh_repo = {'name': 'myrepo'}
    result = sync_issue_module._get_summary(gh_issue, gh_repo)
    assert 'PR' in result
    assert '(PROJ-123)' not in result  # JIRA slug stripped


def test_get_summary_strips_jira_slug(sync_issue_module):
    gh_issue = {'number': 3, 'title': 'Fix something (ABC-99)', 'labels': []}
    gh_repo = {'name': 'repo'}
    result = sync_issue_module._get_summary(gh_issue, gh_repo)
    assert '(ABC-99)' not in result


# ── _get_description ──────────────────────────────────────────────────────────

def test_get_description_issue(sync_issue_module):
    gh_issue = {'number': 1, 'title': 'Test', 'body': None, 'html_url': 'https://github.com/repo/issues/1',
                'user': {'login': 'user1', 'html_url': 'https://github.com/user1'}, 'labels': []}
    gh_repo = {'name': 'myrepo'}
    with patch('sync_jira_actions.sync_issue._markdown2wiki', return_value='wiki text'):
        result = sync_issue_module._get_description(gh_issue, gh_repo)
    assert 'Issue' in result
    assert 'myrepo' in result
    assert 'Closes #1' in result  # issue-specific dot point


def test_get_description_pr(sync_issue_module):
    gh_issue = {'number': 2, 'title': 'PR Title', 'body': 'PR body',
                'html_url': 'https://github.com/repo/pull/2',
                'user': {'login': 'user1', 'html_url': 'https://github.com/user1'},
                'labels': [], 'pull_request': True}
    gh_repo = {'name': 'myrepo'}
    with patch('sync_jira_actions.sync_issue._markdown2wiki', return_value='wiki text'):
        result = sync_issue_module._get_description(gh_issue, gh_repo)
    assert 'Pull Request' in result
    assert 'Closes' not in result  # PR does not get the closes dot point


# ── _get_jira_label ───────────────────────────────────────────────────────────

def test_get_jira_label_replaces_spaces(sync_issue_module):
    result = sync_issue_module._get_jira_label({'name': 'Type: Bug'})
    assert result == 'Type:-Bug'


def test_get_jira_label_no_spaces(sync_issue_module):
    result = sync_issue_module._get_jira_label({'name': 'enhancement'})
    assert result == 'enhancement'


# ── _get_jira_comment_body ────────────────────────────────────────────────────

def test_get_jira_comment_body_no_body(sync_issue_module):
    gh_comment = {'body': 'Hello', 'html_url': 'https://url', 'user': {'login': 'user1'}}
    with patch('sync_jira_actions.sync_issue._markdown2wiki', return_value='Hello wiki'):
        result = sync_issue_module._get_jira_comment_body(gh_comment)
    assert '@user1' in result
    assert 'Hello wiki' in result


def test_get_jira_comment_body_with_body(sync_issue_module):
    gh_comment = {'body': 'Hello', 'html_url': 'https://url', 'user': {'login': 'user1'}}
    result = sync_issue_module._get_jira_comment_body(gh_comment, body='Pre-converted body')
    assert 'Pre-converted body' in result


# ── _add_remote_link ──────────────────────────────────────────────────────────

def test_add_remote_link(sync_issue_module):
    mock_jira = MagicMock()
    mock_issue = MagicMock()
    gh_issue = {'html_url': 'https://github.com/fake/repo/issues/1', 'title': 'Test Issue'}
    sync_issue_module._add_remote_link(mock_jira, mock_issue, gh_issue)
    mock_jira.add_remote_link.assert_called_once()
    call_kwargs = mock_jira.add_remote_link.call_args
    assert call_kwargs.kwargs['globalId'] == 'https://github.com/fake/repo/issues/1'


# ── _update_github_with_jira_key ──────────────────────────────────────────────

def test_update_github_with_jira_key(sync_issue_module, github_client_mock):
    _, mock_repo = github_client_mock
    mock_api_issue = MagicMock()
    mock_api_issue.title = 'Test Issue'
    mock_repo.get_issue.return_value = mock_api_issue
    mock_jira_issue = MagicMock()
    mock_jira_issue.key = 'PROJ-42'
    gh_issue = {'number': 1}
    sync_issue_module._update_github_with_jira_key(gh_issue, mock_jira_issue)
    mock_api_issue.edit.assert_called_once_with(title='Test Issue (PROJ-42)')


def test_update_github_with_jira_key_retries_on_error(sync_issue_module, github_client_mock):
    from github.GithubException import GithubException as GHException
    _, mock_repo = github_client_mock
    mock_api_issue = MagicMock()
    mock_api_issue.title = 'Test'
    mock_repo.get_issue.return_value = mock_api_issue
    mock_api_issue.edit.side_effect = [GHException(500, 'error', None), None]
    mock_jira_issue = MagicMock()
    mock_jira_issue.key = 'PROJ-1'
    with patch('time.sleep'):
        sync_issue_module._update_github_with_jira_key({'number': 1}, mock_jira_issue)
    assert mock_api_issue.edit.call_count == 2


# ── _update_components_field ──────────────────────────────────────────────────

def test_update_components_field_no_env_var(sync_issue_module, monkeypatch):
    monkeypatch.delenv('JIRA_COMPONENT', raising=False)
    mock_jira = MagicMock()
    fields = {}
    sync_issue_module._update_components_field(mock_jira, fields)
    assert 'components' not in fields


def test_update_components_field_component_not_in_project(sync_issue_module, monkeypatch):
    monkeypatch.setenv('JIRA_COMPONENT', 'MyComponent')
    mock_jira = MagicMock()
    mock_component = MagicMock()
    mock_component.name = 'OtherComponent'
    mock_jira.project_components.return_value = [mock_component]
    fields = {}
    sync_issue_module._update_components_field(mock_jira, fields)
    assert 'components' not in fields


def test_update_components_field_sets_component(sync_issue_module, monkeypatch):
    monkeypatch.setenv('JIRA_COMPONENT', 'MyComponent')
    mock_jira = MagicMock()
    mock_component = MagicMock()
    mock_component.name = 'MyComponent'
    mock_jira.project_components.return_value = [mock_component]
    fields = {}
    sync_issue_module._update_components_field(mock_jira, fields)
    assert fields['components'] == [{'name': 'MyComponent'}]


def test_update_components_field_with_existing_issue(sync_issue_module, monkeypatch):
    monkeypatch.setenv('JIRA_COMPONENT', 'MyComponent')
    mock_jira = MagicMock()
    mock_comp = MagicMock()
    mock_comp.name = 'MyComponent'
    mock_jira.project_components.return_value = [mock_comp]
    mock_existing = MagicMock()
    mock_existing.fields.project.key = 'PROJ'
    mock_existing.fields.components = []
    fields = {}
    sync_issue_module._update_components_field(mock_jira, fields, mock_existing)
    assert 'components' in fields


# ── _get_jira_issue_type ──────────────────────────────────────────────────────

def test_get_jira_issue_type_feature_request(sync_issue_module):
    mock_jira = MagicMock()
    gh_issue = {'labels': [{'name': 'Type: Feature Request'}]}
    result = sync_issue_module._get_jira_issue_type(mock_jira, gh_issue)
    assert result == {'id': sync_issue_module.JIRA_NEW_FEATURE_TYPE_ID}


def test_get_jira_issue_type_bug(sync_issue_module):
    mock_jira = MagicMock()
    gh_issue = {'labels': [{'name': 'Type: Bug :bug:'}]}
    result = sync_issue_module._get_jira_issue_type(mock_jira, gh_issue)
    assert result == {'id': sync_issue_module.JIRA_BUG_TYPE_ID}


def test_get_jira_issue_type_label_match(sync_issue_module, monkeypatch):
    monkeypatch.setenv('JIRA_PROJECT', 'FAKE')
    mock_jira = MagicMock()
    mock_issue_type = MagicMock()
    mock_issue_type.name = 'Story'
    mock_issue_type.id = '10200'
    mock_jira.project.return_value.issueTypes = [mock_issue_type]
    gh_issue = {'labels': [{'name': 'story'}]}
    result = sync_issue_module._get_jira_issue_type(mock_jira, gh_issue)
    assert result == {'id': '10200'}


def test_get_jira_issue_type_no_match(sync_issue_module, monkeypatch):
    monkeypatch.setenv('JIRA_PROJECT', 'FAKE')
    mock_jira = MagicMock()
    mock_issue_type = MagicMock()
    mock_issue_type.name = 'Epic'
    mock_jira.project.return_value.issueTypes = [mock_issue_type]
    gh_issue = {'labels': [{'name': 'no-match-label'}]}
    result = sync_issue_module._get_jira_issue_type(mock_jira, gh_issue)
    assert result is None


def test_get_jira_issue_type_no_labels(sync_issue_module):
    mock_jira = MagicMock()
    gh_issue = {'labels': []}
    result = sync_issue_module._get_jira_issue_type(mock_jira, gh_issue)
    assert result is None


# ── _find_jira_issue ──────────────────────────────────────────────────────────

def test_find_jira_issue_found(sync_issue_module):
    mock_jira = MagicMock()
    mock_issue = MagicMock()
    mock_jira.enhanced_search_issues.return_value = [mock_issue]
    gh_issue = {'html_url': 'https://github.com/fake/repo/issues/1', 'title': 'Test'}
    gh_repo = {'name': 'repo'}
    result = sync_issue_module._find_jira_issue(mock_jira, gh_issue, gh_repo)
    assert result == mock_issue


def test_find_jira_issue_multiple_results_returns_first(sync_issue_module):
    mock_jira = MagicMock()
    issue1, issue2 = MagicMock(), MagicMock()
    mock_jira.enhanced_search_issues.return_value = [issue1, issue2]
    gh_issue = {'html_url': 'https://github.com/fake/repo/issues/1', 'title': 'Test'}
    gh_repo = {'name': 'repo'}
    result = sync_issue_module._find_jira_issue(mock_jira, gh_issue, gh_repo)
    assert result == issue1


def test_find_jira_issue_not_found_make_new_false(sync_issue_module):
    mock_jira = MagicMock()
    mock_jira.enhanced_search_issues.return_value = []
    gh_issue = {'html_url': 'https://github.com/fake/repo/issues/1', 'title': 'No JIRA key here'}
    gh_repo = {'name': 'repo'}
    result = sync_issue_module._find_jira_issue(mock_jira, gh_issue, gh_repo, make_new=False)
    assert result is None


def test_find_jira_issue_not_found_make_new_true_creates(sync_issue_module):
    mock_jira = MagicMock()
    mock_jira.enhanced_search_issues.return_value = []
    mock_new_issue = MagicMock()
    gh_issue = {
        'html_url': 'https://github.com/fake/repo/issues/1', 'title': 'No JIRA key',
        'number': 1, 'user': {'login': 'u', 'html_url': 'https://github.com/u'},
        'body': '', 'labels': [], 'state': 'open', 'comments': 0,
    }
    gh_repo = {'name': 'repo', 'full_name': 'fake/repo', 'owner': {'login': 'fake'}}
    with patch('sync_jira_actions.sync_issue._create_jira_issue', return_value=mock_new_issue) as mock_create:
        result = sync_issue_module._find_jira_issue(mock_jira, gh_issue, gh_repo, make_new=True, retries=0)
    mock_create.assert_called_once()
    assert result == mock_new_issue


def test_find_jira_issue_manual_sync_match(sync_issue_module):
    mock_jira = MagicMock()
    mock_jira.enhanced_search_issues.return_value = []
    mock_issue = MagicMock()
    mock_issue.key = 'PROJ-99'
    mock_issue.fields.description = 'https://github.com/fake/repo/issues/5'
    mock_jira.issue.return_value = mock_issue

    gh_issue = {'html_url': 'https://github.com/fake/repo/issues/5', 'title': 'Fix something (PROJ-99)', 'number': 5}
    gh_repo = {'name': 'repo'}
    with patch('sync_jira_actions.sync_issue._add_remote_link') as mock_add_link:
        result = sync_issue_module._find_jira_issue(mock_jira, gh_issue, gh_repo, make_new=False)
    mock_add_link.assert_called_once()
    assert result == mock_issue


# ── find_jira_issue (public) ──────────────────────────────────────────────────

def test_find_jira_issue_public(sync_issue_module):
    mock_jira = MagicMock()
    mock_issue = MagicMock()
    mock_jira.enhanced_search_issues.return_value = [mock_issue]
    gh_issue = {'html_url': 'https://github.com/fake/repo/issues/7', 'title': 'Test'}
    result = sync_issue_module.find_jira_issue(mock_jira, gh_issue)
    assert result == mock_issue


# ── _leave_jira_issue_comment ─────────────────────────────────────────────────

def test_leave_jira_issue_comment_with_jira_issue(sync_issue_module, base_event):
    mock_jira = MagicMock()
    mock_jira_issue = MagicMock()
    mock_jira_issue.id = 'PROJ-1'
    result = sync_issue_module._leave_jira_issue_comment(mock_jira, base_event, 'closed', False, jira_issue=mock_jira_issue)
    mock_jira.add_comment.assert_called_once()
    assert result == mock_jira_issue


def test_leave_jira_issue_comment_finds_issue(sync_issue_module, base_event):
    mock_jira = MagicMock()
    mock_jira_issue = MagicMock()
    mock_jira_issue.id = 'PROJ-2'
    with patch('sync_jira_actions.sync_issue._find_jira_issue', return_value=mock_jira_issue):
        result = sync_issue_module._leave_jira_issue_comment(mock_jira, base_event, 'opened', False)
    mock_jira.add_comment.assert_called_once()
    assert result == mock_jira_issue


def test_leave_jira_issue_comment_no_issue_found(sync_issue_module, base_event):
    mock_jira = MagicMock()
    with patch('sync_jira_actions.sync_issue._find_jira_issue', return_value=None):
        result = sync_issue_module._leave_jira_issue_comment(mock_jira, base_event, 'deleted', False)
    mock_jira.add_comment.assert_not_called()
    assert result is None


def test_leave_jira_issue_comment_is_pr(sync_issue_module, base_event):
    mock_jira = MagicMock()
    mock_jira_issue = MagicMock()
    mock_jira_issue.id = 'PROJ-3'
    base_event['issue']['pull_request'] = True
    with patch('sync_jira_actions.sync_issue._find_jira_issue', return_value=mock_jira_issue):
        sync_issue_module._leave_jira_issue_comment(mock_jira, base_event, 'edited', False)
    call_body = mock_jira.add_comment.call_args[0][1]
    assert 'PR' in call_body


def test_leave_jira_issue_comment_uses_user_login_when_no_sender(sync_issue_module, base_event):
    mock_jira = MagicMock()
    mock_jira_issue = MagicMock()
    mock_jira_issue.id = 'PROJ-4'
    del base_event['sender']  # no sender key
    with patch('sync_jira_actions.sync_issue._find_jira_issue', return_value=mock_jira_issue):
        sync_issue_module._leave_jira_issue_comment(mock_jira, base_event, 'opened', False)
    call_body = mock_jira.add_comment.call_args[0][1]
    assert 'testuser' in call_body


# ── _create_jira_issue ────────────────────────────────────────────────────────

def test_create_jira_issue(sync_issue_module, github_client_mock, monkeypatch):
    monkeypatch.setenv('JIRA_PROJECT', 'FAKE')
    _, mock_repo = github_client_mock
    mock_api_issue = MagicMock()
    mock_api_issue.title = 'Test Issue'
    mock_repo.get_issue.return_value = mock_api_issue

    mock_jira = MagicMock()
    mock_new_jira_issue = MagicMock()
    mock_new_jira_issue.key = 'FAKE-1'
    mock_jira.create_issue.return_value = mock_new_jira_issue

    gh_issue = {
        'number': 1, 'title': 'Test Issue', 'body': None,
        'html_url': 'https://github.com/fake/repo/issues/1',
        'user': {'login': 'user1', 'html_url': 'https://github.com/user1'},
        'labels': [], 'state': 'open', 'comments': 0,
    }
    gh_repo = {'name': 'repo', 'full_name': 'fake/repo', 'owner': {'login': 'fake'}}

    with (
        patch('sync_jira_actions.sync_issue._get_jira_issue_type', return_value=None),
        patch('sync_jira_actions.sync_issue._get_description', return_value='desc'),
        patch('sync_jira_actions.sync_issue._update_components_field'),
        patch('sync_jira_actions.sync_issue._set_issue_status_field'),
        patch('sync_jira_actions.sync_issue._add_remote_link'),
        patch('sync_jira_actions.sync_issue._update_github_with_jira_key'),
        patch('sync_jira_actions.sync_issue._add_existing_comments'),
    ):
        result = sync_issue_module._create_jira_issue(mock_jira, gh_issue, gh_repo)
    assert result == mock_new_jira_issue
    mock_jira.create_issue.assert_called_once()


def test_create_jira_issue_closed_updates_link(sync_issue_module, github_client_mock, monkeypatch):
    monkeypatch.setenv('JIRA_PROJECT', 'FAKE')
    _, mock_repo = github_client_mock
    mock_repo.get_issue.return_value = MagicMock(title='Test Issue')

    mock_jira = MagicMock()
    mock_new_jira_issue = MagicMock()
    mock_new_jira_issue.key = 'FAKE-2'
    mock_jira.create_issue.return_value = mock_new_jira_issue

    gh_issue = {
        'number': 2, 'title': 'Closed Issue', 'body': None,
        'html_url': 'https://github.com/fake/repo/issues/2',
        'user': {'login': 'user1', 'html_url': 'https://github.com/user1'},
        'labels': [], 'state': 'closed', 'comments': 0,
    }
    gh_repo = {'name': 'repo', 'full_name': 'fake/repo', 'owner': {'login': 'fake'}}

    with (
        patch('sync_jira_actions.sync_issue._get_jira_issue_type', return_value=None),
        patch('sync_jira_actions.sync_issue._get_description', return_value='desc'),
        patch('sync_jira_actions.sync_issue._update_components_field'),
        patch('sync_jira_actions.sync_issue._set_issue_status_field'),
        patch('sync_jira_actions.sync_issue._add_remote_link'),
        patch('sync_jira_actions.sync_issue._update_github_with_jira_key'),
        patch('sync_jira_actions.sync_issue._add_existing_comments'),
        patch('sync_jira_actions.sync_issue._update_link_resolved') as mock_update_link,
    ):
        sync_issue_module._create_jira_issue(mock_jira, gh_issue, gh_repo)
    mock_update_link.assert_called_once()


# ── _add_existing_comments ────────────────────────────────────────────────────

def test_add_existing_comments_zero_comments(sync_issue_module, github_client_mock):
    mock_jira = MagicMock()
    gh_issue = {'number': 1, 'comments': 0}
    sync_issue_module._add_existing_comments(mock_jira, gh_issue, 'ISSUE-1')
    mock_jira.add_comment.assert_not_called()


def test_add_existing_comments_with_comments(sync_issue_module, github_client_mock):
    _, mock_repo = github_client_mock
    mock_comment = MagicMock()
    mock_comment.body = 'Comment body'
    mock_comment.html_url = 'https://github.com/url#comment1'
    mock_comment.user.login = 'commenter'
    mock_repo.get_issue.return_value.get_comments.return_value.reversed = [mock_comment]

    mock_jira = MagicMock()
    gh_issue = {'number': 1, 'comments': 1}
    with patch('sync_jira_actions.sync_issue._get_jira_comment_body', return_value='formatted'):
        sync_issue_module._add_existing_comments(mock_jira, gh_issue, 'ISSUE-1')
    mock_jira.add_comment.assert_called_once_with('ISSUE-1', 'formatted')
