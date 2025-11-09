"""Backup management for browser bookmarks."""

import json
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List
from src.utils.logger import setup_logger

logger = setup_logger()


class BackupManager:
    """Manages backups of browser bookmark files."""
    
    def __init__(self, backup_dir: Path = Path("./backups")):
        """
        Initialize backup manager.
        
        Args:
            backup_dir: Directory to store backups
        """
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_file = self.backup_dir / "metadata.json"
        self._load_metadata()
    
    def _load_metadata(self) -> Dict:
        """Load backup metadata."""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load backup metadata: {e}")
        return {"backups": []}
    
    def _save_metadata(self, metadata: Dict):
        """Save backup metadata."""
        try:
            with open(self.metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save backup metadata: {e}")
    
    def backup_firefox(self, profile_path: Path, profile_name: str = "default") -> Optional[Path]:
        """
        Backup Firefox places.sqlite database.
        
        Args:
            profile_path: Path to Firefox profile directory
            profile_name: Name of the profile
            
        Returns:
            Path to backup file or None if failed
        """
        places_db = profile_path / "places.sqlite"
        if not places_db.exists():
            logger.error(f"Firefox places.sqlite not found at {places_db}")
            return None
        
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        backup_filename = f"firefox_{profile_name}_places_{timestamp}.sqlite"
        backup_path = self.backup_dir / "firefox" / backup_filename
        
        try:
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(places_db, backup_path)
            
            # Update metadata
            metadata = self._load_metadata()
            metadata["backups"].append({
                "timestamp": datetime.now().isoformat(),
                "source": "firefox",
                "profile": profile_name,
                "file": backup_filename,
                "path": str(backup_path),
                "size": backup_path.stat().st_size
            })
            self._save_metadata(metadata)
            
            logger.info(f"Backed up Firefox profile '{profile_name}' to {backup_path}")
            return backup_path
        except Exception as e:
            logger.error(f"Failed to backup Firefox: {e}")
            return None
    
    def backup_chrome(self, profile_path: Path, profile_name: str = "Default") -> Optional[Path]:
        """
        Backup Chrome Bookmarks file.
        
        Args:
            profile_path: Path to Chrome profile directory
            profile_name: Name of the profile
            
        Returns:
            Path to backup file or None if failed
        """
        bookmarks_file = profile_path / "Bookmarks"
        if not bookmarks_file.exists():
            logger.error(f"Chrome Bookmarks file not found at {bookmarks_file}")
            return None
        
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        backup_filename = f"chrome_{profile_name}_Bookmarks_{timestamp}.json"
        backup_path = self.backup_dir / "chrome" / backup_filename
        
        try:
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(bookmarks_file, backup_path)
            
            # Update metadata
            metadata = self._load_metadata()
            metadata["backups"].append({
                "timestamp": datetime.now().isoformat(),
                "source": "chrome",
                "profile": profile_name,
                "file": backup_filename,
                "path": str(backup_path),
                "size": backup_path.stat().st_size
            })
            self._save_metadata(metadata)
            
            logger.info(f"Backed up Chrome profile '{profile_name}' to {backup_path}")
            return backup_path
        except Exception as e:
            logger.error(f"Failed to backup Chrome: {e}")
            return None
    
    def list_backups(self, source: Optional[str] = None) -> List[Dict]:
        """
        List all backups, optionally filtered by source.
        
        Args:
            source: Filter by source ('firefox' or 'chrome')
            
        Returns:
            List of backup metadata dicts
        """
        metadata = self._load_metadata()
        backups = metadata.get("backups", [])
        
        if source:
            backups = [b for b in backups if b.get("source") == source]
        
        # Sort by timestamp (newest first)
        backups.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return backups
    
    def get_latest_backup(self, source: str) -> Optional[Dict]:
        """
        Get the latest backup for a source.
        
        Args:
            source: 'firefox' or 'chrome'
            
        Returns:
            Latest backup metadata dict or None
        """
        backups = self.list_backups(source)
        return backups[0] if backups else None
    
    def cleanup_old_backups(self, retention_days: int = 30):
        """
        Remove backups older than retention_days.
        
        Args:
            retention_days: Number of days to keep backups
        """
        metadata = self._load_metadata()
        backups = metadata.get("backups", [])
        cutoff_date = datetime.now().timestamp() - (retention_days * 24 * 60 * 60)
        
        kept_backups = []
        removed_count = 0
        
        for backup in backups:
            try:
                backup_time = datetime.fromisoformat(backup["timestamp"]).timestamp()
                backup_path = Path(backup["path"])
                
                if backup_time < cutoff_date:
                    # Remove old backup
                    if backup_path.exists():
                        backup_path.unlink()
                        removed_count += 1
                else:
                    kept_backups.append(backup)
            except Exception as e:
                logger.warning(f"Error processing backup {backup.get('file')}: {e}")
                # Keep backup if we can't process it
                kept_backups.append(backup)
        
        metadata["backups"] = kept_backups
        self._save_metadata(metadata)
        
        if removed_count > 0:
            logger.info(f"Cleaned up {removed_count} old backup(s)")
