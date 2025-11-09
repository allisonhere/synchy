"""Interactive CLI mode."""

import sys
from typing import Optional, List, Callable
from src.utils.paths import get_firefox_profiles, get_chrome_profiles
from src.core.sync_engine import SyncDirection, SyncMode
from src.core.merger import MergeStrategy


def prompt_yes_no(question: str, default: bool = True) -> bool:
    """
    Prompt user for yes/no answer.
    
    Args:
        question: Question to ask
        default: Default value
        
    Returns:
        True for yes, False for no
    """
    default_str = "Y/n" if default else "y/N"
    while True:
        response = input(f"{question} [{default_str}]: ").strip().lower()
        if not response:
            return default
        if response in ['y', 'yes']:
            return True
        if response in ['n', 'no']:
            return False
        print("Please enter 'y' or 'n'")


def prompt_choice(question: str, choices: List[str], default: Optional[int] = None) -> int:
    """
    Prompt user to choose from a list.
    
    Args:
        question: Question to ask
        choices: List of choice strings
        default: Default choice index (None for no default)
        
    Returns:
        Selected choice index
    """
    print(f"\n{question}")
    for i, choice in enumerate(choices, 1):
        marker = " (default)" if default == i - 1 else ""
        print(f"  {i}. {choice}{marker}")
    
    while True:
        try:
            response = input(f"\nEnter choice [1-{len(choices)}]: ").strip()
            if not response and default is not None:
                return default
            choice_num = int(response)
            if 1 <= choice_num <= len(choices):
                return choice_num - 1
            print(f"Please enter a number between 1 and {len(choices)}")
        except ValueError:
            print("Please enter a valid number")


def prompt_text(question: str, default: Optional[str] = None, validator: Optional[Callable[[str], bool]] = None) -> str:
    """
    Prompt user for text input.
    
    Args:
        question: Question to ask
        default: Default value
        validator: Optional validation function
        
    Returns:
        User input string
    """
    default_str = f" [{default}]" if default else ""
    while True:
        response = input(f"{question}{default_str}: ").strip()
        if not response:
            if default:
                return default
            print("Please enter a value")
            continue
        
        if validator and not validator(response):
            continue
        
        return response


def interactive_sync() -> dict:
    """
    Interactive sync configuration.
    
    Returns:
        Dict with sync configuration
    """
    print("\n=== Bookmark Sync - Interactive Mode ===\n")
    
    # Get profiles
    firefox_profiles = get_firefox_profiles()
    chrome_profiles = get_chrome_profiles()
    
    if not firefox_profiles:
        print("ERROR: No Firefox profiles found!")
        sys.exit(1)
    
    if not chrome_profiles:
        print("ERROR: No Chrome profiles found!")
        sys.exit(1)
    
    # Select Firefox profile
    firefox_names = [p['name'] for p in firefox_profiles]
    firefox_idx = prompt_choice(
        "Select Firefox profile:",
        firefox_names,
        default=0
    )
    firefox_profile = firefox_names[firefox_idx]
    
    # Select Chrome profile
    chrome_names = [p['name'] for p in chrome_profiles]
    chrome_idx = prompt_choice(
        "Select Chrome profile:",
        chrome_names,
        default=0
    )
    chrome_profile = chrome_names[chrome_idx]
    
    # Select sync direction
    direction_choices = [
        "Firefox → Chrome (one-way)",
        "Chrome → Firefox (one-way)",
        "Firefox ↔ Chrome (bidirectional merge)"
    ]
    direction_idx = prompt_choice(
        "Select sync direction:",
        direction_choices,
        default=2
    )
    
    direction_map = {
        0: SyncDirection.FIREFOX_TO_CHROME,
        1: SyncDirection.CHROME_TO_FIREFOX,
        2: SyncDirection.BIDIRECTIONAL
    }
    direction = direction_map[direction_idx]
    
    # Select sync mode (if bidirectional)
    sync_mode = SyncMode.FULL
    if direction == SyncDirection.BIDIRECTIONAL:
        mode_choices = [
            "Full sync (replace all)",
            "Incremental sync (only changes)",
            "Merge sync (combine both)"
        ]
        mode_idx = prompt_choice(
            "Select sync mode:",
            mode_choices,
            default=2
        )
        sync_mode = [SyncMode.FULL, SyncMode.INCREMENTAL, SyncMode.MERGE][mode_idx]
    
    # Select merge strategy (if merge mode)
    merge_strategy = MergeStrategy.KEEP_ALL
    if sync_mode == SyncMode.MERGE or direction == SyncDirection.BIDIRECTIONAL:
        strategy_choices = [
            "Keep all (rename duplicates)",
            "Keep newer (timestamp-based)",
            "Firefox priority",
            "Chrome priority",
            "Smart merge"
        ]
        strategy_idx = prompt_choice(
            "Select merge strategy:",
            strategy_choices,
            default=0
        )
        strategies = [
            MergeStrategy.KEEP_ALL,
            MergeStrategy.TIMESTAMP,
            MergeStrategy.FIREFOX_PRIORITY,
            MergeStrategy.CHROME_PRIORITY,
            MergeStrategy.SMART
        ]
        merge_strategy = strategies[strategy_idx]
    
    # Backup option
    backup_before_sync = prompt_yes_no("Backup before syncing?", default=True)
    
    # Dry run option
    dry_run = prompt_yes_no("Dry run (preview changes only)?", default=True)
    
    return {
        "firefox_profile": firefox_profile,
        "chrome_profile": chrome_profile,
        "direction": direction,
        "sync_mode": sync_mode,
        "merge_strategy": merge_strategy,
        "backup_before_sync": backup_before_sync,
        "dry_run": dry_run
    }


