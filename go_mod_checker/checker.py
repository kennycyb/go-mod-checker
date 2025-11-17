"""Module for parsing go.mod files and checking module status."""

import re
import requests
from typing import List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class Module:
    """Represents a Go module dependency."""
    name: str
    version: str
    is_indirect: bool = False


class GoModParser:
    """Parser for go.mod files."""
    
    def __init__(self, filepath: str = "go.mod"):
        """Initialize the parser with a go.mod file path."""
        self.filepath = filepath
    
    def parse(self) -> List[Module]:
        """Parse the go.mod file and return list of direct dependencies."""
        modules = []
        
        try:
            with open(self.filepath, 'r') as f:
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
    
    def __init__(self):
        """Initialize the module checker."""
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'go-mod-checker/0.1.0'
        })
    
    def check_module(self, module: Module) -> Tuple[str, Optional[str]]:
        """
        Check if a module is archived, outdated, or OK.
        
        Returns:
            Tuple of (status, latest_version) where status is 'ARCHIVED', 'OUTDATED', or 'OK'
        """
        # Check if module is on GitHub by validating the full path structure
        # Go module paths on GitHub always have the format: github.com/owner/repo[/subpath]
        parts = module.name.split('/')
        if len(parts) >= 3 and parts[0] == 'github.com':
            return self._check_github_module(module)
        else:
            # For non-GitHub modules, use Go proxy
            return self._check_proxy_module(module)
    
    def _check_github_module(self, module: Module) -> Tuple[str, Optional[str]]:
        """Check GitHub-hosted module status."""
        # Extract owner and repo from module name
        parts = module.name.split('/')
        
        owner = parts[1]
        repo = parts[2]
        
        # Check if repository is archived
        api_url = f"https://api.github.com/repos/{owner}/{repo}"
        try:
            response = self.session.get(api_url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('archived', False):
                    return 'ARCHIVED', None
            elif response.status_code == 404:
                return 'ARCHIVED', None  # Repo not found, treat as archived
        except requests.RequestException:
            # If we can't check, assume OK
            pass
        
        # Check for latest version
        latest_version = self._get_latest_version(module.name)
        if latest_version and latest_version != module.version:
            return 'OUTDATED', latest_version
        
        return 'OK', None
    
    def _check_proxy_module(self, module: Module) -> Tuple[str, Optional[str]]:
        """Check module status using Go proxy."""
        latest_version = self._get_latest_version(module.name)
        if latest_version and latest_version != module.version:
            return 'OUTDATED', latest_version
        
        return 'OK', None
    
    def _get_latest_version(self, module_name: str) -> Optional[str]:
        """Get the latest version of a module from Go proxy."""
        # Use Go proxy to get latest version
        proxy_url = f"https://proxy.golang.org/{module_name}/@latest"
        try:
            response = self.session.get(proxy_url, timeout=10)
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
