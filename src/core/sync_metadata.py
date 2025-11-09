"""Sync metadata tracking for incremental sync."""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional
from src.utils.logger import setup_logger

logger = setup_logger()


class SyncMetadata:
    """Tracks sync metadata for incremental sync."""
    
    def __init__(self, metadata_file: Path = Path(".sync_metadata.json")):
        """
        Initialize sync metadata manager.
        
        Args:
            metadata_file: Path to metadata file
        """
        self.metadata_file = metadata_file
        self.metadata: Dict = self._load_metadata()
    
    def _load_metadata(self) -> Dict:
        """Load metadata from file."""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load sync metadata: {e}")
                return {}
        return {}
    
    def _save_metadata(self):
        """Save metadata to file."""
        try:
            with open(self.metadata_file, 'w') as f:
                json.dump(self.metadata, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save sync metadata: {e}")
    
    def get_last_sync_time(self, source: str, profile: str) -> Optional[datetime]:
        """
        Get last sync time for a source/profile.
        
        Args:
            source: 'firefox' or 'chrome'
            profile: Profile name
            
        Returns:
            Last sync datetime or None
        """
        key = f"{source}:{profile}"
        timestamp = self.metadata.get(key, {}).get("last_sync")
        if timestamp:
            try:
                return datetime.fromisoformat(timestamp)
            except:
                return None
        return None
    
    def set_last_sync_time(self, source: str, profile: str, sync_time: datetime):
        """
        Set last sync time for a source/profile.
        
        Args:
            source: 'firefox' or 'chrome'
            profile: Profile name
            sync_time: Sync datetime
        """
        key = f"{source}:{profile}"
        if key not in self.metadata:
            self.metadata[key] = {}
        self.metadata[key]["last_sync"] = sync_time.isoformat()
        self._save_metadata()
    
    def get_bookmark_hash(self, source: str, profile: str, url: str) -> Optional[str]:
        """
        Get stored hash for a bookmark.
        
        Args:
            source: 'firefox' or 'chrome'
            profile: Profile name
            url: Bookmark URL
            
        Returns:
            Stored hash or None
        """
        key = f"{source}:{profile}"
        bookmarks = self.metadata.get(key, {}).get("bookmarks", {})
        return bookmarks.get(url)
    
    def set_bookmark_hash(self, source: str, profile: str, url: str, hash_value: str):
        """
        Set hash for a bookmark.
        
        Args:
            source: 'firefox' or 'chrome'
            profile: Profile name
            url: Bookmark URL
            hash_value: Hash of bookmark data
        """
        key = f"{source}:{profile}"
        if key not in self.metadata:
            self.metadata[key] = {}
        if "bookmarks" not in self.metadata[key]:
            self.metadata[key]["bookmarks"] = {}
        self.metadata[key]["bookmarks"][url] = hash_value
        self._save_metadata()
    
    def clear_metadata(self, source: Optional[str] = None, profile: Optional[str] = None):
        """
        Clear metadata for a source/profile or all.
        
        Args:
            source: 'firefox' or 'chrome' (None for all)
            profile: Profile name (None for all profiles of source)
        """
        if source is None:
            self.metadata = {}
        elif profile is None:
            # Clear all profiles for source
            keys_to_remove = [k for k in self.metadata.keys() if k.startswith(f"{source}:")]
            for key in keys_to_remove:
                del self.metadata[key]
        else:
            key = f"{source}:{profile}"
            if key in self.metadata:
                del self.metadata[key]
        
        self._save_metadata()
