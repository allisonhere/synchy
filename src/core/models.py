"""Data models for bookmarks."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Union
from enum import Enum


class BookmarkType(Enum):
    """Bookmark item types."""
    URL = "url"
    FOLDER = "folder"


@dataclass
class Bookmark:
    """Represents a bookmark URL."""
    title: str
    url: str
    date_added: datetime
    date_modified: datetime
    favicon: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    
    def __hash__(self):
        """Hash based on URL for duplicate detection."""
        return hash(self.url.lower())
    
    def __eq__(self, other):
        """Equality based on URL."""
        if not isinstance(other, Bookmark):
            return False
        return self.url.lower() == other.url.lower()


@dataclass
class BookmarkFolder:
    """Represents a bookmark folder containing bookmarks and subfolders."""
    name: str
    date_added: datetime
    date_modified: datetime
    children: List[Union['BookmarkFolder', Bookmark]] = field(default_factory=list)
    
    def add_child(self, child: Union['BookmarkFolder', Bookmark]):
        """Add a child bookmark or folder."""
        self.children.append(child)
    
    def find_bookmark_by_url(self, url: str) -> Optional[Bookmark]:
        """Find a bookmark by URL recursively."""
        url_lower = url.lower()
        for child in self.children:
            if isinstance(child, Bookmark):
                if child.url.lower() == url_lower:
                    return child
            elif isinstance(child, BookmarkFolder):
                found = child.find_bookmark_by_url(url)
                if found:
                    return found
        return None
    
    def find_folder_by_name(self, name: str) -> Optional['BookmarkFolder']:
        """Find a folder by name (non-recursive)."""
        for child in self.children:
            if isinstance(child, BookmarkFolder) and child.name == name:
                return child
        return None
    
    def get_all_bookmarks(self) -> List[Bookmark]:
        """Get all bookmarks recursively."""
        bookmarks = []
        for child in self.children:
            if isinstance(child, Bookmark):
                bookmarks.append(child)
            elif isinstance(child, BookmarkFolder):
                bookmarks.extend(child.get_all_bookmarks())
        return bookmarks
    
    def get_all_folders(self) -> List['BookmarkFolder']:
        """Get all folders recursively."""
        folders = []
        for child in self.children:
            if isinstance(child, BookmarkFolder):
                folders.append(child)
                folders.extend(child.get_all_folders())
        return folders


# Type alias for the root bookmark tree
BookmarkTree = BookmarkFolder
