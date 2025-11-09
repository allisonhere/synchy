"""Change detection for incremental sync."""

import hashlib
from typing import List, Set, Dict, Tuple
from datetime import datetime
from src.core.models import BookmarkTree, Bookmark, BookmarkFolder
from src.utils.logger import setup_logger

logger = setup_logger()


class ChangeDetector:
    """Detects changes in bookmarks for incremental sync."""
    
    def __init__(self):
        """Initialize change detector."""
        pass
    
    def compute_bookmark_hash(self, bookmark: Bookmark) -> str:
        """
        Compute hash for a bookmark based on its content.
        
        Args:
            bookmark: Bookmark to hash
            
        Returns:
            Hash string
        """
        # Hash based on URL, title, and date_modified
        content = f"{bookmark.url}|{bookmark.title}|{bookmark.date_modified.isoformat()}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def detect_changes(self, current_tree: BookmarkTree, 
                      previous_hashes: Dict[str, str]) -> Tuple[List[Bookmark], List[Bookmark], List[str]]:
        """
        Detect changes between current bookmarks and previous state.
        
        Args:
            current_tree: Current bookmark tree
            previous_hashes: Dict mapping URL -> hash from previous sync
            
        Returns:
            Tuple of (new_bookmarks, modified_bookmarks, deleted_urls)
        """
        current_bookmarks = current_tree.get_all_bookmarks()
        current_urls: Set[str] = set()
        new_bookmarks: List[Bookmark] = []
        modified_bookmarks: List[Bookmark] = []
        
        for bookmark in current_bookmarks:
            url = bookmark.url.lower()
            current_urls.add(url)
            current_hash = self.compute_bookmark_hash(bookmark)
            
            if url not in previous_hashes:
                # New bookmark
                new_bookmarks.append(bookmark)
            elif previous_hashes[url] != current_hash:
                # Modified bookmark
                modified_bookmarks.append(bookmark)
        
        # Find deleted bookmarks (in previous but not in current)
        deleted_urls = [url for url in previous_hashes.keys() 
                       if url.lower() not in current_urls]
        
        logger.info(f"Change detection: {len(new_bookmarks)} new, "
                   f"{len(modified_bookmarks)} modified, {len(deleted_urls)} deleted")
        
        return new_bookmarks, modified_bookmarks, deleted_urls
    
    def get_all_bookmark_hashes(self, tree: BookmarkTree) -> Dict[str, str]:
        """
        Get hash map for all bookmarks in tree.
        
        Args:
            tree: Bookmark tree
            
        Returns:
            Dict mapping URL (lowercase) -> hash
        """
        hashes = {}
        for bookmark in tree.get_all_bookmarks():
            url = bookmark.url.lower()
            hashes[url] = self.compute_bookmark_hash(bookmark)
        return hashes
    
    def create_incremental_tree(self, new_bookmarks: List[Bookmark],
                               modified_bookmarks: List[Bookmark],
                               deleted_urls: List[str]) -> BookmarkTree:
        """
        Create a bookmark tree containing only changes.
        
        Args:
            new_bookmarks: List of new bookmarks
            modified_bookmarks: List of modified bookmarks
            deleted_urls: List of deleted URLs
            
        Returns:
            BookmarkTree with changes
        """
        tree = BookmarkFolder(
            name="Incremental Changes",
            date_added=datetime.now(),
            date_modified=datetime.now()
        )
        
        # Add new and modified bookmarks
        for bookmark in new_bookmarks + modified_bookmarks:
            tree.add_child(bookmark)
        
        # Note: Deleted URLs are tracked separately
        # They need to be handled during sync
        
        return tree
