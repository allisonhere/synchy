"""Sync engine for bidirectional bookmark synchronization."""

import os
import sqlite3
import json
from enum import Enum
from typing import Optional
from pathlib import Path
from datetime import datetime
from src.browsers.base import BrowserAdapter
from src.browsers.firefox import FirefoxAdapter
from src.browsers.chrome import ChromeAdapter
from src.core.models import BookmarkTree
from src.core.merger import BookmarkMerger, MergeStrategy
from src.core.change_detector import ChangeDetector
from src.core.sync_metadata import SyncMetadata
from src.backup.backup_manager import BackupManager
from src.utils.logger import setup_logger
from src.utils.validators import is_valid_url

logger = setup_logger()


class SyncDirection(Enum):
    """Sync direction."""
    FIREFOX_TO_CHROME = "firefox_to_chrome"
    CHROME_TO_FIREFOX = "chrome_to_firefox"
    BIDIRECTIONAL = "bidirectional"


class SyncMode(Enum):
    """Sync mode."""
    FULL = "full"  # Replace all bookmarks
    INCREMENTAL = "incremental"  # Only sync changes
    MERGE = "merge"  # Merge both sources


class SyncError(Exception):
    """Base exception for sync errors."""
    pass


class BrowserNotFoundError(SyncError):
    """Browser profile not found."""
    pass


class BrowserLockedError(SyncError):
    """Browser database/file is locked."""
    pass


class PermissionError(SyncError):
    """Permission denied accessing browser files."""
    pass


class CorruptedDataError(SyncError):
    """Corrupted bookmark data detected."""
    pass


