# Bookmark Sync App - Implementation Plan

## Overview
A cross-platform application to synchronize bookmarks between Firefox and Chrome browsers with bidirectional sync, merge capabilities, and backup functionality.

## Core Requirements

### 1. Bidirectional Sync
- Sync from Firefox → Chrome
- Sync from Chrome → Firefox
- Detect and handle conflicts intelligently

### 2. Merge Option
- Merge bookmarks from both browsers
- Handle duplicate detection
- Preserve folder structure
- Conflict resolution strategies:
  - Keep both (rename duplicates)
  - Keep newer (timestamp-based)
  - Keep Firefox/Chrome (user preference)
  - Manual resolution

### 3. Backup System
- Automatic backup before any sync operation
- Timestamped backups
- Restore functionality
- Backup location configuration

## Technical Architecture

### Technology Stack
- **Language**: Python 3.9+
- **Database**: SQLite3 (for reading browser databases)
- **JSON**: For Chrome bookmark format
- **GUI Framework**: Tkinter or PyQt6 (optional, CLI-first)
- **Dependencies**:
  - `sqlite3` (built-in)
  - `json` (built-in)
  - `shutil` (backup operations)
  - `pathlib` (cross-platform paths)
  - `datetime` (timestamps)
  - `hashlib` (duplicate detection)

### Browser Bookmark Formats

#### Firefox
- **Location**: `~/.mozilla/firefox/<profile>/places.sqlite`
- **Format**: SQLite database
- **Key Tables**:
  - `moz_bookmarks` - bookmark entries
  - `moz_places` - URL information
  - `moz_favicons` - favicon data
- **Structure**: Hierarchical folders with parent-child relationships

#### Chrome/Chromium
- **Location**: `~/.config/google-chrome/Default/Bookmarks` (Linux)
- **Format**: JSON file
- **Structure**: Nested JSON with `roots` containing:
  - `bookmark_bar`
  - `other`
  - `synced`
- **Fields**: `name`, `url`, `date_added`, `date_modified`, `children`

## Project Structure

```
bookmark-sync/
├── README.md
├── requirements.txt
├── setup.py
├── config.json                 # User configuration
├── src/
│   ├── __init__.py
│   ├── main.py                 # CLI entry point
│   ├── gui.py                  # GUI entry point (optional)
│   ├── core/
│   │   ├── __init__.py
│   │   ├── sync_engine.py      # Main sync logic
│   │   ├── merger.py           # Merge algorithms
│   │   └── conflict_resolver.py # Conflict handling
│   ├── browsers/
│   │   ├── __init__.py
│   │   ├── base.py             # Abstract base class
│   │   ├── firefox.py          # Firefox adapter
│   │   └── chrome.py           # Chrome adapter
│   ├── backup/
│   │   ├── __init__.py
│   │   ├── backup_manager.py   # Backup operations
│   │   └── restore_manager.py  # Restore operations
│   └── utils/
│       ├── __init__.py
│       ├── paths.py            # Browser path detection
│       ├── logger.py           # Logging utilities
│       └── validators.py       # Input validation
├── backups/                    # Backup storage directory
└── tests/
    ├── test_firefox.py
    ├── test_chrome.py
    ├── test_sync.py
    └── test_merge.py
```

## Implementation Phases

### Phase 1: Core Infrastructure (Week 1)
1. **Project Setup**
   - Initialize project structure
   - Set up virtual environment
   - Create requirements.txt
   - Basic configuration system

2. **Browser Path Detection**
   - Detect Firefox profiles
   - Detect Chrome/Chromium profiles
   - Handle multiple profiles
   - Cross-platform path handling (Linux, macOS, Windows)

3. **Backup System**
   - Create backup directory structure
   - Implement backup before sync
   - Timestamped backup naming
   - Backup verification

### Phase 2: Browser Adapters (Week 2)
1. **Firefox Adapter**
   - Connect to places.sqlite
   - Read bookmarks with folder structure
   - Write bookmarks back
   - Handle locked database (browser open)
   - Preserve metadata (dates, favicons)

2. **Chrome Adapter**
   - Read Bookmarks JSON file
   - Parse nested structure
   - Write Bookmarks JSON file
   - Handle file locking
   - Preserve metadata

