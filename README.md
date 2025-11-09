# Bookmark Sync

A cross-platform application to synchronize bookmarks between Firefox and Chrome browsers with bidirectional sync, merge capabilities, and backup functionality.

## Features

- 🔄 **Bidirectional Sync**: Sync bookmarks from Firefox to Chrome or Chrome to Firefox
- 🔀 **Merge Options**: Multiple merge strategies (keep all, timestamp-based, source priority)
- 💾 **Automatic Backups**: Always backup before syncing, with restore capability
- 🛡️ **Safe**: Dry-run mode to preview changes before applying
- 🖥️ **Cross-Platform**: Works on Linux, macOS, and Windows

## Installation

```bash
# Clone or navigate to the project directory
cd bookmark-sync

# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Quick Start

```bash
# Basic bidirectional sync with merge
python -m src.main sync

# Sync Firefox to Chrome
python -m src.main sync --from firefox --to chrome

# Sync Chrome to Firefox
python -m src.main sync --from chrome --to firefox

# Merge with specific strategy
python -m src.main merge --strategy keep_all

# Backup only
python -m src.main backup

# Dry run (preview changes without applying)
python -m src.main sync --dry-run

# List available browser profiles
python -m src.main list-profiles
```

## Configuration

The app will auto-detect browser profiles, but you can configure specific profiles in `config.json`:

```json
{
  "firefox": {
    "profile": "default",
    "auto_detect": true
  },
  "chrome": {
    "profile": "Default",
    "auto_detect": true
  },
  "sync": {
    "merge_strategy": "keep_all",
    "backup_before_sync": true
  }
}
```

## Merge Strategies

- `keep_all`: Keep all bookmarks, rename duplicates with source suffix
- `timestamp`: Keep newer bookmark when duplicates found
- `firefox_priority`: Firefox bookmarks take precedence
- `chrome_priority`: Chrome bookmarks take precedence
- `smart`: Merge folders intelligently, handle duplicates within folders

## Safety

- **Always backs up** before syncing
- **Dry-run mode** to preview changes
- **Rollback capability** from backups
- **Comprehensive logging** for troubleshooting

## Requirements

- Python 3.9+
- Firefox or Chrome/Chromium installed
- Write access to browser profile directories

## License

MIT License
