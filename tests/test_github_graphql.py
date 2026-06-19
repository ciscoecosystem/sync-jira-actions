from unittest.mock import MagicMock, patch

import pytest

from sync_jira_actions import github_graphql


def make_mock_response(json_data, status_code=200):
    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.json.return_value = json_data
    return mock_response


class TestFindClosingIssues:
    def test_success(self):
        nodes = [{'number': 1, 'title': 'Fix bug (PROJ-123)'}]
        data = {'data': {'repository': {'pullRequest': {'closingIssuesReferences': {'nodes': nodes}}}}}
        with patch('requests.post', return_value=make_mock_response(data)):
            result = github_graphql.find_closing_issues('token', 'owner', 'repo', 1)
        assert result == nodes

    def test_query_failure_raises_exception(self):
        with patch('requests.post', return_value=make_mock_response({}, 400)):
            with pytest.raises(Exception, match='Query failed'):
                github_graphql.find_closing_issues('token', 'owner', 'repo', 1)

    def test_empty_nodes(self):
        data = {'data': {'repository': {'pullRequest': {'closingIssuesReferences': {'nodes': []}}}}}
        with patch('requests.post', return_value=make_mock_response(data)):
            result = github_graphql.find_closing_issues('token', 'owner', 'repo', 99)
        assert result == []


class TestFindClosedByPr:
    def test_success(self):
        nodes = [{'number': 10, 'title': 'Some issue'}]
        data = {'data': {'repository': {'issue': {'closedByPullRequestsReferences': {'nodes': nodes}}}}}
        with patch('requests.post', return_value=make_mock_response(data)):
            result = github_graphql.find_closed_by_pr('token', 'owner', 'repo', 10)
        assert result == nodes

    def test_query_failure_raises_exception(self):
        with patch('requests.post', return_value=make_mock_response({}, 500)):
            with pytest.raises(Exception):
                github_graphql.find_closed_by_pr('token', 'owner', 'repo', 10)


class TestGetPrReviewStatus:
    def test_approved(self):
        reviews = [{'state': 'APPROVED'}, {'state': 'APPROVED'}, {'state': 'APPROVED'}]
        pr_data = {'title': 'Test PR', 'reviewDecision': 'APPROVED', 'latestReviews': {'nodes': reviews}}
        data = {'data': {'repository': {'pullRequest': pr_data}}}
        with patch('requests.post', return_value=make_mock_response(data)):
            result = github_graphql.get_pr_review_status('token', 'owner', 'repo', 1)
        assert result.title == 'Test PR'
        assert result.outcome == 'APPROVED'
        assert result.reviews == ['APPROVED', 'APPROVED', 'APPROVED']

    def test_changes_requested(self):
        reviews = [{'state': 'CHANGES_REQUESTED'}]
        pr_data = {'title': 'Test PR', 'reviewDecision': 'CHANGES_REQUESTED', 'latestReviews': {'nodes': reviews}}
        data = {'data': {'repository': {'pullRequest': pr_data}}}
        with patch('requests.post', return_value=make_mock_response(data)):
            result = github_graphql.get_pr_review_status('token', 'owner', 'repo', 2)
        assert result.outcome == 'CHANGES_REQUESTED'
        assert 'CHANGES_REQUESTED' in result.reviews

    def test_query_failure_raises_exception(self):
        with patch('requests.post', return_value=make_mock_response({}, 403)):
            with pytest.raises(Exception):
                github_graphql.get_pr_review_status('token', 'owner', 'repo', 1)


class TestGetRecentlyUpdatedPrUrl:
    def test_success(self):
        nodes = [{'title': 'Test PR', 'number': 5, 'updatedAt': '2024-01-01'}]
        data = {'data': {'repository': {'pullRequests': {'nodes': nodes}}}}
        with patch('requests.post', return_value=make_mock_response(data)):
            result = github_graphql.get_recently_updated_pr_url('token', 'owner', 'myrepo')
        assert result == 'https://api.github.com/repos/owner/myrepo/issues/5'

    def test_no_nodes_returns_none(self):
        data = {'data': {'repository': {'pullRequests': {'nodes': None}}}}
        with patch('requests.post', return_value=make_mock_response(data)):
            result = github_graphql.get_recently_updated_pr_url('token', 'owner', 'repo')
        assert result is None

    def test_query_failure_raises_exception(self):
        with patch('requests.post', return_value=make_mock_response({}, 401)):
            with pytest.raises(Exception):
                github_graphql.get_recently_updated_pr_url('token', 'owner', 'repo')
