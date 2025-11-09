"""Merge engine for combining bookmarks from different sources."""

from typing import List, Set, Dict, Tuple, Optional
from enum import Enum
from datetime import datetime
from urllib.parse import urlparse, urlunparse
from src.core.models import BookmarkTree, BookmarkFolder, Bookmark
from src.core.conflict_resolver import ConflictResolver, BookmarkConflict
from src.utils.logger import setup_logger

logger = setup_logger()


class MergeStrategy(Enum):
    """Merge strategies."""
    KEEP_ALL = "keep_all"  # Keep all bookmarks, rename duplicates
    TIMESTAMP = "timestamp"  # Keep newer bookmark when duplicate
    FIREFOX_PRIORITY = "firefox_priority"  # Firefox bookmarks take precedence
    CHROME_PRIORITY = "chrome_priority"  # Chrome bookmarks take precedence
    SMART = "smart"  # Smart merge with folder awareness


class BookmarkMerger:
    """Merges bookmark trees from different sources."""
    
    def __init__(self, strategy: MergeStrategy = MergeStrategy.KEEP_ALL,
                 enable_fuzzy_matching: bool = True,
                 enable_name_matching: bool = True):
        """
        Initialize merger.
        
        Args:
            strategy: Merge strategy to use
            enable_fuzzy_matching: Enable fuzzy URL matching
            enable_name_matching: Enable name+URL matching for duplicates
        """
        self.strategy = strategy
        self.enable_fuzzy_matching = enable_fuzzy_matching
        self.enable_name_matching = enable_name_matching
        self.conflict_resolver = ConflictResolver()
        self.duplicate_matches: List[Tuple[Bookmark, Bookmark, str]] = []  # (bookmark1, bookmark2, match_type)
    
    def merge(self, tree1: BookmarkTree, tree2: BookmarkTree, 
              source1_name: str = "Source 1", source2_name: str = "Source 2") -> BookmarkTree:
        """
        Merge two bookmark trees.
        
        Args:
            tree1: First bookmark tree
            tree2: Second bookmark tree
            source1_name: Name of first source (for duplicate naming)
            source2_name: Name of second source (for duplicate naming)
            
        Returns:
            Merged BookmarkTree
        """
        # Reset conflict resolver for new merge
        self.conflict_resolver = ConflictResolver()
        self.duplicate_matches = []
        
        merged = BookmarkFolder(
            name="Merged Bookmarks",
            date_added=min(tree1.date_added, tree2.date_added),
            date_modified=max(tree1.date_modified, tree2.date_modified)
        )
        
        if self.strategy == MergeStrategy.KEEP_ALL:
            result = self._merge_keep_all(tree1, tree2, merged, source1_name, source2_name)
        elif self.strategy == MergeStrategy.TIMESTAMP:
            result = self._merge_timestamp(tree1, tree2, merged)
        elif self.strategy == MergeStrategy.FIREFOX_PRIORITY:
            result = self._merge_priority(tree1, tree2, merged, source1_name)
        elif self.strategy == MergeStrategy.CHROME_PRIORITY:
            result = self._merge_priority(tree2, tree1, merged, source2_name)
        elif self.strategy == MergeStrategy.SMART:
            result = self._merge_smart(tree1, tree2, merged)
        else:
            result = self._merge_keep_all(tree1, tree2, merged, source1_name, source2_name)
        
        # Log conflicts if any
        if self.conflict_resolver.conflicts:
            logger.info(f"Detected {len(self.conflict_resolver.conflicts)} conflict(s)")
            logger.debug(self.conflict_resolver.get_conflicts_summary())
        
        return result
    
    def get_conflicts(self) -> List[BookmarkConflict]:
        """Get list of detected conflicts."""
        return self.conflict_resolver.conflicts
    
    def get_duplicate_matches(self) -> List[Tuple[Bookmark, Bookmark, str]]:
        """Get list of duplicate matches found."""
        return self.duplicate_matches
    
    def _merge_keep_all(self, tree1: BookmarkTree, tree2: BookmarkTree,
                       merged: BookmarkFolder, source1_name: str, source2_name: str) -> BookmarkTree:
        """Merge keeping all bookmarks, renaming duplicates."""
        # Build comprehensive duplicate detection
        tree1_bookmarks = tree1.get_all_bookmarks()
        tree2_bookmarks = tree2.get_all_bookmarks()
        
        # Build matching maps
        tree1_url_map = {self._normalize_url(b.url): b for b in tree1_bookmarks}
        tree1_name_url_map = {(b.title.lower(), self._normalize_url(b.url)): b for b in tree1_bookmarks}
        
        # Detect duplicates and conflicts
        tree2_duplicates: Set[str] = set()
        for b2 in tree2_bookmarks:
            normalized_url = self._normalize_url(b2.url)
            
            # Check for exact URL match
            if normalized_url in tree1_url_map:
                b1 = tree1_url_map[normalized_url]
                conflict = self.conflict_resolver.detect_conflicts(b1, b2, source1_name, source2_name)
                tree2_duplicates.add(normalized_url)
                self.duplicate_matches.append((b1, b2, 'url'))
            
            # Check for name+URL match if enabled (only if exact URL didn't match)
            if normalized_url not in tree2_duplicates and self.enable_name_matching:
                name_url_key = (b2.title.lower(), normalized_url)
                if name_url_key in tree1_name_url_map:
                    b1 = tree1_name_url_map[name_url_key]
                    conflict = self.conflict_resolver.detect_conflicts(b1, b2, source1_name, source2_name)
                    tree2_duplicates.add(normalized_url)
                    self.duplicate_matches.append((b1, b2, 'name+url'))
            
            # Check for fuzzy URL match if enabled (only if no other match found)
            if normalized_url not in tree2_duplicates and self.enable_fuzzy_matching:
                fuzzy_match = self._find_fuzzy_match(b2, tree1_bookmarks)
                if fuzzy_match:
                    conflict = self.conflict_resolver.detect_conflicts(fuzzy_match, b2, source1_name, source2_name)
                    tree2_duplicates.add(normalized_url)
                    self.duplicate_matches.append((fuzzy_match, b2, 'fuzzy_url'))
        
        # Add all items from tree1
        for child in tree1.children:
            merged.add_child(self._deep_copy(child))
        
        # Add items from tree2, renaming duplicates
        for child in tree2.children:
            copied = self._deep_copy(child)
            self._rename_duplicates(copied, tree2_duplicates, source2_name)
            merged.add_child(copied)
        
        logger.info(f"Merged {len(merged.get_all_bookmarks())} bookmarks using keep_all strategy")
        if tree2_duplicates:
            logger.info(f"Found {len(tree2_duplicates)} duplicate URL(s)")
        if self.duplicate_matches:
            logger.info(f"Found {len(self.duplicate_matches)} duplicate match(es) (including fuzzy matches)")
        return merged
    
    def _merge_timestamp(self, tree1: BookmarkTree, tree2: BookmarkTree, merged: BookmarkFolder) -> BookmarkTree:
        """Merge keeping newer bookmarks when duplicates found."""
        # Build URL -> Bookmark map from both trees with conflict detection
        url_map: dict[str, Bookmark] = {}
        
        tree1_bookmarks = tree1.get_all_bookmarks()
        tree2_bookmarks = tree2.get_all_bookmarks()
        
        for bookmark in tree1_bookmarks:
            normalized_url = self._normalize_url(bookmark.url)
            if normalized_url not in url_map:
                url_map[normalized_url] = bookmark
            elif bookmark.date_modified > url_map[normalized_url].date_modified:
                # Detect conflict before replacing
                self.conflict_resolver.detect_conflicts(
                    url_map[normalized_url], bookmark, "Source 1", "Source 1"
                )
                url_map[normalized_url] = bookmark
        
        for bookmark in tree2_bookmarks:
            normalized_url = self._normalize_url(bookmark.url)
            if normalized_url not in url_map:
                url_map[normalized_url] = bookmark
            else:
                # Check for conflicts
                existing = url_map[normalized_url]
                conflict = self.conflict_resolver.detect_conflicts(
                    existing, bookmark, "Source 1", "Source 2"
                )
                # Keep newer
                if bookmark.date_modified > existing.date_modified:
                    url_map[normalized_url] = bookmark
        
        # Add all bookmarks to root (simplified - could preserve structure better)
        for bookmark in url_map.values():
            merged.add_child(self._deep_copy(bookmark))
        
        logger.info(f"Merged {len(merged.get_all_bookmarks())} bookmarks using timestamp strategy")
        return merged
    
    def _merge_priority(self, primary: BookmarkTree, secondary: BookmarkTree,
                       merged: BookmarkFolder, primary_name: str) -> BookmarkTree:
        """Merge with priority to primary source."""
        primary_bookmarks = primary.get_all_bookmarks()
        primary_urls: Set[str] = {self._normalize_url(b.url) for b in primary_bookmarks}
        
        # Detect conflicts
        secondary_bookmarks = secondary.get_all_bookmarks()
        for b2 in secondary_bookmarks:
            normalized_url = self._normalize_url(b2.url)
            if normalized_url in primary_urls:
                # Find matching bookmark in primary
                for b1 in primary_bookmarks:
                    if self._normalize_url(b1.url) == normalized_url:
                        self.conflict_resolver.detect_conflicts(b1, b2, primary_name, "Secondary")
                        break
        
        # Add all from primary
        for child in primary.children:
            merged.add_child(self._deep_copy(child))
        
        # Add from secondary only if not in primary
        for child in secondary.children:
            copied = self._deep_copy(child)
            self._filter_duplicates(copied, primary_urls)
            if (isinstance(copied, BookmarkFolder) and copied.children) or isinstance(copied, Bookmark):
                merged.add_child(copied)
        
        logger.info(f"Merged {len(merged.get_all_bookmarks())} bookmarks using priority strategy")
        return merged
    
    def _merge_smart(self, tree1: BookmarkTree, tree2: BookmarkTree, merged: BookmarkFolder) -> BookmarkTree:
        """Smart merge preserving folder structure."""
        # Merge folders by name, bookmarks by URL
        folder_map: dict[str, BookmarkFolder] = {}
        url_set: Set[str] = set()
        
        def add_tree_to_merged(tree: BookmarkTree):
            for child in tree.children:
                if isinstance(child, BookmarkFolder):
                    folder_name = child.name
                    if folder_name not in folder_map:
                        folder_map[folder_name] = BookmarkFolder(
                            name=folder_name,
                            date_added=child.date_added,
                            date_modified=child.date_modified
                        )
                    # Merge folder contents
                    for subchild in child.children:
                        if isinstance(subchild, Bookmark):
                            if subchild.url.lower() not in url_set:
                                folder_map[folder_name].add_child(self._deep_copy(subchild))
                                url_set.add(subchild.url.lower())
                        elif isinstance(subchild, BookmarkFolder):
                            # Recursively handle nested folders
                            add_tree_to_merged(BookmarkFolder(
                                name="temp",
                                date_added=datetime.now(),
                                date_modified=datetime.now(),
                                children=[subchild]
                            ))
                elif isinstance(child, Bookmark):
                    if child.url.lower() not in url_set:
                        merged.add_child(self._deep_copy(child))
                        url_set.add(child.url.lower())
        
        add_tree_to_merged(tree1)
        add_tree_to_merged(tree2)
        
        # Add merged folders to root
        for folder in folder_map.values():
            if folder.children:
                merged.add_child(folder)
        
        logger.info(f"Merged {len(merged.get_all_bookmarks())} bookmarks using smart strategy")
        return merged
    
    def _deep_copy(self, item: BookmarkFolder | Bookmark) -> BookmarkFolder | Bookmark:
        """Create a deep copy of a bookmark or folder."""
        if isinstance(item, Bookmark):
            return Bookmark(
                title=item.title,
                url=item.url,
                date_added=item.date_added,
                date_modified=item.date_modified,
                favicon=item.favicon,
                tags=item.tags.copy() if item.tags else []
            )
        elif isinstance(item, BookmarkFolder):
            folder = BookmarkFolder(
                name=item.name,
                date_added=item.date_added,
                date_modified=item.date_modified
            )
            for child in item.children:
                folder.add_child(self._deep_copy(child))
            return folder
        return item
    
    def _rename_duplicates(self, item: BookmarkFolder | Bookmark, existing_urls: Set[str], source_name: str):
        """Rename duplicates by appending source name."""
        if isinstance(item, Bookmark):
            normalized_url = self._normalize_url(item.url)
            if normalized_url in existing_urls:
                item.title = f"{item.title} ({source_name})"
        elif isinstance(item, BookmarkFolder):
            for child in item.children:
                self._rename_duplicates(child, existing_urls, source_name)
    
    def _filter_duplicates(self, item: BookmarkFolder | Bookmark, existing_urls: Set[str]):
        """Remove items that already exist (for priority merge)."""
        if isinstance(item, Bookmark):
            if self._normalize_url(item.url) in existing_urls:
                return None  # Mark for removal
        elif isinstance(item, BookmarkFolder):
            filtered_children = []
            for child in item.children:
                filtered = self._filter_duplicates(child, existing_urls)
                if filtered is not None:
                    filtered_children.append(filtered)
            item.children = filtered_children
        return item
    
    def _normalize_url(self, url: str) -> str:
        """
        Normalize URL for comparison.
        
        Handles:
        - Case insensitivity
        - Trailing slashes
        - Protocol normalization (optional)
        """
        url = url.lower().strip()
        
        # Remove trailing slash (except for root URLs)
        if url.endswith('/') and len(url) > 1:
            url = url[:-1]
        
        # Remove fragment (#anchor)
        if '#' in url:
            url = url.split('#')[0]
        
        # Remove default ports
        parsed = urlparse(url)
        if parsed.port:
            if (parsed.scheme == 'http' and parsed.port == 80) or \
               (parsed.scheme == 'https' and parsed.port == 443):
                # Reconstruct without port
                netloc = parsed.hostname
                if parsed.username or parsed.password:
                    auth = f"{parsed.username}:{parsed.password}@" if parsed.password else f"{parsed.username}@"
                    netloc = auth + netloc
                url = urlunparse((
                    parsed.scheme,
                    netloc,
                    parsed.path,
                    parsed.params,
                    parsed.query,
                    ''  # fragment
                ))
        
        return url
    
    def _find_fuzzy_match(self, bookmark: Bookmark, candidates: List[Bookmark]) -> Optional[Bookmark]:
        """
        Find fuzzy URL match for a bookmark.
        
        Handles:
        - http vs https
        - www vs non-www
        - Trailing slash differences
        - Query parameter differences (optional)
        """
        normalized_target = self._normalize_url(bookmark.url)
        target_parsed = urlparse(normalized_target)
        
        for candidate in candidates:
            normalized_candidate = self._normalize_url(candidate.url)
            candidate_parsed = urlparse(normalized_candidate)
            
            # Check if domains match (with www normalization)
            target_domain = target_parsed.netloc.replace('www.', '')
            candidate_domain = candidate_parsed.netloc.replace('www.', '')
            
            if target_domain != candidate_domain:
                continue
            
            # Check if paths match (normalized)
            target_path = target_parsed.path.rstrip('/')
            candidate_path = candidate_parsed.path.rstrip('/')
            
            if target_path != candidate_path:
                continue
            
            # Protocol difference (http vs https) is acceptable for fuzzy match
            # Query parameters difference is acceptable
            return candidate
        
        return None
    
    def _urls_are_similar(self, url1: str, url2: str) -> bool:
        """
        Check if two URLs are similar (fuzzy match).
        
        Returns True if URLs are considered the same despite minor differences.
        """
        norm1 = self._normalize_url(url1)
        norm2 = self._normalize_url(url2)
        
        if norm1 == norm2:
            return True
        
        parsed1 = urlparse(norm1)
        parsed2 = urlparse(norm2)
        
        # Compare domains (normalize www)
        domain1 = parsed1.netloc.replace('www.', '')
        domain2 = parsed2.netloc.replace('www.', '')
        
        if domain1 != domain2:
            return False
        
        # Compare paths (normalize trailing slash)
        path1 = parsed1.path.rstrip('/')
        path2 = parsed2.path.rstrip('/')
        
        if path1 != path2:
            return False
        
        # Protocol difference (http vs https) is acceptable
        # Query and fragment differences are acceptable for fuzzy match
        return True