def interactive_config_wizard() -> dict:
    """
    Configuration wizard for first-time setup.
    
    Returns:
        Configuration dict
    """
    print("\n=== Bookmark Sync - Configuration Wizard ===\n")
    print("This wizard will help you set up bookmark sync for the first time.\n")
    
    # Get profiles
    firefox_profiles = get_firefox_profiles()
    chrome_profiles = get_chrome_profiles()
    
    if not firefox_profiles:
        print("WARNING: No Firefox profiles found!")
        firefox_profile = None
    else:
        firefox_names = [p['name'] for p in firefox_profiles]
        if len(firefox_names) == 1:
            firefox_profile = firefox_names[0]
            print(f"Using Firefox profile: {firefox_profile}")
        else:
            firefox_idx = prompt_choice(
                "Select Firefox profile:",
                firefox_names,
                default=0
            )
            firefox_profile = firefox_names[firefox_idx]
    
    if not chrome_profiles:
        print("WARNING: No Chrome profiles found!")
        chrome_profile = None
    else:
        chrome_names = [p['name'] for p in chrome_profiles]
        if len(chrome_names) == 1:
            chrome_profile = chrome_names[0]
            print(f"Using Chrome profile: {chrome_profile}")
        else:
            chrome_idx = prompt_choice(
                "Select Chrome profile:",
                chrome_names,
                default=0
            )
            chrome_profile = chrome_names[chrome_idx]
    
    # Default sync settings
    print("\n=== Default Sync Settings ===")
    
    sync_mode_choices = ["Full sync", "Incremental sync", "Merge sync"]
    sync_mode_idx = prompt_choice(
        "Default sync mode:",
        sync_mode_choices,
        default=2
    )
    sync_mode = ["full", "incremental", "merge"][sync_mode_idx]
    
    merge_strategy_choices = [
        "Keep all (rename duplicates)",
        "Keep newer (timestamp-based)",
        "Firefox priority",
        "Chrome priority",
        "Smart merge"
    ]
    merge_strategy_idx = prompt_choice(
        "Default merge strategy:",
        merge_strategy_choices,
        default=0
    )
    merge_strategy = ["keep_all", "timestamp", "firefox_priority", "chrome_priority", "smart"][merge_strategy_idx]
    
    backup_before_sync = prompt_yes_no("Always backup before sync?", default=True)
    
    config = {
        "firefox": {
            "profile": firefox_profile,
            "auto_detect": True
        },
        "chrome": {
            "profile": chrome_profile,
            "auto_detect": True
        },
        "sync": {
            "sync_mode": sync_mode,
            "merge_strategy": merge_strategy,
            "backup_before_sync": backup_before_sync
        },
        "backup": {
            "directory": "./backups",
            "retention_days": 30
        }
    }
    
    print("\n=== Configuration Summary ===")
    print(f"Firefox profile: {firefox_profile or 'Not found'}")
    print(f"Chrome profile: {chrome_profile or 'Not found'}")
    print(f"Sync mode: {sync_mode}")
    print(f"Merge strategy: {merge_strategy}")
    print(f"Backup before sync: {backup_before_sync}")
    
    if prompt_yes_no("\nSave this configuration?", default=True):
        return config
    else:
        return None
