import importlib
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest


# Patch the GitHub client before importing modules that use it
@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch):
    monkeypatch.setenv('GITHUB_TOKEN', 'fake-token')
    monkeypatch.setenv('GITHUB_REPOSITORY', 'fake/repo')


@pytest.fixture
def mock_github():
    with patch('github.Github') as MockGithub:
        mock_repo = MagicMock()
        mock_pr = MagicMock()
        mock_pr.number = 1
        mock_pr.title = 'Test PR'
        mock_pr.html_url = 'http://example.com/testpr'
        mock_pr.user.login = 'testuser'
        mock_pr.labels = []
        mock_pr.state = 'open'
        mock_pr.body = 'Test body'
        mock_repo.get_pulls.return_value = [mock_pr]
        mock_repo.has_in_collaborators.return_value = False

        MockGithub.return_value.get_repo.return_value = mock_repo
        yield mock_repo


@pytest.fixture
def sync_pr_module(mock_github):
    # Import the module from the sync_jira_actions directory
    import sys

    sys.path.insert(0, 'sync_jira_actions')  # Add sync_jira_actions directory to the Python path
    import sync_pr

    # Reload the module to ensure the mock is applied
    importlib.reload(sync_pr)
    # Return the reloaded module
    return sync_pr


@pytest.fixture
def mock_sync_issue():
    with (
        patch('sync_pr._create_jira_issue') as mock_create_jira_issue,
        patch('sync_pr._find_jira_issue', return_value=None) as mock_find_jira_issue,
    ):
        yield mock_create_jira_issue, mock_find_jira_issue


def test_sync_remain_prs(sync_pr_module, mock_sync_issue, mock_github):
    mock_jira = MagicMock()
    mock_create_jira_issue, mock_find_jira_issue = mock_sync_issue

    # Use the function from the reloaded module
    sync_pr_module.sync_remain_prs(mock_jira)

    # Verify _find_jira_issue was called once with the mock_jira client and the PR data
    assert mock_find_jira_issue.call_count == 1

    # Verify _create_jira_issue was called once since no corresponding JIRA issue was found
    assert mock_create_jira_issue.call_count == 1

    # Example of verifying call arguments (simplified)
    call_args = mock_create_jira_issue.call_args
    assert 'Test PR' in call_args[0][1]['title'], 'PR title does not match expected value'


# ── find_and_link_pr_issues ───────────────────────────────────────────────────

@pytest.fixture
def sync_pr_module_clean():
    import importlib
    import sys
    sys.path.insert(0, 'sync_jira_actions')
    import sync_pr
    importlib.reload(sync_pr)
    return sync_pr


def test_find_and_link_pr_issues_with_jira_keys(sync_pr_module, mock_github):
    gh_issue = {
        'number': 5,
        'title': 'Fix the bug',
        'html_url': 'https://github.com/fake/repo/pull/5',
        'user': {'login': 'testuser'},
        'labels': [],
    }
    closing_issues = [{'title': 'Related issue (PROJ-42)', 'number': 10}]

    with (
        patch('sync_pr.find_closing_issues', return_value=closing_issues),
        patch('sync_pr.Github', return_value=MagicMock(get_repo=MagicMock(return_value=mock_github))),
    ):
        result = sync_pr_module.find_and_link_pr_issues(gh_issue)

    assert 'PROJ-42' in result
    mock_github.get_issue.assert_called_once_with(5)


def test_find_and_link_pr_issues_no_closing_issues(sync_pr_module, mock_github):
    gh_issue = {
        'number': 6,
        'title': 'Another PR',
        'html_url': 'https://github.com/fake/repo/pull/6',
        'user': {'login': 'testuser'},
        'labels': [],
    }
    with patch('sync_pr.find_closing_issues', return_value=[]):
        result = sync_pr_module.find_and_link_pr_issues(gh_issue)

    assert result == []


