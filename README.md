<div align="center">
  <h1>GitHub to JIRA Sync (GitHub Action)</h1>
  <img src="docs/sync-jira-actions.png" alt="GitHub to JIRA Sync logo" width="400">
  <br>
  <br>
  <!-- GitHub Badges -->
   <img alt="release" src="https://img.shields.io/github/v/release/ciscoecosystem/sync-jira-actions" />
   <img alt="tests" src="https://github.com/ciscoecosystem/sync-jira-actions/actions/workflows/python-test.yml/badge.svg" />
   <img alt="codeql" src="https://github.com/ciscoecosystem/sync-jira-actions/actions/workflows/github-code-scanning/codeql/badge.svg?branch=v1" />
</div>
GitHub to JIRA Sync GitHub Action is a solution for one-way synchronization of GitHub issues into JIRA projects.
<br>
<br>
This action automates the integration of your GitHub repositories with JIRA projects by automatically creating corresponding JIRA tickets for new GitHub issues and pull requests, as well as managing comments within these issues and pull requests from external contributors.

<hr>

- [Features](#features)
- ['Synced From' Link Details](#synced-from-link-details)
  - [Key Features and Considerations](#key-features-and-considerations)
- [Manually Linking a GitHub Issue to JIRA](#manually-linking-a-github-issue-to-jira)
  - [Step-by-Step Guide](#step-by-step-guide)
  - [Automation Trigger](#automation-trigger)
  - [Important Note](#important-note)
- [Issue Type Synchronization](#issue-type-synchronization)
  - [How It Works](#how-it-works)
- [Limitations](#limitations)
  - [What's Not Synced](#whats-not-synced)
- [Usage Instructions for GitHub to JIRA Issue Sync Action](#usage-instructions-for-github-to-jira-issue-sync-action)
  - [Syncing New Issues to JIRA](#syncing-new-issues-to-jira)
  - [Syncing New Issue Comments to JIRA](#syncing-new-issue-comments-to-jira)
  - [Syncing New Pull Requests to JIRA](#syncing-new-pull-requests-to-jira)
  - [Syncing Pull Request Review Status to JIRA](#syncing-pull-request-review-status-to-jira)
  - [Using a Sync Label to Gate Syncing](#using-a-sync-label-to-gate-syncing)
- [Manually Syncing Issues and Pull Requests to JIRA](#manually-syncing-issues-and-pull-requests-to-jira)
  - [Configuration for Manual Sync](#configuration-for-manual-sync)
  - [Workflow Setup](#workflow-setup)
- [Environment Variables and Secrets Configuration](#environment-variables-and-secrets-configuration)
  - [Important Consideration:](#important-consideration)
  - [Action Inputs](#action-inputs)
- [Security](#security)
  - [Never interpolate workflow outputs into `run:` steps](#never-interpolate-workflow-outputs-into-run-steps)
  - [Do not check out and run untrusted PR code in the same job](#do-not-check-out-and-run-untrusted-pr-code-in-the-same-job)
  - [Use least-privilege permissions](#use-least-privilege-permissions)
  - [Gate on a trusted label](#gate-on-a-trusted-label)
  - [Use per-item concurrency with `cancel-in-progress`](#use-per-item-concurrency-with-cancel-in-progress)
  - [Pin to a commit SHA](#pin-to-a-commit-sha)
  - [Trim `pull_request_target` activity types](#trim-pull_request_target-activity-types)
- [Project Issues](#project-issues)
- [Contributing](#contributing)

## Features

- **Automatic Issue Creation**: When a new GitHub issue is opened, a matching JIRA issue is created within the specified project.
- **Markdown Conversion**: The body of the GitHub issue is converted to JIRA Wiki format using [markdown2confluence](http://chunpu.github.io/markdown2confluence/browser/).
- **Custom Field Mapping**: A JIRA custom field named "GitHub Reference" is populated with the URL of the GitHub issue.
- **Issue Title Sync**: The title of the GitHub issue is updated to include the JIRA issue key.
- **Comment Sync (GitHub → JIRA)**: Comments added to a GitHub issue are mirrored in the corresponding JIRA issue. Edits and deletions are also reflected.
- **Label Synchronization**: Labels added or removed from the GitHub issue are similarly updated in the JIRA issue.
- **Remote Issue Link**: After syncing, a [Remote Issue Link](https://developer.atlassian.com/server/jira/platform/creating-remote-issue-links/) is created on the JIRA issue for easy reference back to the GitHub issue.
- **PR Review Status Sync**: Pull request review approvals, change requests, and dismissals automatically transition the linked JIRA issue between workflow states (e.g. "Review in progress", "Reviewer Approved", "Changes Requested").
- **Label-gated Sync**: Optionally require a specific label (via `sync_label`) to be present on an issue or PR before it is synced to JIRA.
- **PR-to-Issue Linking**: When `link_closing_issues` is enabled, the action automatically detects GitHub issues that a PR will close, appends the corresponding JIRA key to the PR title, and transitions the JIRA issue based on PR review status.

## 'Synced From' Link Details

Once a JIRA issue is created and synced from GitHub, a [Remote Issue Link](https://developer.atlassian.com/server/jira/platform/creating-remote-issue-links/) is automatically generated for the JIRA issue. This link includes a "globalID" that corresponds to the URL of the GitHub issue. This mechanism ensures that any future changes to the GitHub issue are tracked and reflected in the JIRA issue, maintaining a consistent link between the two platforms.

### Key Features and Considerations

- **Persistent Synchronization**: The Remote Issue Link facilitates ongoing updates to JIRA issues that are moved to other JIRA projects, assuming the remote issue link is also transferred and the GitHub Action's JIRA user has access to the new project.
- **Link Management**: To sever the connection between a GitHub issue and a JIRA issue, simply remove the Remote Issue Link. Be aware, however, that subsequent updates to the GitHub issue may trigger the creation of a new JIRA issue to ensure continuity of tracking.
- **Manual Links**: It's important to note that Remote Issue Links created manually for GitHub issues won't contain the necessary globalID. Since JIRA's search functionality for Remote Issue Links relies exclusively on globalID and not the URL, such manually created links cannot facilitate automated syncing.

This design ensures that the integration between GitHub and JIRA remains dynamic and adaptable to changes, providing a robust solution for tracking issues across both platforms.

## Manually Linking a GitHub Issue to JIRA

Creating a Remote Issue Link with the appropriate `globalID` directly through the JIRA Web UI is not feasible without leveraging the JIRA API. However, you can manually establish a connection between an existing GitHub issue and a JIRA issue by following these steps:

### Step-by-Step Guide

1. **Verify Unique Linking**: Ensure that the GitHub issue is not already linked to another JIRA issue. Use JIRA's advanced search with the query `issue in issuesWithRemoteLinksByGlobalId("GitHub Issue URL")` to check for existing links.
2. **Update JIRA Issue Description**: Include the URL of the GitHub issue in the description field of the JIRA issue. This step is crucial for the GitHub action to recognize and link the issues.
3. **Amend GitHub Issue Title**: Append the JIRA issue key to the end of the GitHub issue title within parentheses, e.g., `GitHub Issue title (JIRAKEY-123)`. This modification helps in identifying the linked issues easily.

### Automation Trigger

Upon the next update to the GitHub issue (which might occur immediately if you follow the steps sequentially), the GitHub action will automatically generate the "Synced from" link, establishing a manual link between the issues.

### Important Note

If the GitHub issue URL is not present in the JIRA issue description, the GitHub action will not create a link. This safeguard is designed to prevent unauthorized or unintended updates to JIRA issues from external sources.

## Issue Type Synchronization

The GitHub to JIRA Issue Sync Action intelligently creates JIRA issues with specific types based on the labels attached to the GitHub issue. This feature ensures that the issue types in JIRA accurately reflect the nature or category of the issue as determined in GitHub.

### How It Works

- **Label Matching**: When a new GitHub issue is created, the action checks for labels that either directly match the name of a JIRA issue type or follow the format `Type: <issue type>`. The search for matching labels is case insensitive, ensuring flexibility in label naming conventions.
- **Environment Variable Fallback**: In cases where no labels match any issue type, the action refers to the `JIRA_ISSUE_TYPE` environment variable to determine the issue type for the new JIRA issue. If this environment variable is not defined, the default issue type used is "Task".
- **Handling Label Changes**: If the labels on a GitHub issue are modified after creation, these changes will not alter the issue type of the already created JIRA issue. This limitation arises from the [inability of the JIRA REST API to safely change an issue type](https://jira.atlassian.com/browse/JRACLOUD-68207) when the new type is associated with a different workflow. In such scenarios, the action will leave a comment in the JIRA issue to inform about the label change in GitHub.

## Limitations

There are certain limitations to the data and events that can be synchronized:

### What's Not Synced

- **Labels**: The action does not sync labels between GitHub and JIRA, with the exception of labels that match JIRA issue types. This means that general labels used for categorization or prioritization in GitHub won't automatically reflect in JIRA.
- **Transitions**: Changes in the status of a GitHub issue, such as closing, reopening, or deleting, do not automatically result in the corresponding transition of the JIRA issue's status. Instead, these actions result in a comment being added to the linked JIRA issue to record the event. This design choice accounts for scenarios where a GitHub issue might be closed by its reporter, but the underlying problem it documents still requires attention and resolution within the JIRA project. Note that pull request review events (approvals, change requests) _do_ trigger JIRA status transitions — see [PR Review Status Sync](#syncing-pull-request-review-status-to-jira).

## Usage Instructions for GitHub to JIRA Issue Sync Action

This GitHub Action provides a comprehensive solution for integrating GitHub with JIRA, ensuring that issues, comments, and pull requests in GitHub are seamlessly synced to JIRA. Below are the setups to synchronize different types of activities from GitHub to JIRA.

### Syncing New Issues to JIRA

Automatically creates a corresponding JIRA issue when a new issue is opened in GitHub.

```yaml
name: Sync issues to Jira

on: issues

concurrency:
  group: jira-sync-${{ github.event.issue.number }}
  cancel-in-progress: true

jobs:
  sync_issues_to_jira:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      issues: write
    steps:
      - uses: actions/checkout@v4

      - name: Sync GitHub issues to Jira project
        uses: ciscoecosystem/sync-jira-actions@v1
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          JIRA_PASS: ${{ secrets.JIRA_PASS }}
          JIRA_PROJECT: SOMEPROJECT # define the JIRA project here
          JIRA_COMPONENT: SOMECOMPONENT # define (optional) JIRA component here
          JIRA_URL: ${{ secrets.JIRA_URL }}
          JIRA_USER: ${{ secrets.JIRA_USER }}
```

### Syncing New Issue Comments to JIRA

Ensures that comments made on GitHub issues are also reflected in the corresponding JIRA issue.

```yaml
name: Sync issue comments to JIRA

on: issue_comment

concurrency:
  group: jira-sync-comment-${{ github.event.issue.number }}
  cancel-in-progress: true

jobs:
  sync_issue_comments_to_jira:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      issues: write
    steps:
      - uses: actions/checkout@v4

      - name: Sync GitHub issue comments to Jira project
        uses: ciscoecosystem/sync-jira-actions@v1
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          JIRA_PASS: ${{ secrets.JIRA_PASS }}
          JIRA_PROJECT: SOMEPROJECT
          JIRA_URL: ${{ secrets.JIRA_URL }}
          JIRA_USER: ${{ secrets.JIRA_USER }}
```

### Syncing New Pull Requests to JIRA

There are two approaches for syncing pull requests, depending on your security requirements.

#### Option A — `pull_request_target` (recommended for forks)

The `pull_request_target` event runs with repository secrets but executes the base-branch workflow, making it safe for fork PRs **as long as you do not check out and execute the PR code** (see [Security](#security)).

```yaml
name: Sync PRs to Jira

on:
  pull_request_target:
    types: [opened, edited, closed, reopened, labeled, unlabeled]

concurrency:
  group: jira-sync-pr-${{ github.event.pull_request.number }}
  cancel-in-progress: true

jobs:
  sync_prs_to_jira:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      issues: write
      pull-requests: write
    steps:
      - uses: actions/checkout@v4

      - name: Sync PRs to Jira project
        uses: ciscoecosystem/sync-jira-actions@v1
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          JIRA_PASS: ${{ secrets.JIRA_PASS }}
          JIRA_PROJECT: SOMEPROJECT # define the JIRA project here
          JIRA_COMPONENT: SOMECOMPONENT # define (optional) JIRA component here
          JIRA_URL: ${{ secrets.JIRA_URL }}
          JIRA_USER: ${{ secrets.JIRA_USER }}
```

#### Option B — Cron job catch-up

A scheduled cron job can catch any PRs that were missed by event-driven workflows. This approach scans all open PRs and creates JIRA issues for any that are not yet synced.

```yaml
name: Sync remaining PRs to Jira

on:
  schedule:
    - cron: "0 * * * *"

concurrency:
  group: jira-sync-cron-${{ github.repository }}
  cancel-in-progress: true

jobs:
  sync_prs_to_jira:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      issues: write
      pull-requests: write
    steps:
      - uses: actions/checkout@v4

      - name: Sync PRs to Jira project
        uses: ciscoecosystem/sync-jira-actions@v1
        with:
          cron_job: true
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          JIRA_PASS: ${{ secrets.JIRA_PASS }}
          JIRA_PROJECT: SOMEPROJECT # define the JIRA project here
          JIRA_COMPONENT: SOMECOMPONENT # define (optional) JIRA component here
          JIRA_URL: ${{ secrets.JIRA_URL }}
          JIRA_USER: ${{ secrets.JIRA_USER }}
```

### Syncing Pull Request Review Status to JIRA

When a PR linked to a JIRA issue receives reviews, the action can automatically transition the JIRA issue between workflow states. This uses the `workflow_run` event triggered by `pull_request_review`.

The minimum number of approvals required before the JIRA issue transitions to "Reviewer Approved" is controlled by the `minimum_approvals` input (default: `3`).

```yaml
name: Sync PR review status to Jira

on:
  workflow_run:
    workflows: ["<name-of-your-pr-workflow>"]
    types: [completed]

concurrency:
  group: jira-sync-review-${{ github.event.workflow_run.id }}
  cancel-in-progress: true

jobs:
  sync_pr_review_to_jira:
    if: github.event.workflow_run.event == 'pull_request_review'
    runs-on: ubuntu-latest
    permissions:
      contents: read
      issues: write
      pull-requests: write
    steps:
      - uses: actions/checkout@v4

      - name: Sync PR review status to Jira
        uses: ciscoecosystem/sync-jira-actions@v1
        with:
          minimum_approvals: 3
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          JIRA_PASS: ${{ secrets.JIRA_PASS }}
          JIRA_PROJECT: SOMEPROJECT
          JIRA_URL: ${{ secrets.JIRA_URL }}
          JIRA_USER: ${{ secrets.JIRA_USER }}
```

### Using a Sync Label to Gate Syncing

When you only want to sync issues or PRs that have been explicitly approved by a maintainer, use the `sync_label` input together with a job-level `if:` gate. The `if:` guard prevents the job from running at all on unlabeled events (saving runner time and reducing secret exposure), while `sync_label` acts as a second check inside the action itself.

```yaml
name: Sync labeled issues to Jira

on:
  issues:
    types: [opened, edited, closed, reopened, labeled, unlabeled]
  pull_request_target:
    types: [opened, edited, closed, reopened, labeled, unlabeled]

concurrency:
  group: jira-sync-${{ github.event.issue.number || github.event.pull_request.number }}
  cancel-in-progress: true

jobs:
  sync_to_jira:
    # Only run when the sync label is present – avoids executing with secrets on every event
    if: |
      contains(github.event.issue.labels.*.name, 'sync-to-jira') ||
      contains(github.event.pull_request.labels.*.name, 'sync-to-jira')
    runs-on: ubuntu-latest
    permissions:
      contents: read
      issues: write
      pull-requests: write
    steps:
      - uses: actions/checkout@v4

      - name: Sync to Jira project
        uses: ciscoecosystem/sync-jira-actions@v1
        with:
          sync_label: sync-to-jira
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          JIRA_PASS: ${{ secrets.JIRA_PASS }}
          JIRA_PROJECT: SOMEPROJECT
          JIRA_URL: ${{ secrets.JIRA_URL }}
          JIRA_USER: ${{ secrets.JIRA_USER }}
```

## Manually Syncing Issues and Pull Requests to JIRA

For cases where you need to manually sync issues and pull requests that were not automatically captured by the [Sync a new issue to Jira](#sync-a-new-issue-to-jira) and [Sync a new pull request to Jira](#sync-a-new-pull-request-to-jira) workflows, this GitHub Action provides a solution. It allows for the manual synchronization of both new and old issues and pull requests directly to your JIRA project.

### Configuration for Manual Sync

This action introduces two parameters for manual triggering:

- `action`: Specifies the action to be performed, with a default value of `mirror-issues`.
- `issue-numbers`: Lists the numbers of the issues and pull requests that you wish to sync to JIRA.

### Workflow Setup

To set up the manual sync action, include the following workflow in your GitHub repository:

```yaml
name: Manually trigger sync issue to Jira

on:
  workflow_dispatch:
    inputs:
      action:
        description: "Action to be performed"
        required: true
        default: "mirror-issues"
      issue-numbers:
        description: "Issue numbers"
        required: true

concurrency:
  group: jira-sync-manual-${{ github.run_id }}
  cancel-in-progress: true

jobs:
  sync_issues_to_jira:
    name: Sync issues to Jira
    runs-on: ubuntu-latest
    permissions:
      contents: read
      issues: write
      pull-requests: write
    steps:
      - uses: actions/checkout@v4

      - name: Sync GitHub issues to Jira project
        uses: ciscoecosystem/sync-jira-actions@v1
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          JIRA_PASS: ${{ secrets.JIRA_PASS }}
          JIRA_PROJECT: SOMEPROJECT # define the JIRA project here
          JIRA_COMPONENT: SOMECOMPONENT # define (optional) JIRA component here
          JIRA_URL: ${{ secrets.JIRA_URL }}
          JIRA_USER: ${{ secrets.JIRA_USER }}
```

This workflow can be triggered manually from the GitHub Actions tab in your repository, allowing you to specify the issues or pull requests to be synced by entering their numbers.

This ensures that even items not caught by the automatic sync process can still be integrated into your JIRA project for tracking and management.

## Environment Variables and Secrets Configuration

The GitHub to JIRA Issue Sync workflow requires the configuration of specific environment variables and secrets to operate effectively. These settings ensure the correct creation and updating of issues within your JIRA project based on activities in your GitHub repository.

Below is a detailed table outlining the necessary environment variable configurations:

| Variable/Secret   | Description                                                                                  | Requirement |
| ----------------- | -------------------------------------------------------------------------------------------- | ----------- |
| `JIRA_PROJECT`    | The slug of the JIRA project where new issues will be created.                               | Mandatory   |
| `JIRA_URL`        | The main URL of your JIRA instance.                                                          | Inherited   |
| `JIRA_USER`       | The username used for logging into JIRA (basic auth).                                        | Inherited   |
| `JIRA_PASS`       | The JIRA token (for token auth) or password (for basic auth) used for logging in.            | Inherited   |
| `JIRA_ISSUE_TYPE` | Specifies the JIRA issue type for new issues. Defaults to "Task" if not set.                 | Optional    |
| `JIRA_COMPONENT`  | The name of a JIRA component to add to every synced issue. The component must exist in JIRA. | Optional    |

### Action Inputs

The following inputs are passed via the `with:` block in your workflow step:

| Input                | Default | Description                                                                                                                                  |
| -------------------- | ------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| `cron_job`           | —       | Set to `true` to run in cron mode, which scans all open PRs and creates JIRA issues for any that have not yet been synced.                   |
| `sync_label`         | —       | When set, only issues and PRs that carry this label will be synced to JIRA. All others are silently skipped.                                  |
| `link_closing_issues`| —       | When set, finds GitHub issues that a PR will close, appends the JIRA key to the PR title, and drives JIRA transitions based on review status. |
| `minimum_approvals`  | `3`     | Minimum number of PR approvals required before the linked JIRA issue transitions to the "Reviewer Approved" state.                           |
| `status_field_id`    | `12100` | The custom field ID of the "GitHub Issue Status" field in JIRA. Override if your JIRA instance uses a different field ID.                    |
| `find_jira_retries`  | `5`     | Number of times the action retries looking up the JIRA issue before deciding to create a new one. Helps avoid race conditions.               |

### Important Consideration:

- **GitHub Organizational Secrets**: `JIRA_URL`, `JIRA_USER`, `JIRA_PASS` - These secrets are **inherited from the GitHub organizational secrets, as they are common to all projects within the organization**. It is advised not to set these secrets at the individual repository level to avoid conflicts and ensure a unified configuration across all projects.

- **Token as JIRA_PASS**: When using a token for `JIRA_PASS`, prefix the token value with `token:` (e.g., `token:Xyz123**************ABC`). This prefix helps distinguish between password and token types, and it will be removed by the script before making the API call.

---

## Security

This action runs with `GITHUB_TOKEN` and Jira secrets (`JIRA_URL`, `JIRA_USER`, `JIRA_PASS`) in scope. Follow these guidelines to keep your workflows secure.

### Never interpolate workflow outputs into `run:` steps

Workflow outputs (e.g., issue titles or PR bodies) can contain attacker-controlled content. Never interpolate them directly into shell commands:

```yaml
# ❌ Dangerous – attacker-controlled content reaches the shell
- run: echo "${{ github.event.issue.title }}"

# ✅ Safe – pass via an environment variable
- run: echo "$ISSUE_TITLE"
  env:
    ISSUE_TITLE: ${{ github.event.issue.title }}
```

### Do not check out and run untrusted PR code in the same job

Under `pull_request_target`, the workflow runs with full access to repository secrets. **Never** check out the PR head ref and then execute it (build, test, lint, etc.) in the same job — this lets fork authors run arbitrary code with your secrets:

```yaml
# ❌ Dangerous – fork-controlled code executes with secrets in scope
- uses: actions/checkout@v4
  with:
    ref: ${{ github.event.pull_request.head.sha }}
- run: npm install && npm test
```

### Use least-privilege permissions

Add an explicit `permissions:` block to every workflow job to limit the `GITHUB_TOKEN` scope to only what is required:

```yaml
permissions:
  contents: read
  issues: write
  pull-requests: write
```

### Gate on a trusted label

Add a job-level `if:` condition so the workflow does not run with secrets unless a maintainer has applied the sync label. This is more efficient and safer than relying solely on the `sync_label` input inside the action, because the job never starts — and secrets are never loaded — on unlabeled events.

```yaml
jobs:
  sync_to_jira:
    if: |
      contains(github.event.issue.labels.*.name, 'sync-to-jira') ||
      contains(github.event.pull_request.labels.*.name, 'sync-to-jira')
```

Pair this with the `sync_label` input as a defence-in-depth second check inside the action:

```yaml
      - uses: ciscoecosystem/sync-jira-actions@v1
        with:
          sync_label: sync-to-jira
```

See [Using a Sync Label to Gate Syncing](#using-a-sync-label-to-gate-syncing) for a complete workflow example.

### Use per-item concurrency with `cancel-in-progress`

A single global concurrency group serialises all events into one queue, which can cause a large backlog during event floods. Use a per-issue or per-PR group and cancel superseded runs instead:

```yaml
concurrency:
  group: jira-sync-${{ github.event.issue.number || github.event.pull_request.number }}
  cancel-in-progress: true
```

### Pin to a commit SHA

Referencing a mutable tag (e.g. `@v1`) means a supply-chain compromise of this action could silently affect your workflows. Pin to a specific immutable commit SHA instead:

```yaml
# ✅ Pinned to a specific commit SHA
- uses: ciscoecosystem/sync-jira-actions@<commit-sha>
```

Find the commit SHA for the latest release on the [Releases page](https://github.com/ciscoecosystem/sync-jira-actions/releases).

### Trim `pull_request_target` activity types

The `pull_request_target` event fires on many activity types by default. Restrict it to only the types this action handles to reduce the unnecessary trigger surface:

```yaml
on:
  pull_request_target:
    types: [opened, edited, closed, reopened, labeled, unlabeled]
```

---

## Project Issues

If you encounter any issues, feel free to report them in the project's issues or create Pull Request with your suggestion.

## Contributing

📘 If you are interested in contributing to this project, see the [project Contributing Guide](CONTRIBUTING.md).
