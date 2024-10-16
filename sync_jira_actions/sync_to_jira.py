#!/usr/bin/env python3
#
# Copyright 2019 Espressif Systems (Shanghai) CO LTD
# Copyright: (c) 2024, Samita Bhattacharjee (@samiib) <samitab@cisco.com>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import json
import os
import requests

from github import Github
from jira import JIRA
from sync_issue import handle_comment_created
from sync_issue import handle_comment_deleted
from sync_issue import handle_comment_edited
from sync_issue import handle_issue_closed
from sync_issue import handle_issue_deleted
from sync_issue import handle_issue_edited
from sync_issue import handle_issue_labeled
from sync_issue import handle_issue_opened
from sync_issue import handle_issue_reopened
from sync_issue import handle_issue_unlabeled
from sync_issue import sync_issues_manually
from sync_issue import find_jira_issue
from sync_pr import sync_remain_prs, find_and_link_pr_issues, check_pr_approval_and_move
from github_graphql import get_recently_updated_pr_url


class _JIRA(JIRA):
    def applicationlinks(self):
        return []  # disable this function as we don't need it and it makes add_remote_links() slow


def main():
    if 'GITHUB_REPOSITORY' not in os.environ:
        print('Not running in GitHub action context, nothing to do')
        return

    jira_url = os.environ.get("JIRA_URL")
    if jira_url is None or jira_url == "":
        print('No Jira URL configured, nothing to do')
        return

    # Connect to Jira server
    print('Connecting to Jira Server...')

    # Check if the JIRA_PASS is token or password
    token_or_pass = os.environ['JIRA_PASS']
    if token_or_pass.startswith('token:'):
        print('Authenticating with JIRA_TOKEN ...')
        token = token_or_pass[6:]  # Strip the 'token:' prefix
        jira = _JIRA(os.environ['JIRA_URL'], token_auth=token)
    else:
        print('Authenticating with JIRA_USER and JIRA_PASS ...')
        jira = _JIRA(os.environ['JIRA_URL'], basic_auth=(os.environ['JIRA_USER'], token_or_pass))

    # Check if it's a cron job
    if os.environ.get('INPUT_CRON_JOB'):
        print('Running as a cron job. Syncing remaining PRs...')
        sync_remain_prs(jira)
        return
    
    event_name = os.environ['GITHUB_EVENT_NAME']
    print(f"On: {event_name}")

    # The path of the file with the complete webhook event payload. For example, /github/workflow/event.json.
    with open(os.environ['GITHUB_EVENT_PATH'], 'r', encoding='utf-8') as file:
        event = json.load(file)
        print(json.dumps(event, indent=4))

    # Check if event is workflow_dispatch and action is mirror issues.
    # If so, run manual mirroring and skip rest of the script. Works both for issues and pull requests.
    if event_name == 'workflow_dispatch':
        inputs = event.get('inputs')

        if not inputs:
            print('Triggered workflow_dispatch event without correct inputs. Exiting...')
            return

        input_action = inputs.get('action')
        issue_numbers = inputs.get('issue-numbers')
        if input_action != 'mirror-issues':
            print('This action needs input "mirror-issues". Exiting...')
            return
        if not issue_numbers:
            print('This action needs inputs "issue-numbers". Exiting...')
            return

        print(f'Starting manual sync of issues: {issue_numbers}')
        sync_issues_manually(jira, event)
        return

    # The name of the webhook event that triggered the workflow.
    action = event['action']

    token = os.environ['GITHUB_TOKEN']
    github = Github(token)
    repo = github.get_repo(os.environ['GITHUB_REPOSITORY'])

    if event_name == 'pull_request':
        # Treat pull request events just like issues events for syncing purposes
        # (we can check the 'pull_request' key in the "issue" later to know if this is an issue or a PR)
        event_name = 'issues'
        event['issue'] = event['pull_request']
        if 'pull_request' not in event['issue']:
            event['issue']['pull_request'] = True  # we don't care about the value

    if event_name == 'pull_request_target':
        # Also treat pull_request_target events just like issues events for syncing purposes
        # Need to use the PR issue data instead of the pull data
        event_name = 'issues'
        issue_url = event['pull_request']['_links']['issue']['href']
        print(f'GET {issue_url}')
        data = requests.get(issue_url).json()
        print(json.dumps(data, indent=4))
        event['issue'] = data

    if event_name == 'workflow_run':
        # Also treat workflow_run events triggered from pull_request_review just like issues events for syncing purposes
        # Need to use the PR issue data instead of the workflow data
        run_data = event.get('workflow_run', {})
        run_event = run_data.get('event')
        if run_event == 'pull_request_review':
            event_name = 'issues'
            issue_url = get_recently_updated_pr_url(token, repo.owner.login, repo.name)
            print(f'GET Last Updated PR: {issue_url}')
            data = requests.get(issue_url).json()
            print(json.dumps(data, indent=4))
            event['issue'] = data

    sync_label = os.environ.get('INPUT_SYNC_LABEL')
    gh_issue = event['issue']
    has_sync_label = sync_label in [l['name'] for l in gh_issue["labels"]]

    # Don't sync a PR if user/creator is a collaborator
    # unless a sync label is used and is present.
    is_pr = 'pull_request' in gh_issue

    if is_pr and os.environ.get('INPUT_LINK_CLOSING_ISSUES'):
        jira_keys = find_and_link_pr_issues(gh_issue)
        if any(jira_keys):
            check_pr_approval_and_move(jira, gh_issue, jira_keys)
            print("Skipping sync for Pull Request linked to synced GitHub Issue")
            return

    if is_pr and repo.has_in_collaborators(gh_issue['user']['login']) and not has_sync_label:
        print('Skipping issue sync for Pull Request from collaborator')
        return

    # If sync label is set, don't sync any issues that do not have the label
    if sync_label and not has_sync_label:
        print(f'Skipping issue sync because Issue is missing the {sync_label} label')
        return

    # If syncing enabled for a standalone PR, check aproval before action handlers to
    # handle appropriate transitions
    if is_pr:
        issue = find_jira_issue(jira, gh_issue)
        if issue is not None:
            check_pr_approval_and_move(jira, gh_issue, [issue.key])

    action_handlers = {
        'issues': {
            'opened': handle_issue_opened,
            'edited': handle_issue_edited,
            'closed': handle_issue_closed,
            'deleted': handle_issue_deleted,
            'reopened': handle_issue_reopened,
            'labeled': handle_issue_labeled,
            'unlabeled': handle_issue_unlabeled,
        },
        'issue_comment': {
            'created': handle_comment_created,
            'edited': handle_comment_edited,
            'deleted': handle_comment_deleted,
        }
    }

    if event_name not in action_handlers:
        print(f"No handler for event '{event_name}'. Skipping.")
    elif action not in action_handlers[event_name]:
        print(f"No handler '{event_name}' action '{action}'. Skipping.")
    else:
        action_handlers[event_name][action](jira, event)


if __name__ == '__main__':
    main()
