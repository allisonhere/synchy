"""Conflict detection and resolution for bookmarks."""

from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime
from src.core.models import Bookmark
from src.utils.logger import setup_logger

logger = setup_logger()


@dataclass
class BookmarkConflict:
    """Represents a conflict between two bookmarks."""
    url: str
    bookmark1: Bookmark
    bookmark2: Bookmark
    source1_name: str
    source2_name: str
    conflict_type: str  # 'metadata', 'title', 'date'
    
    def __str__(self):
        return f"Conflict: {self.url} - {self.conflict_type}"


class ConflictResolver:
    """Resolves conflicts between bookmarks."""
    
    def __init__(self):
        self.conflicts: List[BookmarkConflict] = []
    
    def detect_conflicts(self, bookmark1: Bookmark, bookmark2: Bookmark,
                        source1_name: str, source2_name: str) -> Optional[BookmarkConflict]:
        """
        Detect if two bookmarks with the same URL have conflicts.
        
        Args:
            bookmark1: First bookmark
            bookmark2: Second bookmark
            source1_name: Name of first source
            source2_name: Name of second source
            
        Returns:
            BookmarkConflict if conflict detected, None otherwise
        """
        # Normalize URLs for comparison
        url1 = self._normalize_url(bookmark1.url)
        url2 = self._normalize_url(bookmark2.url)
        
        if url1 != url2:
            return None  # Different URLs, not a conflict
        
        # Check for conflicts
        conflicts = []
        
        if bookmark1.title != bookmark2.title:
            conflicts.append('title')
        
        if bookmark1.date_added != bookmark2.date_added:
            conflicts.append('date')
        
        if bookmark1.favicon != bookmark2.favicon:
            conflicts.append('metadata')
        
        if conflicts:
            conflict = BookmarkConflict(
                url=bookmark1.url,
                bookmark1=bookmark1,
                bookmark2=bookmark2,
                source1_name=source1_name,
                source2_name=source2_name,
                conflict_type=', '.join(conflicts)
            )
            self.conflicts.append(conflict)
            return conflict
        
        return None
    
    def resolve_conflict(self, conflict: BookmarkConflict, resolution: str) -> Bookmark:
        """
        Resolve a conflict by choosing a resolution strategy.
        
        Args:
            conflict: The conflict to resolve
            resolution: Resolution strategy ('keep_first', 'keep_second', 'keep_newer', 'merge')
            
        Returns:
            Resolved bookmark
        """
        if resolution == 'keep_first':
            return conflict.bookmark1
        elif resolution == 'keep_second':
            return conflict.bookmark2
        elif resolution == 'keep_newer':
            if conflict.bookmark1.date_modified > conflict.bookmark2.date_modified:
                return conflict.bookmark1
            else:
                return conflict.bookmark2
        elif resolution == 'merge':
            # Merge metadata: use newer title, newer date
            if conflict.bookmark1.date_modified > conflict.bookmark2.date_modified:
                resolved = conflict.bookmark1
                # But keep both titles if significantly different
                if conflict.bookmark1.title != conflict.bookmark2.title:
                    resolved.title = f"{conflict.bookmark1.title} / {conflict.bookmark2.title}"
            else:
                resolved = conflict.bookmark2
                if conflict.bookmark1.title != conflict.bookmark2.title:
                    resolved.title = f"{conflict.bookmark1.title} / {conflict.bookmark2.title}"
            return resolved
        else:
            # Default: keep newer
            return self.resolve_conflict(conflict, 'keep_newer')
    
    def _normalize_url(self, url: str) -> str:
        """Normalize URL for comparison."""
        url = url.lower().strip()
        
        # Remove trailing slash
        if url.endswith('/'):
            url = url[:-1]
        
        # Normalize protocol (http vs https)
        # For now, we treat them as different, but could normalize
        # url = url.replace('https://', 'http://')
        
        return url
    
    def get_conflicts_summary(self) -> str:
        """Get a summary of all conflicts."""
        if not self.conflicts:
            return "No conflicts detected."
        
        summary = f"Found {len(self.conflicts)} conflict(s):\n"
        for i, conflict in enumerate(self.conflicts, 1):
            summary += f"  {i}. {conflict.url}\n"
            summary += f"     Type: {conflict.conflict_type}\n"
            summary += f"     {conflict.source1_name}: {conflict.bookmark1.title}\n"
            summary += f"     {conflict.source2_name}: {conflict.bookmark2.title}\n"
        
        return summary