3. **Unified Data Model**
   - Common bookmark representation
   - Folder hierarchy mapping
   - Metadata preservation

### Phase 3: Merge Engine (Week 3)
1. **Duplicate Detection**
   - URL-based matching
   - Name + URL matching
   - Fuzzy matching for similar URLs

2. **Merge Strategies**
   - Simple merge (keep all, rename duplicates)
   - Timestamp-based merge (keep newer)
   - Source preference (Firefox/Chrome priority)
   - Folder-aware merging

3. **Conflict Resolution**
   - Detect conflicts (same URL, different metadata)
   - Conflict resolution UI/logic
   - Manual resolution support

### Phase 4: Sync Engine (Week 4)
1. **Bidirectional Sync**
   - Firefox → Chrome sync
   - Chrome → Firefox sync
   - Dry-run mode (preview changes)
   - Change detection (only sync differences)

2. **Sync Modes**
   - Full sync (replace all)
   - Incremental sync (only new/changed)
   - Merge sync (combine both)

3. **Error Handling**
   - Browser not found
   - Database locked
   - Permission errors
   - Corrupted data handling

### Phase 5: User Interface (Week 5)
1. **CLI Interface**
   - Command-line arguments
   - Interactive mode
   - Configuration wizard
   - Progress indicators

2. **GUI Interface (Optional)**
   - Simple GUI for non-technical users
   - Profile selection
   - Sync options
   - Progress visualization

### Phase 6: Testing & Polish (Week 6)
1. **Testing**
   - Unit tests for each component
   - Integration tests
   - Edge case handling
   - Cross-platform testing

2. **Documentation**
   - User guide
   - API documentation
   - Troubleshooting guide

3. **Error Recovery**
   - Restore from backup
   - Rollback functionality
   - Logging and diagnostics

## Detailed Component Specifications

### 1. Browser Adapters

#### Base Browser Class
```python
class BrowserAdapter(ABC):
    @abstractmethod
    def read_bookmarks(self) -> BookmarkTree
    @abstractmethod
    def write_bookmarks(self, tree: BookmarkTree) -> bool
    @abstractmethod
    def get_profile_path(self) -> Path
    @abstractmethod
    def is_locked(self) -> bool
```

#### Firefox Implementation
- Use SQLite3 to read `places.sqlite`
- Query `moz_bookmarks` and `moz_places` tables
- Reconstruct folder hierarchy
- Handle `type` field (1=URL, 2=folder)
- Preserve `dateAdded`, `lastModified`

#### Chrome Implementation
- Read `Bookmarks` JSON file
- Parse nested structure
- Handle `bookmark_bar`, `other`, `synced` roots
- Preserve `date_added`, `date_modified` (microseconds since epoch)

### 2. Data Model

```python
@dataclass
class Bookmark:
    title: str
    url: str
    date_added: datetime
    date_modified: datetime
    favicon: Optional[str] = None
    tags: List[str] = None

@dataclass
class BookmarkFolder:
    name: str
    children: List[Union[Bookmark, 'BookmarkFolder']]
    date_added: datetime
    date_modified: datetime

BookmarkTree = BookmarkFolder  # Root folder
```

### 3. Merge Algorithm

**Strategy 1: Keep All (Rename Duplicates)**
- Compare URLs
- If duplicate found, append source suffix (e.g., "Bookmark (Firefox)")
- Preserve folder structure from both sources

**Strategy 2: Timestamp-Based**
- Compare URLs
- If duplicate, keep bookmark with newer `date_modified`
- Log which bookmarks were replaced

**Strategy 3: Source Priority**
- User selects primary source (Firefox or Chrome)
- Duplicates from primary source take precedence
- Secondary source bookmarks only added if not in primary

**Strategy 4: Smart Merge**
- Merge folders with same name
- Merge bookmarks within folders
- Handle nested folder structures recursively

### 4. Backup System

**Backup Structure:**
```
backups/
├── firefox/
│   ├── places_2024-01-15_14-30-25.sqlite
│   └── places_2024-01-15_15-45-10.sqlite
├── chrome/
│   ├── Bookmarks_2024-01-15_14-30-25.json
│   └── Bookmarks_2024-01-15_15-45-10.json
└── metadata.json  # Backup index
```

