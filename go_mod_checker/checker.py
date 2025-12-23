"""Module for parsing go.mod files and checking module status."""

import os
import re
import requests
from datetime import datetime, timedelta
from typing import List, Tuple, Optional
from dataclasses import dataclass, field
from packaging import version


# Default timeout for HTTP requests in seconds
DEFAULT_TIMEOUT = 10


@dataclass
class Module:
    """Represents a Go module dependency."""
    name: str
    version: str
    is_indirect: bool = False


@dataclass
class ModuleCheckResult:
    """Result of checking a module's status."""
    status: str  # 'ARCHIVED', 'OUTDATED', 'OK'
    latest_version: Optional[str]
    contributor_count: Optional[int] = None
    last_updated: Optional[str] = None  # ISO date string
    warnings: List[str] = field(default_factory=list)


class GoModParser:
    """Parser for go.mod files."""

    def __init__(self, filepath: str = "go.mod"):
        """Initialize the parser with a go.mod file path."""
        self.filepath = filepath

    def parse(self) -> List[Module]:
        """Parse the go.mod file and return list of direct dependencies."""
        modules = []

        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                content = f.read()
        except FileNotFoundError:
            raise FileNotFoundError(f"go.mod file not found at {self.filepath}")

        # Parse require block
        in_require = False
        for line in content.split('\n'):
            line = line.strip()

            # Skip comments
            if line.startswith('//'):
                continue

            # Check for require block
            if line.startswith('require ('):
                in_require = True
                continue
            elif line == ')' and in_require:
                in_require = False
                continue

            # Parse single require statement
            if line.startswith('require '):
                match = re.match(r'require\s+(\S+)\s+(\S+)(\s+//\s*indirect)?', line)
                if match:
                    name = match.group(1)
                    version = match.group(2)
                    is_indirect = match.group(3) is not None
                    if not is_indirect:  # Only add direct dependencies
                        modules.append(Module(name, version, is_indirect))

            # Parse require block lines
            elif in_require:
                match = re.match(r'(\S+)\s+(\S+)(\s+//\s*indirect)?', line)
                if match:
                    name = match.group(1)
                    version = match.group(2)
                    is_indirect = match.group(3) is not None
                    if not is_indirect:  # Only add direct dependencies
                        modules.append(Module(name, version, is_indirect))

        return modules


class ModuleChecker:
    """Checker for Go module status."""

    def __init__(self, timeout: int = DEFAULT_TIMEOUT):
        """
        Initialize the module checker.

        Args:
            timeout: Timeout in seconds for HTTP requests (default: 10)
        """
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'go-mod-checker/0.1.0'
        })
        self.timeout = timeout

        # Add GitHub token authentication if available
        github_token = os.environ.get('GITHUB_TOKEN')
        if github_token:
            self.session.headers.update({
                'Authorization': f'token {github_token}'
            })

    def check_module(self, module: Module) -> ModuleCheckResult:
        """
        Check if a module is archived, outdated, or OK.

        Returns:
            ModuleCheckResult with status, latest_version, and additional info
        """
        # Check if module is on GitHub by validating the full path structure
        # Go module paths on GitHub always have the format: github.com/owner/repo[/subpath]
        parts = module.name.split('/')
        if len(parts) >= 3 and parts[0] == 'github.com':
            return self._check_github_module(module)
        else:
            # For non-GitHub modules, use Go proxy
            return self._check_proxy_module(module)

    def _is_version_outdated(self, current: str, latest: str) -> bool:
        """
        Compare two version strings to determine if current is outdated.

        Handles semantic versioning properly, including versions with 'v' prefix.
        Returns True if latest is newer than current.
        """
        try:
            # Remove 'v' prefix if present for comparison
            current_clean = current.lstrip('v')
            latest_clean = latest.lstrip('v')

            current_ver = version.parse(current_clean)
            latest_ver = version.parse(latest_clean)

            return latest_ver > current_ver
        except (version.InvalidVersion, AttributeError):
            # Fall back to string comparison if version parsing fails
            return latest != current

    def _check_github_module(self, module: Module) -> ModuleCheckResult:
        """Check GitHub-hosted module status."""
        # Extract owner and repo from module name
        parts = module.name.split('/')

        owner = parts[1]
        repo = parts[2]

        result = ModuleCheckResult(status='OK', latest_version=None)

        # Get repository information
        api_url = f"https://api.github.com/repos/{owner}/{repo}"
        try:
            response = self.session.get(api_url, timeout=self.timeout)
            if response.status_code == 200:
                content_type = response.headers.get('content-type', '')
                if 'application/json' in content_type:
                    try:
                        data = response.json()
                        if data.get('archived', False):
                            result.status = 'ARCHIVED'
                            return result

                        # Store last updated date
                        result.last_updated = data.get('updated_at')

                        # Check if last update was more than 6 months ago
                        if result.last_updated:
                            try:
                                updated_date = datetime.fromisoformat(result.last_updated.replace('Z', '+00:00'))
                                six_months_ago = datetime.now(updated_date.tzinfo) - timedelta(days=180)
                                if updated_date < six_months_ago:
                                    result.warnings.append("Repository not updated in >6 months")
                            except (ValueError, TypeError):
                                pass  # Invalid date format, skip warning

                    except ValueError:
                        # Invalid JSON, continue to version check
                        pass
            # Note: 404 means repository not found, not necessarily archived
            # We skip the archived check and proceed to version checking
        except requests.RequestException:
            # If we can't check, assume OK
            pass

        # Get contributor count
        contributors_url = f"https://api.github.com/repos/{owner}/{repo}/contributors?per_page=100"
        try:
            response = self.session.get(contributors_url, timeout=self.timeout)
            if response.status_code == 200:
                data = response.json()
                contributor_count = len(data)

                # Check if there are more pages (GitHub limits to 500 contributors)
                link_header = response.headers.get('Link', '')
                if 'rel="next"' in link_header:
                    # There are more contributors, set to a high number to indicate many contributors
                    contributor_count = 500  # GitHub's max

                result.contributor_count = contributor_count

                # Check if less than 3 contributors
                if result.contributor_count < 3:
                    result.warnings.append(f"Repository has only {result.contributor_count} contributor(s)")

        except requests.RequestException:
            # If we can't check contributors, skip this warning
            pass

        # Check for latest version
        latest_version = self._get_latest_version(module.name)
        if latest_version and self._is_version_outdated(module.version, latest_version):
            result.status = 'OUTDATED'
            result.latest_version = latest_version

        return result

    def _check_proxy_module(self, module: Module) -> ModuleCheckResult:
        """Check module status using Go proxy."""
        result = ModuleCheckResult(status='OK', latest_version=None)
        latest_version = self._get_latest_version(module.name)
        if latest_version and self._is_version_outdated(module.version, latest_version):
            result.status = 'OUTDATED'
            result.latest_version = latest_version

        return result

    def _get_latest_version(self, module_name: str) -> Optional[str]:
        """Get the latest version of a module from Go proxy."""
        # Use Go proxy to get latest version
        proxy_url = f"https://proxy.golang.org/{module_name}/@latest"
        try:
            response = self.session.get(proxy_url, timeout=self.timeout)
            if response.status_code == 200:
                content_type = response.headers.get('content-type', '')
                if 'application/json' in content_type:
                    try:
                        data = response.json()
                        return data.get('Version')
                    except ValueError:
                        pass  # Invalid JSON
        except requests.RequestException:
            # Network error or invalid response; unable to fetch latest version, so return None.
            pass

        return None
