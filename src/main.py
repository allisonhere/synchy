#!/usr/bin/env python3
"""CLI interface for bookmark sync."""

import argparse
import json
import sys
from pathlib import Path
from src.core.sync_engine import SyncEngine, SyncDirection, SyncMode
from src.core.merger import MergeStrategy
from src.backup.backup_manager import BackupManager
from src.backup.restore_manager import RestoreManager
from src.utils.paths import get_firefox_profiles, get_chrome_profiles
from src.utils.logger import setup_logger
from src.ui.interactive import interactive_sync, interactive_config_wizard
from src.ui.progress import ProgressTracker

logger = setup_logger()


def load_config() -> dict:
    """Load configuration from config.json."""
    config_file = Path("config.json")
    if config_file.exists():
        try:
            with open(config_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load config: {e}")
    return {}


def save_config(config: dict):
    """Save configuration to config.json."""
    config_file = Path("config.json")
    try:
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save config: {e}")


def cmd_sync(args):
    """Handle sync command."""
    config = load_config()
    
    firefox_profile = args.firefox_profile or config.get("firefox", {}).get("profile")
    chrome_profile = args.chrome_profile or config.get("chrome", {}).get("profile")
    
    # Determine merge strategy
    merge_strategy_name = args.merge_strategy or config.get("sync", {}).get("merge_strategy", "keep_all")
    try:
        merge_strategy = MergeStrategy(merge_strategy_name)
    except ValueError:
        logger.error(f"Invalid merge strategy: {merge_strategy_name}")
        logger.info(f"Available strategies: {[s.value for s in MergeStrategy]}")
        return 1
    
    # Determine sync mode
    sync_mode_name = args.sync_mode or config.get("sync", {}).get("sync_mode", "full")
    try:
        sync_mode = SyncMode(sync_mode_name)
    except ValueError:
        logger.error(f"Invalid sync mode: {sync_mode_name}")
        logger.info(f"Available modes: {[s.value for s in SyncMode]}")
        return 1
    
    # Determine sync direction
    if args.from_browser and args.to_browser:
        if args.from_browser == "firefox" and args.to_browser == "chrome":
            direction = SyncDirection.FIREFOX_TO_CHROME
        elif args.from_browser == "chrome" and args.to_browser == "firefox":
            direction = SyncDirection.CHROME_TO_FIREFOX
        else:
            logger.error("Invalid browser combination. Use 'firefox' or 'chrome'")
            return 1
    else:
        direction = SyncDirection.BIDIRECTIONAL
    
    try:
        engine = SyncEngine(
            firefox_profile=firefox_profile,
            chrome_profile=chrome_profile,
            merge_strategy=merge_strategy,
            backup_before_sync=not args.no_backup
        )
        
        success = engine.sync(direction=direction, dry_run=args.dry_run)
        return 0 if success else 1
        
    except FileNotFoundError as e:
        logger.error(f"Browser profile not found: {e}")
        logger.info("Use 'list-profiles' to see available profiles")
        return 1
    except Exception as e:
        logger.error(f"Sync failed: {e}")
        return 1


def cmd_merge(args):
    """Handle merge command."""
    config = load_config()
    
    firefox_profile = args.firefox_profile or config.get("firefox", {}).get("profile")
    chrome_profile = args.chrome_profile or config.get("chrome", {}).get("profile")
    
    merge_strategy_name = args.strategy or config.get("sync", {}).get("merge_strategy", "keep_all")
    try:
        merge_strategy = MergeStrategy(merge_strategy_name)
    except ValueError:
        logger.error(f"Invalid merge strategy: {merge_strategy_name}")
        return 1
    
    try:
        engine = SyncEngine(
            firefox_profile=firefox_profile,
            chrome_profile=chrome_profile,
            merge_strategy=merge_strategy,
            backup_before_sync=not args.no_backup,
            sync_mode=SyncMode.MERGE  # Merge command always uses merge mode
        )
        
        # Merge is essentially bidirectional sync
        success = engine.sync(direction=SyncDirection.BIDIRECTIONAL, dry_run=args.dry_run)
        return 0 if success else 1
        
    except Exception as e:
        logger.error(f"Merge failed: {e}")
        return 1


def cmd_backup(args):
    """Handle backup command."""
    backup_manager = BackupManager()
    
    if args.source:
        if args.source == "firefox":
            from src.browsers.firefox import FirefoxAdapter
            try:
                adapter = FirefoxAdapter(args.firefox_profile)
                backup_manager.backup_firefox(
                    adapter.get_profile_path(),
                    adapter.profile_name or "default"
                )
            except Exception as e:
                logger.error(f"Failed to backup Firefox: {e}")
                return 1
        elif args.source == "chrome":
            from src.browsers.chrome import ChromeAdapter
            try:
                adapter = ChromeAdapter(args.chrome_profile)
                backup_manager.backup_chrome(
                    adapter.get_profile_path(),
                    adapter.profile_name or "Default"
                )
            except Exception as e:
                logger.error(f"Failed to backup Chrome: {e}")
                return 1
        else:
            logger.error("Source must be 'firefox' or 'chrome'")
            return 1
    else:
        # Backup both
        from src.browsers.firefox import FirefoxAdapter
        from src.browsers.chrome import ChromeAdapter
        
        try:
            firefox_adapter = FirefoxAdapter()
            backup_manager.backup_firefox(
                firefox_adapter.get_profile_path(),
                firefox_adapter.profile_name or "default"
            )
        except Exception as e:
            logger.warning(f"Firefox backup skipped: {e}")
        
        try:
            chrome_adapter = ChromeAdapter()
            backup_manager.backup_chrome(
                chrome_adapter.get_profile_path(),
                chrome_adapter.profile_name or "Default"
            )
        except Exception as e:
            logger.warning(f"Chrome backup skipped: {e}")
    
    logger.info("Backup completed")
    return 0


def cmd_restore(args):
    """Handle restore command."""
    backup_manager = BackupManager()
    restore_manager = RestoreManager(backup_manager)
    
    # Show backup location
    print(f"\n📁 Backup directory: {backup_manager.backup_dir.absolute()}\n")
    
    # List backups if requested
    if args.list:
        backups = backup_manager.list_backups(source=args.source)
        if not backups:
            logger.info("No backups found")
            if args.source:
                logger.info(f"Filtered by source: {args.source}")
            return 0
        
        print(f"{'='*70}")
        print("AVAILABLE BACKUPS")
        print(f"{'='*70}\n")
        
        for i, backup in enumerate(backups, 1):
            timestamp = backup.get('timestamp', 'Unknown')
            source = backup.get('source', 'unknown')
            profile = backup.get('profile', 'unknown')
            file = backup.get('file', 'unknown')
            size = backup.get('size', 0)
            size_mb = size / (1024 * 1024) if size else 0
            
            print(f"{i}. {source.upper()} - {profile}")
            print(f"   File: {file}")
            print(f"   Date: {timestamp}")
            print(f"   Size: {size_mb:.2f} MB")
            print(f"   Path: {backup.get('path', 'N/A')}")
            print()
        
        print(f"Total: {len(backups)} backup(s)")
        print(f"\nTo restore, use:")
        print(f"  python3 -m src.main restore --interactive")
        print(f"  python3 -m src.main restore --latest --source firefox")
        print(f"  python3 -m src.main restore <backup_file_path>")
        return 0
    
    # Interactive selection
    if args.interactive:
        from src.ui.interactive import prompt_choice
        
        backups = backup_manager.list_backups(source=args.source)
        if not backups:
            logger.error("No backups found")
            return 1
        
        print("\nAvailable backups:")
        choices = []
        for backup in backups:
            timestamp = backup.get('timestamp', 'Unknown')
            source = backup.get('source', 'unknown')
            profile = backup.get('profile', 'unknown')
            file = backup.get('file', 'unknown')
            choices.append(f"{source.upper()} - {profile} ({timestamp[:10]}) - {file}")
        
        idx = prompt_choice("Select backup to restore:", choices)
        selected_backup = backups[idx]
        backup_path = Path(selected_backup['path'])
        source = selected_backup['source']
        profile_name = selected_backup['profile']
    elif args.latest:
        # Restore from latest backup
        if not args.source:
            logger.error("--source is required when using --latest")
            logger.info("Use: --latest --source firefox  or  --latest --source chrome")
            return 1
        
        backup = backup_manager.get_latest_backup(args.source)
        if not backup:
            logger.error(f"No backups found for {args.source}")
            return 1
        
        backup_path = Path(backup['path'])
        source = backup['source']
        profile_name = backup['profile']
        logger.info(f"Using latest {source} backup: {backup['file']}")
    elif args.backup_file:
        # Use provided backup file path
        backup_path = Path(args.backup_file)
        if not backup_path.exists():
            logger.error(f"Backup file not found: {backup_path}")
            logger.info("\nUse 'python3 -m src.main restore --list' to see available backups")
            return 1
        
        # Try to find backup in metadata
        backups = backup_manager.list_backups()
        matching_backup = None
        for backup in backups:
            if Path(backup['path']) == backup_path:
                matching_backup = backup
                break
        
        if matching_backup:
            source = matching_backup['source']
            profile_name = matching_backup['profile']
        else:
            # Determine source from backup path or file name
            if "firefox" in backup_path.name.lower() or "firefox" in str(backup_path):
                source = "firefox"
            elif "chrome" in backup_path.name.lower() or "chrome" in str(backup_path):
                source = "chrome"
            else:
                logger.error("Could not determine backup source from filename")
                logger.info("Backup filename should contain 'firefox' or 'chrome'")
                logger.info("Or use: python3 -m src.main restore --list")
                return 1
            profile_name = None
    else:
        logger.error("No backup specified. Use:")
        logger.info("  --list to see available backups")
        logger.info("  --interactive to choose interactively")
        logger.info("  --latest --source <firefox|chrome> for latest backup")
        logger.info("  <backup_file_path> to specify a file")
        return 1
    
    # Get profile path
    if source == "firefox":
        from src.browsers.firefox import FirefoxAdapter
        try:
            adapter = FirefoxAdapter(args.firefox_profile or profile_name)
            profile_path = adapter.get_profile_path()
        except Exception as e:
            logger.error(f"Failed to get Firefox profile: {e}")
            return 1
    else:
        from src.browsers.chrome import ChromeAdapter
        try:
            adapter = ChromeAdapter(args.chrome_profile or profile_name)
            profile_path = adapter.get_profile_path()
        except Exception as e:
            logger.error(f"Failed to get Chrome profile: {e}")
            return 1
    
    logger.info(f"Restoring {source} from {backup_path}")
    logger.info(f"Target profile: {profile_path}")
    
    # Confirm restore
    if not args.latest and not args.interactive:
        response = input(f"\n⚠️  This will replace current {source} bookmarks. Continue? [y/N]: ")
        if response.lower() not in ['y', 'yes']:
            logger.info("Restore cancelled")
            return 0
    
    if source == "firefox":
        success = restore_manager.restore_firefox(backup_path, profile_path)
    else:
        success = restore_manager.restore_chrome(backup_path, profile_path)
    
    if success:
        logger.info("✓ Restore completed successfully")
        logger.info(f"  Backup location: {backup_manager.backup_dir.absolute()}")
        return 0
    else:
        logger.error("✗ Restore failed")
        return 1


def cmd_list_profiles(args):
    """Handle list-profiles command."""
    print("\n=== Firefox Profiles ===")
    firefox_profiles = get_firefox_profiles()
    if firefox_profiles:
        for profile in firefox_profiles:
            print(f"  Name: {profile['name']}")
            print(f"  Path: {profile['path']}")
            print()
    else:
        print("  No Firefox profiles found")
    
    print("\n=== Chrome Profiles ===")
    chrome_profiles = get_chrome_profiles()
    if chrome_profiles:
        for profile in chrome_profiles:
            print(f"  Name: {profile['name']}")
            print(f"  Path: {profile['path']}")
            print(f"  Browser: {profile.get('browser', 'Chrome')}")
            print()
    else:
        print("  No Chrome profiles found")
    
    return 0


def cmd_list_backups(args):
    """Handle list-backups command."""
    backup_manager = BackupManager()
    backups = backup_manager.list_backups(source=args.source)
    
    if not backups:
        print("No backups found")
        if args.source:
            print(f"Filtered by source: {args.source}")
        print(f"\nBackup directory: {backup_manager.backup_dir.absolute()}")
        return 0
    
    print(f"\n{'='*70}")
    print("AVAILABLE BACKUPS")
    print(f"{'='*70}\n")
    print(f"📁 Backup directory: {backup_manager.backup_dir.absolute()}\n")
    
    for i, backup in enumerate(backups, 1):
        timestamp = backup.get('timestamp', 'Unknown')
        source = backup.get('source', 'unknown')
        profile = backup.get('profile', 'unknown')
        file = backup.get('file', 'unknown')
        size = backup.get('size', 0)
        size_mb = size / (1024 * 1024) if size else 0
        path = backup.get('path', 'N/A')
        
        print(f"{i}. {source.upper()} - Profile: {profile}")
        print(f"   File: {file}")
        print(f"   Date: {timestamp}")
        print(f"   Size: {size_mb:.2f} MB")
        print(f"   Path: {path}")
        print()
    
    print(f"Total: {len(backups)} backup(s)")
    print(f"\nTo restore a backup:")
    print(f"  python3 -m src.main restore --interactive")
    print(f"  python3 -m src.main restore --latest --source <firefox|chrome>")
    print(f"  python3 -m src.main restore <backup_file_path>")
    
    return 0


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Sync bookmarks between Firefox and Chrome",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('--interactive', '-i', action='store_true',
                       help='Run in interactive mode')
    parser.add_argument('--gui', action='store_true',
                       help='Run GUI interface')
    parser.add_argument('--config-wizard', action='store_true',
                       help='Run configuration wizard')
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Sync command
    sync_parser = subparsers.add_parser('sync', help='Sync bookmarks')
    sync_parser.add_argument('--from', dest='from_browser', choices=['firefox', 'chrome'],
                            help='Source browser')
    sync_parser.add_argument('--to', dest='to_browser', choices=['firefox', 'chrome'],
                            help='Target browser')
    sync_parser.add_argument('--firefox-profile', help='Firefox profile name')
    sync_parser.add_argument('--chrome-profile', help='Chrome profile name')
    sync_parser.add_argument('--merge-strategy', choices=[s.value for s in MergeStrategy],
                            help='Merge strategy for bidirectional sync')
    sync_parser.add_argument('--sync-mode', choices=[s.value for s in SyncMode],
                            help='Sync mode: full (replace all), incremental (only changes), merge (combine both)')
    sync_parser.add_argument('--dry-run', action='store_true',
                            help='Preview changes without applying')
    sync_parser.add_argument('--no-backup', action='store_true',
                            help='Skip backup before sync')
    
    # Merge command
    merge_parser = subparsers.add_parser('merge', help='Merge bookmarks from both browsers')
    merge_parser.add_argument('--strategy', choices=[s.value for s in MergeStrategy],
                             help='Merge strategy')
    merge_parser.add_argument('--firefox-profile', help='Firefox profile name')
    merge_parser.add_argument('--chrome-profile', help='Chrome profile name')
    merge_parser.add_argument('--dry-run', action='store_true',
                             help='Preview changes without applying')
    merge_parser.add_argument('--no-backup', action='store_true',
                             help='Skip backup before sync')
    
    # Backup command
    backup_parser = subparsers.add_parser('backup', help='Backup bookmarks')
    backup_parser.add_argument('--source', choices=['firefox', 'chrome'],
                              help='Browser to backup (default: both)')
    backup_parser.add_argument('--firefox-profile', help='Firefox profile name')
    backup_parser.add_argument('--chrome-profile', help='Chrome profile name')
    
    # Restore command
    restore_parser = subparsers.add_parser('restore', help='Restore from backup')
    restore_parser.add_argument('backup_file', nargs='?', help='Path to backup file (or use --list to choose)')
    restore_parser.add_argument('--list', '-l', action='store_true',
                              help='List available backups and exit')
    restore_parser.add_argument('--interactive', '-i', action='store_true',
                              help='Interactive backup selection')
    restore_parser.add_argument('--source', choices=['firefox', 'chrome'],
                              help='Filter backups by source')
    restore_parser.add_argument('--firefox-profile', help='Firefox profile name')
    restore_parser.add_argument('--chrome-profile', help='Chrome profile name')
    restore_parser.add_argument('--latest', action='store_true',
                              help='Restore from latest backup')
    
    # List profiles command
    subparsers.add_parser('list-profiles', help='List available browser profiles')
    
    # List backups command
    list_backups_parser = subparsers.add_parser('list-backups', help='List backups')
    list_backups_parser.add_argument('--source', choices=['firefox', 'chrome'],
                                    help='Filter by source')
    
    args = parser.parse_args()
    
    # Handle special modes
    if args.gui:
        try:
            from src.ui.gui_qt import run_gui
            run_gui()
            return 0
        except ImportError as e:
            logger.error(f"PyQt6 GUI not available: {e}")
            logger.info("Installing PyQt6...")
            logger.info("Try: pip install PyQt6")
            # Fallback to Tkinter if available
            try:
                from src.ui.gui import run_gui as run_tkinter_gui
                logger.info("Falling back to Tkinter GUI...")
                run_tkinter_gui()
                return 0
            except ImportError:
                logger.error("Neither PyQt6 nor Tkinter is available")
                return 1
    
    if args.config_wizard:
        config = interactive_config_wizard()
        if config:
            save_config(config)
            logger.info("Configuration saved to config.json")
        return 0
    
    if args.interactive and args.command == 'sync':
        # Interactive sync mode
        try:
            sync_config = interactive_sync()
            engine = SyncEngine(
                firefox_profile=sync_config['firefox_profile'],
                chrome_profile=sync_config['chrome_profile'],
                merge_strategy=sync_config['merge_strategy'],
                backup_before_sync=sync_config['backup_before_sync'],
                sync_mode=sync_config['sync_mode']
            )
            success = engine.sync(direction=sync_config['direction'], dry_run=sync_config['dry_run'])
            return 0 if success else 1
        except KeyboardInterrupt:
            logger.info("\nCancelled by user")
            return 1
        except Exception as e:
            logger.error(f"Sync failed: {e}")
            return 1
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Route to command handler
    if args.command == 'sync':
        return cmd_sync(args)
    elif args.command == 'merge':
        return cmd_merge(args)
    elif args.command == 'backup':
        return cmd_backup(args)
    elif args.command == 'restore':
        return cmd_restore(args)
    elif args.command == 'list-backups':
        return cmd_list_backups(args)
    elif args.command == 'list-profiles':
        return cmd_list_profiles(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
