"""Restore functionality for backups."""

import shutil
from pathlib import Path
from typing import Optional
from src.utils.logger import setup_logger
from src.backup.backup_manager import BackupManager

logger = setup_logger()


class RestoreManager:
    """Manages restoration of browser bookmark files from backups."""
    
    def __init__(self, backup_manager: BackupManager):
        """
        Initialize restore manager.
        
        Args:
            backup_manager: BackupManager instance
        """
        self.backup_manager = backup_manager
    
    def restore_firefox(self, backup_path: Path, profile_path: Path) -> bool:
        """
        Restore Firefox places.sqlite from backup.
        
        Args:
            backup_path: Path to backup file
            profile_path: Path to Firefox profile directory
            
        Returns:
            True if successful, False otherwise
        """
        places_db = profile_path / "places.sqlite"
        
        if not backup_path.exists():
            logger.error(f"Backup file not found: {backup_path}")
            return False
        
        try:
            # Create backup of current state before restoring
            current_backup = self.backup_manager.backup_firefox(
                profile_path,
                profile_path.name
            )
            if current_backup:
                logger.info(f"Created backup of current state: {current_backup}")
            
            # Restore from backup
            shutil.copy2(backup_path, places_db)
            logger.info(f"Restored Firefox from {backup_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to restore Firefox: {e}")
            return False
    
    def restore_chrome(self, backup_path: Path, profile_path: Path) -> bool:
        """
        Restore Chrome Bookmarks from backup.
        
        Args:
            backup_path: Path to backup file
            profile_path: Path to Chrome profile directory
            
        Returns:
            True if successful, False otherwise
        """
        bookmarks_file = profile_path / "Bookmarks"
        
        if not backup_path.exists():
            logger.error(f"Backup file not found: {backup_path}")
            return False
        
        try:
            # Create backup of current state before restoring
            current_backup = self.backup_manager.backup_chrome(
                profile_path,
                profile_path.name
            )
            if current_backup:
                logger.info(f"Created backup of current state: {current_backup}")
            
            # Restore from backup
            shutil.copy2(backup_path, bookmarks_file)
            logger.info(f"Restored Chrome from {backup_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to restore Chrome: {e}")
            return False