class SyncEngine:
    """Engine for synchronizing bookmarks between browsers."""
    
    def __init__(self, firefox_profile: Optional[str] = None,
                 chrome_profile: Optional[str] = None,
                 merge_strategy: MergeStrategy = MergeStrategy.KEEP_ALL,
                 backup_before_sync: bool = True,
                 sync_mode: SyncMode = SyncMode.FULL):
        """
        Initialize sync engine.
        
        Args:
            firefox_profile: Firefox profile name (None for default)
            chrome_profile: Chrome profile name (None for Default)
            merge_strategy: Merge strategy to use
            backup_before_sync: Whether to backup before syncing
            sync_mode: Sync mode (full, incremental, merge)
        """
        try:
            self.firefox_adapter = FirefoxAdapter(firefox_profile)
            self.firefox_profile_name = firefox_profile or "default"
        except FileNotFoundError as e:
            raise BrowserNotFoundError(f"Firefox profile not found: {e}")
        
        try:
            self.chrome_adapter = ChromeAdapter(chrome_profile)
            self.chrome_profile_name = chrome_profile or "Default"
        except FileNotFoundError as e:
            raise BrowserNotFoundError(f"Chrome profile not found: {e}")
        
        self.merger = BookmarkMerger(merge_strategy)
        self.backup_manager = BackupManager()
        self.backup_before_sync = backup_before_sync
        self.sync_mode = sync_mode
        self.change_detector = ChangeDetector()
        self.metadata = SyncMetadata()
    
    def sync(self, direction: SyncDirection = SyncDirection.BIDIRECTIONAL, 
             dry_run: bool = False) -> bool:
        """
        Synchronize bookmarks.
        
        Args:
            direction: Direction of sync
            dry_run: If True, preview changes without applying
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Validate browser access
            self._validate_browser_access()
            
            if direction == SyncDirection.FIREFOX_TO_CHROME:
                return self._sync_firefox_to_chrome(dry_run)
            elif direction == SyncDirection.CHROME_TO_FIREFOX:
                return self._sync_chrome_to_firefox(dry_run)
            else:  # BIDIRECTIONAL
                if self.sync_mode == SyncMode.MERGE:
                    return self._sync_bidirectional(dry_run)
                else:
                    # For full/incremental, sync both directions
                    success1 = self._sync_firefox_to_chrome(dry_run)
                    success2 = self._sync_chrome_to_firefox(dry_run)
                    return success1 and success2
        except BrowserLockedError as e:
            logger.error(f"Browser is locked: {e}")
            return False
        except PermissionError as e:
            logger.error(f"Permission denied: {e}")
            return False
        except CorruptedDataError as e:
            logger.error(f"Corrupted data detected: {e}")
            return False
        except BrowserNotFoundError as e:
            logger.error(f"Browser not found: {e}")
            return False
        except Exception as e:
            logger.error(f"Sync failed: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return False
    
    def _validate_browser_access(self):
        """Validate access to browser files."""
        # Check Firefox
        if self.firefox_adapter.is_locked():
            raise BrowserLockedError("Firefox database is locked. Please close Firefox.")
        
        firefox_path = self.firefox_adapter.get_profile_path()
        if not os.access(firefox_path, os.R_OK):
            raise PermissionError(f"Cannot read Firefox profile: {firefox_path}")
        
        # Check Chrome
        if self.chrome_adapter.is_locked():
            raise BrowserLockedError("Chrome Bookmarks file is locked. Please close Chrome.")
        
        chrome_path = self.chrome_adapter.get_profile_path()
        if not os.access(chrome_path, os.R_OK):
            raise PermissionError(f"Cannot read Chrome profile: {chrome_path}")
    
    def _validate_bookmark_tree(self, tree: BookmarkTree) -> bool:
        """
        Validate bookmark tree for corruption.
        
        Args:
            tree: Bookmark tree to validate
            
        Returns:
            True if valid, raises CorruptedDataError if invalid
        """
        bookmarks = tree.get_all_bookmarks()
        
        for bookmark in bookmarks:
            if not is_valid_url(bookmark.url):
                raise CorruptedDataError(f"Invalid URL in bookmark: {bookmark.url}")
            
            if not bookmark.title or len(bookmark.title.strip()) == 0:
                logger.warning(f"Bookmark with empty title: {bookmark.url}")
        
        return True
    
    def _sync_firefox_to_chrome(self, dry_run: bool = False) -> bool:
        """Sync Firefox bookmarks to Chrome."""
        logger.info(f"Syncing Firefox → Chrome (mode: {self.sync_mode.value})")
        
        # Backup if enabled
        if self.backup_before_sync and not dry_run:
            self.backup_manager.backup_firefox(
                self.firefox_adapter.get_profile_path(),
                self.firefox_profile_name
            )
            self.backup_manager.backup_chrome(
                self.chrome_adapter.get_profile_path(),
                self.chrome_profile_name
            )
        
        # Read Firefox bookmarks
        logger.info("Reading Firefox bookmarks...")
        try:
            firefox_tree = self.firefox_adapter.read_bookmarks()
            self._validate_bookmark_tree(firefox_tree)
        except Exception as e:
            raise CorruptedDataError(f"Failed to read Firefox bookmarks: {e}")
        
        # Handle incremental sync
        if self.sync_mode == SyncMode.INCREMENTAL:
            return self._sync_incremental_firefox_to_chrome(firefox_tree, dry_run)
        
        # Full sync
        if dry_run:
            logger.info(f"DRY RUN: Would write {len(firefox_tree.get_all_bookmarks())} bookmarks to Chrome")
            return True
        
        # Write to Chrome
        logger.info("Writing bookmarks to Chrome...")
        try:
            success = self.chrome_adapter.write_bookmarks(firefox_tree)
            
            if success:
                # Update metadata
                sync_time = datetime.now()
                self.metadata.set_last_sync_time("firefox", self.firefox_profile_name, sync_time)
                self.metadata.set_last_sync_time("chrome", self.chrome_profile_name, sync_time)
                
                # Store bookmark hashes
                hashes = self.change_detector.get_all_bookmark_hashes(firefox_tree)
                for url, hash_value in hashes.items():
                    self.metadata.set_bookmark_hash("chrome", self.chrome_profile_name, url, hash_value)
                
                logger.info("Successfully synced Firefox → Chrome")
            else:
                logger.error("Failed to sync Firefox → Chrome")
            
            return success
        except Exception as e:
            raise CorruptedDataError(f"Failed to write Chrome bookmarks: {e}")
    
    def _sync_incremental_firefox_to_chrome(self, firefox_tree: BookmarkTree, dry_run: bool) -> bool:
        """Incremental sync Firefox to Chrome."""
        logger.info("Performing incremental sync...")
        
        # Get previous Chrome bookmarks state
        previous_hashes = {}
        chrome_bookmarks_file = self.chrome_adapter.bookmarks_file
        if chrome_bookmarks_file.exists():
            try:
                chrome_tree = self.chrome_adapter.read_bookmarks()
                previous_hashes = self.change_detector.get_all_bookmark_hashes(chrome_tree)
            except:
                logger.warning("Could not read previous Chrome state, performing full sync")
                previous_hashes = {}
        
        # Detect changes
        new_bookmarks, modified_bookmarks, deleted_urls = self.change_detector.detect_changes(
            firefox_tree, previous_hashes
        )
        
        if not new_bookmarks and not modified_bookmarks and not deleted_urls:
            logger.info("No changes detected, sync not needed")
            return True
        
        logger.info(f"Incremental sync: {len(new_bookmarks)} new, "
                   f"{len(modified_bookmarks)} modified, {len(deleted_urls)} deleted")
        
        if dry_run:
            logger.info(f"DRY RUN: Would sync {len(new_bookmarks) + len(modified_bookmarks)} changed bookmarks")
            return True
        
        # For incremental sync, we still write the full tree
        # (browsers don't support partial updates easily)
        # But we track what changed
        success = self.chrome_adapter.write_bookmarks(firefox_tree)
        
        if success:
            # Update metadata
            sync_time = datetime.now()
            self.metadata.set_last_sync_time("firefox", self.firefox_profile_name, sync_time)
            self.metadata.set_last_sync_time("chrome", self.chrome_profile_name, sync_time)
            
            # Store bookmark hashes
            hashes = self.change_detector.get_all_bookmark_hashes(firefox_tree)
            for url, hash_value in hashes.items():
                self.metadata.set_bookmark_hash("chrome", self.chrome_profile_name, url, hash_value)
        
        return success
    
    def _sync_chrome_to_firefox(self, dry_run: bool = False) -> bool:
        """Sync Chrome bookmarks to Firefox."""
        logger.info(f"Syncing Chrome → Firefox (mode: {self.sync_mode.value})")
        
        # Backup if enabled
        if self.backup_before_sync and not dry_run:
            self.backup_manager.backup_firefox(
                self.firefox_adapter.get_profile_path(),
                self.firefox_profile_name
            )
            self.backup_manager.backup_chrome(
                self.chrome_adapter.get_profile_path(),
                self.chrome_profile_name
            )
        
        # Read Chrome bookmarks
        logger.info("Reading Chrome bookmarks...")
        try:
            chrome_tree = self.chrome_adapter.read_bookmarks()
            self._validate_bookmark_tree(chrome_tree)
        except Exception as e:
            raise CorruptedDataError(f"Failed to read Chrome bookmarks: {e}")
        
        # Handle incremental sync
        if self.sync_mode == SyncMode.INCREMENTAL:
            return self._sync_incremental_chrome_to_firefox(chrome_tree, dry_run)
        
        # Full sync
        if dry_run:
            logger.info(f"DRY RUN: Would write {len(chrome_tree.get_all_bookmarks())} bookmarks to Firefox")
            return True
        
        # Write to Firefox
        logger.info("Writing bookmarks to Firefox...")
        try:
            success = self.firefox_adapter.write_bookmarks(chrome_tree)
            
            if success:
                # Update metadata
                sync_time = datetime.now()
                self.metadata.set_last_sync_time("firefox", self.firefox_profile_name, sync_time)
                self.metadata.set_last_sync_time("chrome", self.chrome_profile_name, sync_time)
                
                # Store bookmark hashes
                hashes = self.change_detector.get_all_bookmark_hashes(chrome_tree)
                for url, hash_value in hashes.items():
                    self.metadata.set_bookmark_hash("firefox", self.firefox_profile_name, url, hash_value)
                
                logger.info("Successfully synced Chrome → Firefox")
            else:
                logger.error("Failed to sync Chrome → Firefox")
            
            return success
        except Exception as e:
            raise CorruptedDataError(f"Failed to write Firefox bookmarks: {e}")
    
    def _sync_incremental_chrome_to_firefox(self, chrome_tree: BookmarkTree, dry_run: bool) -> bool:
        """Incremental sync Chrome to Firefox."""
        logger.info("Performing incremental sync...")
        
        # Get previous Firefox bookmarks state
        previous_hashes = {}
        try:
            firefox_tree = self.firefox_adapter.read_bookmarks()
            previous_hashes = self.change_detector.get_all_bookmark_hashes(firefox_tree)
        except:
            logger.warning("Could not read previous Firefox state, performing full sync")
            previous_hashes = {}
        
        # Detect changes
        new_bookmarks, modified_bookmarks, deleted_urls = self.change_detector.detect_changes(
            chrome_tree, previous_hashes
        )
        
        if not new_bookmarks and not modified_bookmarks and not deleted_urls:
            logger.info("No changes detected, sync not needed")
            return True
        
        logger.info(f"Incremental sync: {len(new_bookmarks)} new, "
                   f"{len(modified_bookmarks)} modified, {len(deleted_urls)} deleted")
        
        if dry_run:
            logger.info(f"DRY RUN: Would sync {len(new_bookmarks) + len(modified_bookmarks)} changed bookmarks")
            return True
        
        # Write full tree (browsers don't support partial updates easily)
        success = self.firefox_adapter.write_bookmarks(chrome_tree)
        
        if success:
            # Update metadata
            sync_time = datetime.now()
            self.metadata.set_last_sync_time("firefox", self.firefox_profile_name, sync_time)
            self.metadata.set_last_sync_time("chrome", self.chrome_profile_name, sync_time)
            
            # Store bookmark hashes
            hashes = self.change_detector.get_all_bookmark_hashes(chrome_tree)
            for url, hash_value in hashes.items():
                self.metadata.set_bookmark_hash("firefox", self.firefox_profile_name, url, hash_value)
        
        return success
    
    def _sync_bidirectional(self, dry_run: bool = False) -> bool:
        """Sync bookmarks bidirectionally with merge."""
        logger.info("Syncing Firefox ↔ Chrome (bidirectional merge)")
        
        # Check if browsers are locked
        if self.firefox_adapter.is_locked():
            logger.error("Firefox is running. Please close Firefox and try again.")
            return False
        
        if self.chrome_adapter.is_locked():
            logger.error("Chrome is running. Please close Chrome and try again.")
            return False
        
        # Backup if enabled
        if self.backup_before_sync and not dry_run:
            self.backup_manager.backup_firefox(
                self.firefox_adapter.get_profile_path(),
                self.firefox_profile_name
            )
            self.backup_manager.backup_chrome(
                self.chrome_adapter.get_profile_path(),
                self.chrome_profile_name
            )
        
        # Read both
        logger.info("Reading Firefox bookmarks...")
        try:
            firefox_tree = self.firefox_adapter.read_bookmarks()
            self._validate_bookmark_tree(firefox_tree)
        except Exception as e:
            raise CorruptedDataError(f"Failed to read Firefox bookmarks: {e}")
        
        logger.info("Reading Chrome bookmarks...")
        try:
            chrome_tree = self.chrome_adapter.read_bookmarks()
            self._validate_bookmark_tree(chrome_tree)
        except Exception as e:
            raise CorruptedDataError(f"Failed to read Chrome bookmarks: {e}")
        
        # Merge
        logger.info(f"Merging bookmarks using {self.merger.strategy.value} strategy...")
        merged_tree = self.merger.merge(
            firefox_tree,
            chrome_tree,
            "Firefox",
            "Chrome"
        )
        
        logger.info(f"Merged tree contains {len(merged_tree.get_all_bookmarks())} bookmarks")
        
        # Report conflicts and duplicates
        conflicts = self.merger.get_conflicts()
        duplicates = self.merger.get_duplicate_matches()
        
        if conflicts:
            logger.warning(f"Found {len(conflicts)} conflict(s) during merge")
            for conflict in conflicts:
                logger.warning(f"  Conflict: {conflict.url} - {conflict.conflict_type}")
        
        if duplicates:
            logger.info(f"Found {len(duplicates)} duplicate match(es)")
            for b1, b2, match_type in duplicates[:5]:  # Show first 5
                logger.debug(f"  Duplicate ({match_type}): {b1.url}")
        
        if dry_run:
            logger.info(f"DRY RUN: Would write {len(merged_tree.get_all_bookmarks())} bookmarks to both browsers")
            logger.info(f"  Firefox: {len(firefox_tree.get_all_bookmarks())} → {len(merged_tree.get_all_bookmarks())}")
            logger.info(f"  Chrome: {len(chrome_tree.get_all_bookmarks())} → {len(merged_tree.get_all_bookmarks())}")
            return True
        
        # Write to both
        logger.info("Writing merged bookmarks to Chrome...")
        try:
            chrome_success = self.chrome_adapter.write_bookmarks(merged_tree)
        except Exception as e:
            raise CorruptedDataError(f"Failed to write Chrome bookmarks: {e}")
        
        logger.info("Writing merged bookmarks to Firefox...")
        try:
            firefox_success = self.firefox_adapter.write_bookmarks(merged_tree)
        except Exception as e:
            raise CorruptedDataError(f"Failed to write Firefox bookmarks: {e}")
        
        if chrome_success and firefox_success:
            # Update metadata
            sync_time = datetime.now()
            self.metadata.set_last_sync_time("firefox", self.firefox_profile_name, sync_time)
            self.metadata.set_last_sync_time("chrome", self.chrome_profile_name, sync_time)
            
            # Store bookmark hashes
            hashes = self.change_detector.get_all_bookmark_hashes(merged_tree)
            for url, hash_value in hashes.items():
                self.metadata.set_bookmark_hash("firefox", self.firefox_profile_name, url, hash_value)
                self.metadata.set_bookmark_hash("chrome", self.chrome_profile_name, url, hash_value)
            
            logger.info("Successfully synced Firefox ↔ Chrome")
            return True
        elif chrome_success:
            logger.warning("Chrome sync succeeded, but Firefox sync failed")
            return False
        else:
            logger.error("Failed to sync to both browsers")
            return False
