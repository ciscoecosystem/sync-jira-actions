#!/usr/bin/env python3
#
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

import requests
from collections import namedtuple

GITHUB_GRAPHQL = 'https://api.github.com/graphql'
GITHUB_BASE_REST_API = 'https://api.github.com/repos'

def __post_query(token, query, vars):
    headers = {"Authorization": f"Bearer {token}"}
    request = requests.post(GITHUB_GRAPHQL, json={'query': query, 'variables': vars}, headers=headers)
    if request.status_code == 200:
        return request.json().get('data')
    else:
        raise Exception("Query failed to run by returning code of {}. {}".format(request.status_code, query))


def find_closing_issues(token, owner, repo, pr):
    vars = {"owner": owner, "repo": repo, "pr": pr}
    query = """
        query($owner:String!, $repo:String!, $pr:Int!) {
            repository (owner: $owner, name: $repo) {
                pullRequest (number: $pr) {
                    closingIssuesReferences (first: 10) {
                        nodes {
                            number
                            title
                        }
                    }
                }
            }
        }
    """
    data = __post_query(token, query, vars)
    return data.get('repository').get('pullRequest').get('closingIssuesReferences').get('nodes')


def find_closed_by_pr(token, owner, repo, issue):
    vars = {"owner": owner, "repo": repo, "issue": issue}
    query = """
        query($owner:String!, $repo:String!, $pr:Int!) {
            repository (owner: $owner, name: $repo) {
                issue (number: $issue) {
                    closedByPullRequestsReferences (first: 10) {
                        nodes {
                            number
                            title
                        }
                    }
                }
            }
        }
        """
    data = __post_query(token, query, vars)
    return data.get('repository').get('issue').get('closedByPullRequestsReferences').get('nodes')


def get_pr_review_status(token, owner, repo, pr):
    vars = {"owner": owner, "repo": repo, "pr": pr}
    query = """
        query($owner:String!, $repo:String!, $pr:Int!) {
            repository (owner: $owner, name: $repo) {
                pullRequest (number: $pr) {
                    title,
                    reviewDecision,
                    latestReviews (last: 10) {
                        nodes {
                            state
                        }
                    }
                }
            }
        }
    """
    data = __post_query(token, query, vars)
    pr_data = data.get('repository').get('pullRequest')
    reviews = [review.get('state') for review in pr_data.get("latestReviews").get("nodes")]
    result = {"title": pr_data.get('title'), "outcome": pr_data.get('reviewDecision'), "reviews": reviews}
    return namedtuple('Struct', result.keys())(*result.values())


def get_recently_updated_pr_url(token, owner, repo):
    vars = {"owner": owner, "repo": repo}
    query = """
        query($owner:String!, $repo:String!) {
            repository (owner: $owner, name: $repo) {
                pullRequests (last:1 orderBy: {field: UPDATED_AT, direction: ASC} ) {
                    nodes {
                        title
                        number
                        updatedAt
                    }
                }
            }
        }
    """
    data = __post_query(token, query, vars)
    nodes = data.get('repository', {}).get('pullRequests', {}).get('nodes', None)
    if nodes is None:
        return None
    return f"{GITHUB_BASE_REST_API}/{owner}/{repo}/issues/{nodes[0].get('number')}"