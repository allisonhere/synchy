"""Firefox browser adapter."""

import sqlite3
import uuid
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Tuple
from src.browsers.base import BrowserAdapter
from src.core.models import BookmarkTree, BookmarkFolder, Bookmark
from src.utils.paths import get_firefox_profile_path, get_firefox_places_db, is_firefox_locked
from src.utils.logger import setup_logger
from src.utils.validators import is_valid_url

logger = setup_logger()


class FirefoxAdapter(BrowserAdapter):
    """Adapter for reading and writing Firefox bookmarks."""
    
    # Firefox bookmark types
    TYPE_BOOKMARK = 1
    TYPE_FOLDER = 2
    TYPE_SEPARATOR = 3
    
    # Root folder IDs (these are standard in Firefox)
    ROOT_BOOKMARKS_MENU = 2
    ROOT_BOOKMARKS_TOOLBAR = 3
    ROOT_UNFILED = 4
    ROOT_MOBILE = 5
    
    def __init__(self, profile_name: Optional[str] = None):
        """
        Initialize Firefox adapter.
        
        Args:
            profile_name: Name of Firefox profile (None for default)
        """
        self.profile_name = profile_name
        self.profile_path = get_firefox_profile_path(profile_name)
        self.places_db = get_firefox_places_db(profile_name)
        
        if not self.places_db or not self.places_db.exists():
            raise FileNotFoundError(
                f"Firefox places.sqlite not found for profile '{profile_name or 'default'}'"
            )
    
    def get_profile_path(self) -> Path:
        """Get path to Firefox profile directory."""
        return self.profile_path
    
    def is_locked(self) -> bool:
        """Check if Firefox database is locked."""
        return is_firefox_locked(self.profile_name)
    
    def _timestamp_to_datetime(self, timestamp: int) -> datetime:
        """Convert Firefox timestamp (microseconds) to datetime."""
        # Firefox uses microseconds since epoch
        return datetime.fromtimestamp(timestamp / 1000000)
    
    def _datetime_to_timestamp(self, dt: datetime) -> int:
        """Convert datetime to Firefox timestamp (microseconds)."""
        return int(dt.timestamp() * 1000000)
    
    def _generate_guid(self) -> str:
        """
        Generate a Firefox-style GUID.
        Firefox uses 12-byte GUIDs in a specific format.
        Format: {8hex-4hex-4hex-4hex-12hex}
        """
        guid = uuid.uuid4()
        return str(guid)
    
    def _get_or_create_place(self, conn: sqlite3.Connection, url: str, title: str) -> int:
        """
        Get existing place_id or create new entry in moz_places.
        
        Args:
            conn: Database connection
            url: URL to look up or create
            title: Title for the URL
            
        Returns:
            place_id (integer)
        """
        cursor = conn.cursor()
        
        # Check if URL already exists
        cursor.execute("SELECT id FROM moz_places WHERE url = ?", (url,))
        row = cursor.fetchone()
        
        if row:
            place_id = row[0]
            # Update title if provided and different
            if title:
                cursor.execute("UPDATE moz_places SET title = ? WHERE id = ?", (title, place_id))
            return place_id
        
        # Create new place entry
        now = self._datetime_to_timestamp(datetime.now())
        cursor.execute("""
            INSERT INTO moz_places (url, title, rev_host, visit_count, hidden, typed, frecency, last_visit_date)
            VALUES (?, ?, ?, 0, 0, 0, 0, ?)
        """, (url, title, self._reverse_host(url), now))
        
        return cursor.lastrowid
    
    def _reverse_host(self, url: str) -> str:
        """Reverse host for Firefox's rev_host field."""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            host = parsed.netloc
            if host:
                return '.'.join(reversed(host.split('.')))
        except:
            pass
        return ''
    
    def _get_next_position(self, conn: sqlite3.Connection, parent_id: int) -> int:
        """Get the next position for a bookmark in a folder."""
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(position) FROM moz_bookmarks WHERE parent = ?", (parent_id,))
        row = cursor.fetchone()
        if row and row[0] is not None:
            return row[0] + 1
        return 0
    
    def _write_bookmark_item(self, conn: sqlite3.Connection, item: Bookmark | BookmarkFolder,
                            parent_id: int, position: int) -> Optional[int]:
        """
        Write a bookmark or folder to the database.
        
        Args:
            conn: Database connection
            item: Bookmark or BookmarkFolder to write
            parent_id: Parent folder ID
            position: Position within parent
            
        Returns:
            Bookmark ID if successful, None otherwise
        """
        cursor = conn.cursor()
        now = self._datetime_to_timestamp(datetime.now())
        guid = self._generate_guid()
        
        if isinstance(item, Bookmark):
            # Write bookmark
            # First ensure place exists
            place_id = self._get_or_create_place(conn, item.url, item.title)
            
            date_added = self._datetime_to_timestamp(item.date_added)
            date_modified = self._datetime_to_timestamp(item.date_modified)
            
            cursor.execute("""
                INSERT INTO moz_bookmarks 
                (type, fk, parent, position, title, dateAdded, lastModified, guid)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                self.TYPE_BOOKMARK,
                place_id,
                parent_id,
                position,
                item.title,
                date_added,
                date_modified,
                guid
            ))
            
            bookmark_id = cursor.lastrowid
            
            # Write children (if any - bookmarks shouldn't have children, but handle gracefully)
            if hasattr(item, 'children') and item.children:
                logger.warning(f"Bookmark {item.title} has children, which is unexpected")
            
            return bookmark_id
            
        elif isinstance(item, BookmarkFolder):
            # Write folder
            date_added = self._datetime_to_timestamp(item.date_added)
            date_modified = self._datetime_to_timestamp(item.date_modified)
            
            cursor.execute("""
                INSERT INTO moz_bookmarks 
                (type, parent, position, title, dateAdded, lastModified, guid)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                self.TYPE_FOLDER,
                parent_id,
                position,
                item.name,
                date_added,
                date_modified,
                guid
            ))
            
            folder_id = cursor.lastrowid
            
            # Write children
            child_position = 0
            for child in item.children:
                child_id = self._write_bookmark_item(conn, child, folder_id, child_position)
                if child_id:
                    child_position += 1
            
            return folder_id
        
        return None
    
    def read_bookmarks(self) -> BookmarkTree:
        """
        Read bookmarks from Firefox places.sqlite.
        
        Returns:
            BookmarkTree with all bookmarks
        """
        if self.is_locked():
            raise RuntimeError("Firefox database is locked. Please close Firefox and try again.")
        
        conn = sqlite3.connect(str(self.places_db))
        conn.row_factory = sqlite3.Row
        
        try:
            # Create root folder
            root = BookmarkFolder(
                name="Firefox Bookmarks",
                date_added=datetime.now(),
                date_modified=datetime.now()
            )
            
            # Read all bookmarks and folders
            cursor = conn.cursor()
            
            # Get all bookmark items
            # Note: favicon_id removed as it may not exist in all Firefox versions
            cursor.execute("""
                SELECT 
                    b.id,
                    b.type,
                    b.parent,
                    b.title,
                    b.dateAdded,
                    b.lastModified,
                    b.fk as place_id,
                    p.url,
                    p.title as url_title
                FROM moz_bookmarks b
                LEFT JOIN moz_places p ON b.fk = p.id
                ORDER BY b.parent, b.position
            """)
            
            rows = cursor.fetchall()
            
            # Build a map of id -> BookmarkFolder or Bookmark
            items: Dict[int, BookmarkFolder | Bookmark] = {}
            parent_map: Dict[int, List[int]] = {}  # parent_id -> [child_ids]
            
            for row in rows:
                item_id = row['id']
                item_type = row['type']
                parent_id = row['parent']
                title = row['title'] or ""
                
                if item_type == self.TYPE_FOLDER:
                    date_added = self._timestamp_to_datetime(row['dateAdded']) if row['dateAdded'] else datetime.now()
                    date_modified = self._timestamp_to_datetime(row['lastModified']) if row['lastModified'] else datetime.now()
                    
                    folder = BookmarkFolder(
                        name=title,
                        date_added=date_added,
                        date_modified=date_modified
                    )
                    items[item_id] = folder
                    
                    if parent_id not in parent_map:
                        parent_map[parent_id] = []
                    parent_map[parent_id].append(item_id)
                
                elif item_type == self.TYPE_BOOKMARK and row['url']:
                    url = row['url']
                    if not is_valid_url(url):
                        continue
                    
                    date_added = self._timestamp_to_datetime(row['dateAdded']) if row['dateAdded'] else datetime.now()
                    date_modified = self._timestamp_to_datetime(row['lastModified']) if row['lastModified'] else datetime.now()
                    
                    bookmark_title = row['url_title'] or title or url
                    
                    bookmark = Bookmark(
                        title=bookmark_title,
                        url=url,
                        date_added=date_added,
                        date_modified=date_modified
                    )
                    items[item_id] = bookmark
                    
                    if parent_id not in parent_map:
                        parent_map[parent_id] = []
                    parent_map[parent_id].append(item_id)
            
            # Build hierarchy
            def build_tree(node_id: int) -> Optional[BookmarkFolder | Bookmark]:
                if node_id not in items:
                    return None
                
                item = items[node_id]
                
                # Add children if it's a folder
                if isinstance(item, BookmarkFolder):
                    child_ids = parent_map.get(node_id, [])
                    for child_id in child_ids:
                        child = build_tree(child_id)
                        if child:
                            item.add_child(child)
                
                return item
            
            # Start from root folders (excluding root 1 which is the root container)
            root_folder_ids = [
                self.ROOT_BOOKMARKS_MENU,
                self.ROOT_BOOKMARKS_TOOLBAR,
                self.ROOT_UNFILED,
                self.ROOT_MOBILE
            ]
            
            for root_folder_id in root_folder_ids:
                if root_folder_id in parent_map:
                    for child_id in parent_map[root_folder_id]:
                        child = build_tree(child_id)
                        if child:
                            root.add_child(child)
            
            logger.info(f"Read {len(root.get_all_bookmarks())} bookmarks from Firefox")
            return root
            
        finally:
            conn.close()
    
    def write_bookmarks(self, tree: BookmarkTree, clear_existing: bool = False) -> bool:
        """
        Write bookmarks to Firefox places.sqlite.
        
        Args:
            tree: BookmarkTree to write
            clear_existing: If True, clear existing bookmarks before writing
            
        Returns:
            True if successful, False otherwise
        """
        if self.is_locked():
            raise RuntimeError("Firefox database is locked. Please close Firefox and try again.")
        
        conn = sqlite3.connect(str(self.places_db))
        
        try:
            conn.execute("BEGIN TRANSACTION")
            
            if clear_existing:
                # Clear existing bookmarks (but keep root folders)
                logger.info("Clearing existing bookmarks...")
                cursor = conn.cursor()
                
                # Delete all bookmarks except root folders
                root_folder_ids = [
                    self.ROOT_BOOKMARKS_MENU,
                    self.ROOT_BOOKMARKS_TOOLBAR,
                    self.ROOT_UNFILED,
                    self.ROOT_MOBILE
                ]
                
                # Delete children of root folders
                for root_id in root_folder_ids:
                    cursor.execute("DELETE FROM moz_bookmarks WHERE parent = ?", (root_id,))
            
            # Write bookmarks to Bookmarks Menu (root 2) by default
            # Distribute to different roots based on folder names if needed
            target_root = self.ROOT_BOOKMARKS_MENU
            
            # Check if tree has specific root folders we should map to
            # Handle both Firefox and Chrome naming conventions
            root_mapping = {
                # Firefox names
                "Bookmarks Bar": self.ROOT_BOOKMARKS_TOOLBAR,
                "Bookmarks Toolbar": self.ROOT_BOOKMARKS_TOOLBAR,
                "Other Bookmarks": self.ROOT_UNFILED,
                "Unfiled Bookmarks": self.ROOT_UNFILED,
                "Mobile Bookmarks": self.ROOT_MOBILE,
                # Chrome names (from reading Chrome bookmarks)
                "Bookmark Bar": self.ROOT_BOOKMARKS_TOOLBAR,
                "Other": self.ROOT_UNFILED,
                "Synced": self.ROOT_MOBILE,
            }
            
            # Write children to appropriate root folders
            position = 0
            written_count = 0
            
            for child in tree.children:
                if isinstance(child, BookmarkFolder):
                    # Check if this folder should go to a specific root
                    folder_name = child.name
                    target = root_mapping.get(folder_name, target_root)
                    
                    # Write folder and its contents
                    folder_id = self._write_bookmark_item(conn, child, target, position)
                    if folder_id:
                        position += 1
                        written_count += len(child.get_all_bookmarks())
                elif isinstance(child, Bookmark):
                    # Write bookmark directly to root
                    bookmark_id = self._write_bookmark_item(conn, child, target_root, position)
                    if bookmark_id:
                        position += 1
                        written_count += 1
            
            # Update sync change counter (Firefox uses this for sync)
            # Check if column exists first (some Firefox versions may not have it)
            cursor = conn.cursor()
            try:
                cursor.execute("PRAGMA table_info(moz_bookmarks)")
                columns = [row[1] for row in cursor.fetchall()]
                if 'syncChangeCounter' in columns:
                    cursor.execute("UPDATE moz_bookmarks SET syncChangeCounter = 1 WHERE syncChangeCounter IS NULL")
            except Exception as e:
                logger.debug(f"Could not update syncChangeCounter: {e}")
            
            conn.commit()
            logger.info(f"Successfully wrote {written_count} bookmarks to Firefox")
            return True
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to write Firefox bookmarks: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return False
        finally:
            conn.close()
