"""Base class for browser adapters."""

from abc import ABC, abstractmethod
from pathlib import Path
from src.core.models import BookmarkTree


class BrowserAdapter(ABC):
    """Abstract base class for browser bookmark adapters."""
    
    @abstractmethod
    def read_bookmarks(self) -> BookmarkTree:
        """Read bookmarks from browser."""
        pass
    
    @abstractmethod
    def write_bookmarks(self, tree: BookmarkTree) -> bool:
        """Write bookmarks to browser."""
        pass
    
    @abstractmethod
    def get_profile_path(self) -> Path:
        """Get path to browser profile directory."""
        pass
    
    @abstractmethod
    def is_locked(self) -> bool:
        """Check if browser database/file is locked."""
        pass