**Backup Metadata:**
```json
{
  "backups": [
    {
      "timestamp": "2024-01-15T14:30:25",
      "source": "firefox",
      "profile": "default",
      "file": "places_2024-01-15_14-30-25.sqlite",
      "size": 1234567
    }
  ]
}
```

### 5. Configuration

```json
{
  "firefox": {
    "profile": "default",
    "path": "~/.mozilla/firefox/",
    "auto_detect": true
  },
  "chrome": {
    "profile": "Default",
    "path": "~/.config/google-chrome/",
    "auto_detect": true
  },
  "sync": {
    "direction": "bidirectional",
    "merge_strategy": "keep_all",
    "backup_before_sync": true,
    "max_backups": 10
  },
  "backup": {
    "directory": "./backups",
    "retention_days": 30
  }
}
```

## CLI Interface Design

```bash
# Basic sync (bidirectional merge)
bookmark-sync sync

# Sync Firefox to Chrome
bookmark-sync sync --from firefox --to chrome

# Sync Chrome to Firefox
bookmark-sync sync --from chrome --to firefox

# Merge mode
bookmark-sync merge --strategy keep_all

# Backup only
bookmark-sync backup

# Restore from backup
bookmark-sync restore --backup backups/firefox/places_2024-01-15_14-30-25.sqlite

# List profiles
bookmark-sync list-profiles

# Configure
bookmark-sync config --firefox-profile default --chrome-profile Default

# Dry run (preview changes)
bookmark-sync sync --dry-run
```

## Error Handling

### Common Scenarios
1. **Browser is running**
   - Detect locked database/file
   - Prompt user to close browser
   - Option to force (copy database first)

2. **Profile not found**
   - List available profiles
   - Allow user to select
   - Auto-detect default profile

3. **Permission errors**
   - Check file permissions
   - Suggest running with appropriate permissions
   - Clear error messages

4. **Corrupted data**
   - Validate bookmark data before writing
   - Rollback on error
   - Restore from backup

## Security Considerations

1. **File Permissions**
   - Respect existing permissions
   - Don't expose bookmarks unnecessarily

2. **Backup Security**
   - Store backups in user-controlled location
   - Option to encrypt backups

3. **Data Validation**
   - Validate URLs before writing
   - Sanitize bookmark titles
   - Prevent path traversal in folder names

## Future Enhancements

1. **Additional Browsers**
   - Edge/Chromium variants
   - Brave
   - Opera

2. **Cloud Sync**
   - Export to HTML
   - Import from HTML
   - Sync to cloud storage

3. **Advanced Features**
   - Bookmark deduplication
   - Dead link detection
   - Bookmark organization tools
   - Tag synchronization

4. **Scheduling**
   - Automatic periodic sync
   - Cron integration
   - Systemd timer

## Development Milestones

- [ ] Phase 1: Project setup and backup system
- [ ] Phase 2: Browser adapters (Firefox & Chrome)
- [ ] Phase 3: Merge engine with multiple strategies
- [ ] Phase 4: Bidirectional sync engine
- [ ] Phase 5: CLI interface
- [ ] Phase 6: Testing and documentation
- [ ] Phase 7: GUI (optional)
- [ ] Phase 8: Advanced features

## Risk Mitigation

1. **Data Loss Risk**
   - Always backup before sync
   - Dry-run mode for preview
   - Rollback capability
   - Comprehensive logging

2. **Browser Compatibility**
   - Test with multiple Firefox versions
   - Test with Chrome/Chromium variants
   - Handle format changes gracefully

3. **Cross-Platform Issues**
   - Use pathlib for paths
   - Test on Linux, macOS, Windows
   - Handle profile location differences

## Success Criteria

1. Successfully sync bookmarks between Firefox and Chrome
2. Preserve folder structure
3. Handle conflicts intelligently
4. Never lose data (backup before sync)
5. User-friendly CLI/GUI
6. Works on Linux, macOS, Windows
7. Comprehensive error handling
8. Well-documented code
