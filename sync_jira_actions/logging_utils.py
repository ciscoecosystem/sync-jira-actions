#!/usr/bin/env python3
#
# Copyright: (c) 2026, Samita Bhattacharjee (@samiib) <samitab@cisco.com>
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

# Patterns targeting user-pasted secrets. GitHub-managed secrets (GITHUB_TOKEN,
# JIRA_PASS, etc.) are already redacted automatically by the Actions runner.
_REDACT_PATTERNS = [
    # GitHub personal access tokens, fine-grained tokens, and App tokens
    (re.compile(r'gh[pousra]_[A-Za-z0-9]+'), '[REDACTED_GH_TOKEN]'),
    (re.compile(r'ghs_[A-Za-z0-9]+'), '[REDACTED_GH_TOKEN]'),
    # AWS access key IDs
    (re.compile(r'AKIA[0-9A-Z]{16}'), '[REDACTED_AWS_KEY]'),
    # PEM private key blocks (single- or multi-line)
    (re.compile(r'-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----', re.DOTALL),
     '[REDACTED_PRIVATE_KEY]'),
    # Generic token/secret/key assignments (e.g. token=abc123, secret: xyz)
    (re.compile(r'(?i)\b(token|secret|key)\s*[=:]\s*\S+'), r'\1=[REDACTED]'),
]


def is_debug() -> bool:
    """Return True when GitHub Actions runner debug logging is enabled.

    Set ``ACTIONS_RUNNER_DEBUG: true`` in your workflow ``env:`` block to
    enable verbose payload logging. See README for caveats around public repos.
    """
    return os.environ.get('ACTIONS_RUNNER_DEBUG') == 'true'


def redact(text: str) -> str:
    """Apply redaction patterns to a string before writing it to the log.

    Targets user-pasted secret patterns that GitHub's built-in ``secrets.*``
    redaction does not cover (it only redacts exact matches of registered
    secrets, not derived or typed values).
    """
    if not text:
        return text
    for pattern, replacement in _REDACT_PATTERNS:
        text = pattern.sub(replacement, text)
    return text
