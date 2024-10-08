#!/usr/bin/env python3
#
# Copyright 2019-2024 Espressif Systems (Shanghai) CO LTD
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
import os
import re
from jira import JIRA
from github import Github
from sync_issue import _create_jira_issue
from sync_issue import _find_jira_issue
from github_graphql import find_closing_issues, get_pr_review_status

# The minimum number of approvals before a PR is ready to merge.
MINIMUM_APPROVALS = int(os.environ.get('INPUT_MINIMUM_APPROVALS', 3))

def sync_remain_prs(jira):
    """
    Sync remain PRs (i.e. PRs without any comments) to Jira
    """
    github = Github(os.environ['GITHUB_TOKEN'])
    repo = github.get_repo(os.environ['GITHUB_REPOSITORY'])
    prs = repo.get_pulls(state='open', sort='created', direction='desc')
    for pr in prs:
        if not repo.has_in_collaborators(pr.user.login):
            # mock a github issue using current PR
            gh_issue = {
                'pull_request': True,
                'labels': [{'name': lbl.name} for lbl in pr.labels],
                'number': pr.number,
                'title': pr.title,
                'html_url': pr.html_url,
                'user': {'login': pr.user.login},
                'state': pr.state,
                'body': pr.body,
            }
            issue = _find_jira_issue(jira, gh_issue)
            if issue is None:
                _create_jira_issue(jira, gh_issue)


def find_and_link_pr_issues(gh_issue):
    """
    Finds any linked issues that will be closed by a PR then adds the Jira issues to the title
    This allows auto linking of PR's to related Jira issues.
    """
    token = os.environ['GITHUB_TOKEN']
    project = os.environ['JIRA_PROJECT']
    github = Github(os.environ['GITHUB_TOKEN'])
    repo = github.get_repo(os.environ['GITHUB_REPOSITORY'])
    pr_number = int(gh_issue['number'])
    pr_title = gh_issue['title']
    closing_issues = find_closing_issues(token, repo.owner.login, repo.name, pr_number)
    jira_keys = []
    for issue in closing_issues:
        title = issue.get('title')
        match = re.search(f'.*({project}-\d*).*', title)
        if match:
            jira_key = match.group(1)
            print(f"Found linked issue: {jira_key}")
            jira_keys.append(jira_key)
    if len(jira_keys) > 0:
        new_pr_title = re.sub(f'{project}-\d*', '', pr_title)
        new_pr_title = re.sub('\(\s*\)', '', new_pr_title).strip()
        new_pr_title = f'{new_pr_title} ({" ".join(jira_keys)})'
        print(f'New PR title: {new_pr_title}')
        repo.get_issue(pr_number).edit(title=new_pr_title)
    return jira_keys

def check_pr_approval_and_move(jira: JIRA, gh_issue, jira_keys):
    """
    Checks the approval criteria of the PR and moves any linked Jira issues to Approved or back to review.
    """
    token = os.environ['GITHUB_TOKEN']
    github = Github(os.environ['GITHUB_TOKEN'])
    repo = github.get_repo(os.environ['GITHUB_REPOSITORY'])
    pr_number = int(gh_issue['number'])
    approved = __check_pr_approval_status(pr_number, repo, token)
    for key in jira_keys:
        issue_status = str(jira.issue(key).get_field("status"))
        print(f"{key}: status '{issue_status}' approved '{approved}'")
        if approved and issue_status == "Review in progress":
            print(f"{key}: Transition to Approved")
            jira.transition_issue(key, "Approved")
            jira.add_comment(key, "The PR linked to this issue has met approval criteria and is ready to merge.")
        if not approved and issue_status == "Reviewer Approved":
            print(f"{key}: Transition back to review in progress")
            jira.transition_issue(key, "Requires re-review")
            jira.add_comment(key, "The PR linked to this issue has new changes requested and moved back to review.")

def __check_pr_approval_status(pr, repo, token):
    """
    Checks the approval criteria of the PR
    """
    status = get_pr_review_status(token, repo.owner.login, repo.name, pr)
    approved = status.outcome == "APPROVED"
    num_approved = len([r for r in status.reviews if r == "APPROVED"])
    print(f"PR Status: {status.outcome} with {num_approved}/{MINIMUM_APPROVALS} approvals")
    return approved and num_approved >= MINIMUM_APPROVALS