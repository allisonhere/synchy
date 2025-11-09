# Bookmark Sync - Usage Guide

## Quick Start

### 1. List Available Profiles

First, check what browser profiles are available:

```bash
python3 -m src.main list-profiles
```

This will show all Firefox and Chrome profiles detected on your system.

### 2. Basic Sync (Bidirectional Merge)

Sync bookmarks between Firefox and Chrome, merging both:

```bash
python3 -m src.main sync
```

This will:
- Read bookmarks from both browsers
- Merge them using the default strategy (keep_all)
- Write merged bookmarks back to both browsers
- Create backups before syncing

### 3. One-Way Sync

Sync from Firefox to Chrome:

```bash
python3 -m src.main sync --from firefox --to chrome
```

Sync from Chrome to Firefox:

```bash
python3 -m src.main sync --from chrome --to firefox
```

### 4. Dry Run (Preview Changes)

Preview what would happen without actually syncing:

```bash
python3 -m src.main sync --dry-run
```

### 5. Merge Strategies

Use different merge strategies:

```bash
# Keep all bookmarks, rename duplicates
python3 -m src.main sync --merge-strategy keep_all

# Keep newer bookmark when duplicate found
python3 -m src.main sync --merge-strategy timestamp

# Firefox bookmarks take priority
python3 -m src.main sync --merge-strategy firefox_priority

# Chrome bookmarks take priority
python3 -m src.main sync --merge-strategy chrome_priority

# Smart merge preserving folder structure
python3 -m src.main sync --merge-strategy smart
```

### 6. Backup Only

Create backups without syncing:

```bash
# Backup both browsers
python3 -m src.main backup

# Backup Firefox only
python3 -m src.main backup --source firefox

# Backup Chrome only
python3 -m src.main backup --source chrome
```

### 7. List Backups

View all backups:

```bash
# List all backups
python3 -m src.main list-backups

# List Firefox backups only
python3 -m src.main list-backups --source firefox

# List Chrome backups only
python3 -m src.main list-backups --source chrome
```

### 8. Restore from Backup

Restore a backup:

```bash
python3 -m src.main restore backups/firefox/firefox_default_places_2024-01-15_14-30-25.sqlite
```

## Configuration

Edit `config.json` to set default profiles and sync options:

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

## Important Notes

### Browser Locking

**Always close your browsers before syncing!** The app will check if browsers are running and warn you if they are. Browsers lock their bookmark files while running, which prevents syncing.

### Firefox Write Support

⚠️ **Note**: Full Firefox write support is not yet implemented. Firefox's bookmark database (places.sqlite) uses complex GUIDs and metadata that require careful handling. 

For now:
- **Reading** from Firefox works perfectly
- **Writing** to Chrome works perfectly
- **Writing** to Firefox is limited (use Firefox's built-in import/export for now)

### Backup Safety

The app **always creates backups** before syncing (unless you use `--no-backup`). Backups are stored in the `backups/` directory with timestamps.

## Examples

### Example 1: Merge Bookmarks

You have bookmarks in both Firefox and Chrome and want to merge them:

```bash
# Preview the merge
python3 -m src.main sync --dry-run

# Perform the merge
python3 -m src.main sync --merge-strategy keep_all
```

### Example 2: Sync Chrome to Firefox

You want to copy all Chrome bookmarks to Firefox:

```bash
# First, backup both
python3 -m src.main backup

# Then sync Chrome → Firefox
python3 -m src.main sync --from chrome --to firefox
```

### Example 3: Use Specific Profiles

If you have multiple browser profiles:

```bash
# List profiles first
python3 -m src.main list-profiles

# Sync specific profiles
python3 -m src.main sync \
  --firefox-profile "Profile 1" \
  --chrome-profile "Profile 2"
```

## Troubleshooting

### "Browser profile not found"

- Run `list-profiles` to see available profiles
- Make sure the browser is installed
- Check that you've used the browser at least once (to create the profile)

### "Database is locked"

- Close the browser completely
- Wait a few seconds for file locks to release
- Try again

### "Permission denied"

- Make sure you have read/write access to browser profile directories
- On Linux, profiles are usually in `~/.mozilla/firefox/` and `~/.config/google-chrome/`

### Sync didn't work as expected

- Check the logs in `logs/` directory
- Use `--dry-run` first to preview changes
- Restore from backup if needed: `python3 -m src.main restore <backup-file>`