def test_find_and_link_pr_issues_no_jira_key_in_title(sync_pr_module, mock_github):
    gh_issue = {
        'number': 7,
        'title': 'PR without jira key',
        'html_url': 'https://github.com/fake/repo/pull/7',
        'user': {'login': 'testuser'},
        'labels': [],
    }
    closing_issues = [{'title': 'Issue without JIRA key', 'number': 11}]
    with patch('sync_pr.find_closing_issues', return_value=closing_issues):
        result = sync_pr_module.find_and_link_pr_issues(gh_issue)

    assert result == []


# ── check_pr_approval_and_move ────────────────────────────────────────────────

def _make_pr_review_status(outcome, reviews):
    from collections import namedtuple
    data = {'title': 'Test PR', 'outcome': outcome, 'reviews': reviews}
    return namedtuple('Struct', data.keys())(*data.values())


def test_check_pr_approval_and_move_approved(sync_pr_module, mock_github):
    mock_jira = MagicMock()
    mock_issue = MagicMock()
    mock_issue.get_field.side_effect = lambda f: 'Review in progress' if f == 'status' else 'Task'
    mock_jira.issue.return_value = mock_issue

    gh_issue = {'number': 1, 'title': 'Test', 'user': {'login': 'u'}, 'labels': []}
    jira_keys = ['PROJ-1']

    status = _make_pr_review_status('APPROVED', ['APPROVED', 'APPROVED', 'APPROVED'])
    with patch('sync_pr.get_pr_review_status', return_value=status):
        sync_pr_module.check_pr_approval_and_move(mock_jira, gh_issue, jira_keys)

    mock_jira.transition_issue.assert_called_once()
    mock_jira.add_comment.assert_called_once()


def test_check_pr_approval_and_move_changes_requested(sync_pr_module, mock_github):
    mock_jira = MagicMock()
    mock_issue = MagicMock()
    mock_issue.get_field.side_effect = lambda f: 'Review in progress' if f == 'status' else 'Task'
    mock_jira.issue.return_value = mock_issue

    gh_issue = {'number': 2, 'title': 'Test', 'user': {'login': 'u'}, 'labels': []}
    jira_keys = ['PROJ-2']

    status = _make_pr_review_status('CHANGES_REQUESTED', ['CHANGES_REQUESTED'])
    with patch('sync_pr.get_pr_review_status', return_value=status):
        sync_pr_module.check_pr_approval_and_move(mock_jira, gh_issue, jira_keys)

    mock_jira.transition_issue.assert_called_once()


def test_check_pr_approval_and_move_review_in_progress(sync_pr_module, mock_github):
    mock_jira = MagicMock()
    mock_issue = MagicMock()
    mock_issue.get_field.side_effect = lambda f: 'In Progress' if f == 'status' else 'Task'
    mock_jira.issue.return_value = mock_issue

    gh_issue = {'number': 3, 'title': 'Test', 'user': {'login': 'u'}, 'labels': []}
    jira_keys = ['PROJ-3']

    status = _make_pr_review_status(None, [])
    with patch('sync_pr.get_pr_review_status', return_value=status):
        sync_pr_module.check_pr_approval_and_move(mock_jira, gh_issue, jira_keys)

    mock_jira.transition_issue.assert_not_called()


def test_check_pr_approval_and_move_approved_demotes_to_review(sync_pr_module, mock_github):
    """When review is in progress but jira issue was previously approved, demote it."""
    mock_jira = MagicMock()
    mock_issue = MagicMock()
    mock_issue.get_field.side_effect = lambda f: 'Reviewer Approved' if f == 'status' else 'Task'
    mock_jira.issue.return_value = mock_issue

    gh_issue = {'number': 4, 'title': 'Test', 'user': {'login': 'u'}, 'labels': []}
    jira_keys = ['PROJ-4']

    status = _make_pr_review_status(None, [])
    with patch('sync_pr.get_pr_review_status', return_value=status):
        sync_pr_module.check_pr_approval_and_move(mock_jira, gh_issue, jira_keys)

    mock_jira.transition_issue.assert_called_once()
    mock_jira.add_comment.assert_called_once()
