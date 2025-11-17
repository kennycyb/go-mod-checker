"""Command-line interface for go-mod-checker."""

import sys
import argparse
from pathlib import Path
from colorama import init, Fore, Style

from .checker import GoModParser, ModuleChecker


def main():
    """Main entry point for the CLI."""
    # Initialize colorama for cross-platform colored output
    init(autoreset=True)
    
    parser = argparse.ArgumentParser(
        description='Check Go module dependencies status',
        prog='go-mod-checker'
    )
    parser.add_argument(
        'path',
        nargs='?',
        default='go.mod',
        help='Path to go.mod file (default: go.mod in current directory)'
    )
    parser.add_argument(
        '--version',
        action='version',
        version='%(prog)s 0.1.0'
    )
    
    args = parser.parse_args()
    
    # Check if go.mod file exists
    go_mod_path = Path(args.path)
    if not go_mod_path.exists():
        print(f"{Fore.RED}Error: go.mod file not found at {args.path}{Style.RESET_ALL}")
        sys.exit(1)
    
    # Parse go.mod file
    print(f"Checking dependencies in {args.path}...\n")
    parser = GoModParser(str(go_mod_path))
    
    try:
        modules = parser.parse()
    except Exception as e:
        print(f"{Fore.RED}Error parsing go.mod: {e}{Style.RESET_ALL}")
        sys.exit(1)
    
    if not modules:
        print(f"{Fore.YELLOW}No direct dependencies found in go.mod{Style.RESET_ALL}")
        return
    
    # Check each module
    checker = ModuleChecker()
    
    print(f"Found {len(modules)} direct dependencies:\n")
    
    archived_count = 0
    outdated_count = 0
    ok_count = 0
    
    for module in modules:
        status, latest_version = checker.check_module(module)
        
        if status == 'ARCHIVED':
            status_text = f"{Fore.RED}ARCHIVED{Style.RESET_ALL}"
            archived_count += 1
        elif status == 'OUTDATED':
            status_text = f"{Fore.YELLOW}OUTDATED{Style.RESET_ALL} (latest: {latest_version})"
            outdated_count += 1
        else:  # OK
            status_text = f"{Fore.GREEN}OK{Style.RESET_ALL}"
            ok_count += 1
        
        print(f"  {module.name} {module.version} - {status_text}")
    
    # Print summary
    print(f"\n{Fore.CYAN}Summary:{Style.RESET_ALL}")
    print(f"  {Fore.GREEN}✓{Style.RESET_ALL} OK: {ok_count}")
    print(f"  {Fore.YELLOW}⚠{Style.RESET_ALL} OUTDATED: {outdated_count}")
    print(f"  {Fore.RED}✗{Style.RESET_ALL} ARCHIVED: {archived_count}")
    
    # Exit with error code if there are issues
    if archived_count > 0 or outdated_count > 0:
        sys.exit(1)
    
    sys.exit(0)


if __name__ == '__main__':
    main()
