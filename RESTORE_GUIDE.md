# How to Restore Backups

The backup system automatically creates backups before syncing, but you need to know how to restore them. Here's how!

## 📁 Backup Location

**Default location:** `./backups/` (in the project directory)

Backups are organized by browser:
- `backups/firefox/` - Firefox bookmark backups
- `backups/chrome/` - Chrome bookmark backups
- `backups/metadata.json` - Backup index file

## 🔍 Finding Your Backups

### Method 1: List All Backups
```bash
python3 -m src.main restore --list
```

This shows:
- All available backups
- Backup location (full path)
- Date, size, and profile for each backup
- How to restore them

### Method 2: List Backups for Specific Browser
```bash
python3 -m src.main restore --list --source firefox
python3 -m src.main restore --list --source chrome
```

### Method 3: Use the list-backups Command
```bash
python3 -m src.main list-backups
python3 -m src.main list-backups --source firefox
```

## 🔄 Restoring Backups

### Method 1: Interactive Restore (Easiest!)
```bash
python3 -m src.main restore --interactive
```

This will:
1. Show you all available backups
2. Let you choose which one to restore
3. Automatically detect the browser and profile
4. Ask for confirmation before restoring

### Method 2: Restore Latest Backup
```bash
# Restore latest Firefox backup
python3 -m src.main restore --latest --source firefox

# Restore latest Chrome backup
python3 -m src.main restore --latest --source chrome
```

### Method 3: Restore Specific Backup File
```bash
python3 -m src.main restore backups/firefox/firefox_default-release_places_2025-11-08_18-14-08.sqlite
```

Or with full path:
```bash
python3 -m src.main restore /home/allie/Projects/bookmark-sync/backups/chrome/chrome_Default_Bookmarks_2025-11-08_18-14-08.json
```

## ⚠️ Important Notes

1. **Automatic Backup Before Restore**: The restore process automatically creates a backup of your current bookmarks before restoring, so you can undo if needed!

2. **Close Your Browser**: Make sure Firefox/Chrome is closed before restoring, or the restore will fail.

3. **Profile Selection**: If you have multiple profiles, specify which one:
   ```bash
   python3 -m src.main restore --latest --source firefox --firefox-profile myprofile
   ```

## 📋 Example Workflow

```bash
# 1. List available backups
python3 -m src.main restore --list

# 2. Restore interactively (easiest)
python3 -m src.main restore --interactive

# Or restore latest Firefox backup
python3 -m src.main restore --latest --source firefox
```

## 🆘 Troubleshooting

**"No backups found"**
- Check if backups directory exists: `ls backups/`
- Backups are only created when you run sync with `--backup` (enabled by default)

**"Backup file not found"**
- Use `--list` to see the exact paths
- Make sure you're using the full path or relative path from project directory

**"Browser is locked"**
- Close Firefox/Chrome completely
- Wait a few seconds and try again

## 💡 Pro Tips

1. **Check backup location**: The restore command always shows the backup directory location
2. **Use interactive mode**: It's the easiest way to restore - no need to remember paths
3. **Latest backup**: Use `--latest` for quick restore of the most recent backup
4. **List first**: Always list backups first to see what's available

## 📍 Finding Backup Location Programmatically

The backup location is stored in:
- Default: `./backups/` (relative to where you run the command)
- Can be configured in `config.json` (if you add backup directory setting)

To see where backups are stored:
```bash
python3 -m src.main restore --list
# Shows: 📁 Backup directory: /full/path/to/backups
```
