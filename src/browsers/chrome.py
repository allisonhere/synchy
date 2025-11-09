"""Chrome browser adapter."""

import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
from src.browsers.base import BrowserAdapter
from src.core.models import BookmarkTree, BookmarkFolder, Bookmark
from src.utils.paths import get_chrome_profile_path, get_chrome_bookmarks_file, is_chrome_locked
from src.utils.logger import setup_logger
from src.utils.validators import is_valid_url

logger = setup_logger()


class ChromeAdapter(BrowserAdapter):
    """Adapter for reading and writing Chrome bookmarks."""
    
    def __init__(self, profile_name: Optional[str] = None):
        """
        Initialize Chrome adapter.
        
        Args:
            profile_name: Name of Chrome profile (None for Default)
        """
        self.profile_name = profile_name
        self.profile_path = get_chrome_profile_path(profile_name)
        self.bookmarks_file = get_chrome_bookmarks_file(profile_name)
        
        if not self.bookmarks_file or not self.bookmarks_file.exists():
            raise FileNotFoundError(
                f"Chrome Bookmarks file not found for profile '{profile_name or 'Default'}'"
            )
    
    def get_profile_path(self) -> Path:
        """Get path to Chrome profile directory."""
        return self.profile_path
    
    def is_locked(self) -> bool:
        """Check if Chrome Bookmarks file is locked."""
        return is_chrome_locked(self.profile_name)
    
    def _timestamp_to_datetime(self, timestamp) -> datetime:
        """Convert Chrome timestamp (microseconds since epoch) to datetime."""
        # Chrome uses microseconds since Unix epoch
        # Handle both string and int timestamps (Chrome sometimes stores as strings)
        if isinstance(timestamp, str):
            timestamp = int(timestamp) if timestamp else 0
        elif timestamp is None:
            timestamp = 0
        elif not isinstance(timestamp, (int, float)):
            # Try to convert to int
            try:
                timestamp = int(timestamp)
            except (ValueError, TypeError):
                timestamp = 0
        return datetime.fromtimestamp(timestamp / 1000000)
    
    def _datetime_to_timestamp(self, dt: datetime) -> int:
        """Convert datetime to Chrome timestamp (microseconds)."""
        return int(dt.timestamp() * 1000000)
    
    def _parse_chrome_node(self, node: Dict[str, Any], parent_folder: BookmarkFolder):
        """
        Recursively parse a Chrome bookmark node.
        
        Args:
            node: Chrome bookmark node dict
            parent_folder: Parent BookmarkFolder to add items to
        """
        node_type = node.get("type", "folder")
        name = node.get("name", "")
        
        if node_type == "url":
            url = node.get("url", "")
            if not is_valid_url(url):
                return
            
            date_added_raw = node.get("date_added", "0")
            date_modified_raw = node.get("date_modified", date_added_raw)
            date_added = self._timestamp_to_datetime(date_added_raw)
            date_modified = self._timestamp_to_datetime(date_modified_raw)
            
            bookmark = Bookmark(
                title=name or url,
                url=url,
                date_added=date_added,
                date_modified=date_modified
            )
            parent_folder.add_child(bookmark)
        
        elif node_type == "folder":
            date_added_raw = node.get("date_added", "0")
            date_modified_raw = node.get("date_modified", date_added_raw)
            date_added = self._timestamp_to_datetime(date_added_raw)
            date_modified = self._timestamp_to_datetime(date_modified_raw)
            
            folder = BookmarkFolder(
                name=name or "Unnamed Folder",
                date_added=date_added,
                date_modified=date_modified
            )
            
            # Process children
            children = node.get("children", [])
            for child in children:
                self._parse_chrome_node(child, folder)
            
            parent_folder.add_child(folder)
    
    def read_bookmarks(self) -> BookmarkTree:
        """
        Read bookmarks from Chrome Bookmarks JSON file.
        
        Returns:
            BookmarkTree with all bookmarks
        """
        if self.is_locked():
            raise RuntimeError("Chrome Bookmarks file is locked. Please close Chrome and try again.")
        
        try:
            with open(self.bookmarks_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            raise RuntimeError(f"Failed to read Chrome Bookmarks file: {e}")
        
        # Create root folder
        root = BookmarkFolder(
            name="Chrome Bookmarks",
            date_added=datetime.now(),
            date_modified=datetime.now()
        )
        
        # Chrome has three root folders: bookmark_bar, other, synced
        roots = data.get("roots", {})
        
        for root_name in ["bookmark_bar", "other", "synced"]:
            if root_name in roots:
                root_node = roots[root_name]
                folder_name = root_name.replace("_", " ").title()
                
                folder = BookmarkFolder(
                    name=folder_name,
                    date_added=datetime.now(),
                    date_modified=datetime.now()
                )
                
                children = root_node.get("children", [])
                for child in children:
                    self._parse_chrome_node(child, folder)
                
                if folder.children:
                    root.add_child(folder)
        
        logger.info(f"Read {len(root.get_all_bookmarks())} bookmarks from Chrome")
        return root
    
    def _bookmark_to_chrome_node(self, bookmark: Bookmark) -> Dict[str, Any]:
        """Convert Bookmark to Chrome node format."""
        return {
            "name": bookmark.title,
            "type": "url",
            "url": bookmark.url,
            "date_added": str(self._datetime_to_timestamp(bookmark.date_added)),
            "date_modified": str(self._datetime_to_timestamp(bookmark.date_modified))
        }
    
    def _folder_to_chrome_node(self, folder: BookmarkFolder) -> Dict[str, Any]:
        """Convert BookmarkFolder to Chrome node format."""
        children = []
        for child in folder.children:
            if isinstance(child, Bookmark):
                children.append(self._bookmark_to_chrome_node(child))
            elif isinstance(child, BookmarkFolder):
                children.append(self._folder_to_chrome_node(child))
        
        return {
            "name": folder.name,
            "type": "folder",
            "date_added": str(self._datetime_to_timestamp(folder.date_added)),
            "date_modified": str(self._datetime_to_timestamp(folder.date_modified)),
            "children": children
        }
    
    def write_bookmarks(self, tree: BookmarkTree) -> bool:
        """
        Write bookmarks to Chrome Bookmarks JSON file.
        
        Args:
            tree: BookmarkTree to write
            
        Returns:
            True if successful, False otherwise
        """
        if self.is_locked():
            raise RuntimeError("Chrome Bookmarks file is locked. Please close Chrome and try again.")
        
        try:
            # Read existing file to preserve metadata
            try:
                with open(self.bookmarks_file, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
            except:
                existing_data = {}
            
            # Create new structure
            chrome_data = {
                "checksum": "",
                "roots": {
                    "bookmark_bar": {
                        "children": [],
                        "date_added": str(self._datetime_to_timestamp(datetime.now())),
                        "date_modified": str(self._datetime_to_timestamp(datetime.now())),
                        "id": "1",
                        "name": "Bookmarks Bar",
                        "type": "folder"
                    },
                    "other": {
                        "children": [],
                        "date_added": str(self._datetime_to_timestamp(datetime.now())),
                        "date_modified": str(self._datetime_to_timestamp(datetime.now())),
                        "id": "2",
                        "name": "Other Bookmarks",
                        "type": "folder"
                    },
                    "synced": {
                        "children": [],
                        "date_added": str(self._datetime_to_timestamp(datetime.now())),
                        "date_modified": str(self._datetime_to_timestamp(datetime.now())),
                        "id": "3",
                        "name": "Mobile Bookmarks",
                        "type": "folder"
                    }
                },
                "version": 1
            }
            
            # Distribute bookmarks to root folders
            # Try to match existing structure, or use bookmark_bar as default
            bookmark_bar_children = []
            other_children = []
            
            for child in tree.children:
                if isinstance(child, BookmarkFolder):
                    chrome_node = self._folder_to_chrome_node(child)
                    # Put in bookmark_bar by default, or other if it's a special folder
                    if child.name.lower() in ["other", "other bookmarks"]:
                        other_children.append(chrome_node)
                    else:
                        bookmark_bar_children.append(chrome_node)
                elif isinstance(child, Bookmark):
                    bookmark_bar_children.append(self._bookmark_to_chrome_node(child))
            
            chrome_data["roots"]["bookmark_bar"]["children"] = bookmark_bar_children
            chrome_data["roots"]["other"]["children"] = other_children
            
            # Write to file
            with open(self.bookmarks_file, 'w', encoding='utf-8') as f:
                json.dump(chrome_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Wrote {len(tree.get_all_bookmarks())} bookmarks to Chrome")
            return True
            
        except Exception as e:
            logger.error(f"Failed to write Chrome bookmarks: {e}")
            return False
