# Sync Modes Explained

The bookmark sync application offers three different sync modes, each designed for different use cases. Understanding these modes will help you choose the right one for your needs.

## 1. Full Sync

**What it does:**
- Completely replaces all bookmarks in the target browser with bookmarks from the source browser
- One-way operation: Source → Target
- No merging or combining - it's a complete replacement

**How it works:**
1. Reads all bookmarks from the source browser (e.g., Firefox)
2. Clears all existing bookmarks in the target browser (e.g., Chrome)
3. Writes all source bookmarks to the target browser

**When to use:**
- ✅ You want Chrome to be an exact copy of Firefox (or vice versa)
- ✅ You're setting up a new browser and want to copy all bookmarks
- ✅ You trust one browser's bookmarks completely and want to replace the other
- ✅ You've cleaned up bookmarks in one browser and want to sync that clean state

**Example:**
```
Firefox has: [Bookmark A, Bookmark B, Bookmark C]
Chrome has:  [Bookmark X, Bookmark Y, Bookmark Z]

After Full Sync Firefox → Chrome:
Chrome has:  [Bookmark A, Bookmark B, Bookmark C]
(Bookmark X, Y, Z are gone)
```

**⚠️ Warning:**
- This mode will DELETE all existing bookmarks in the target browser
- Always use backup before running full sync
- Consider using dry-run mode first to preview changes

---

## 2. Incremental Sync

**What it does:**
- Only syncs bookmarks that have changed since the last sync
- Tracks changes using timestamps and content hashes
- More efficient for large bookmark collections
- Can work bidirectionally

**How it works:**
1. Reads bookmarks from both browsers
2. Compares with the last sync metadata (stored in `.sync_metadata.json`)
3. Identifies:
   - **New bookmarks** - Added since last sync
   - **Modified bookmarks** - Changed since last sync
   - **Deleted bookmarks** - Removed since last sync
4. Only syncs the changes, not everything

**When to use:**
- ✅ You sync regularly and want faster syncs
- ✅ You have thousands of bookmarks and full sync is slow
- ✅ You want to keep both browsers in sync over time
- ✅ You make small changes and want to sync only those changes

**Example:**
```
Last sync: Firefox had 900 bookmarks, Chrome had 900 bookmarks

Since then:
- Firefox: Added 5 new bookmarks, deleted 2, modified 1
- Chrome: Added 3 new bookmarks, deleted 1

After Incremental Sync:
- Firefox gets: 3 new bookmarks from Chrome, 1 deletion
- Chrome gets: 5 new bookmarks from Firefox, 2 deletions, 1 modification
```

**Benefits:**
- ⚡ Much faster than full sync
- 💾 Less data transfer
- 🔄 Can run frequently without performance impact

**Note:**
- First sync is always a full sync (no metadata exists yet)
- Subsequent syncs are incremental
- Metadata tracks what changed, so it knows what to sync

---

## 3. Merge Sync

**What it does:**
- Combines bookmarks from both browsers into both browsers
- Bidirectional: Both browsers get the merged result
- Detects and handles duplicates intelligently
- Preserves bookmarks from both sources

**How it works:**
1. Reads bookmarks from both Firefox and Chrome
2. Merges them using the selected merge strategy:
   - **Keep All**: Keeps all bookmarks, renames duplicates
   - **Keep Newer**: Keeps the bookmark with the newer date when duplicates found
   - **Firefox Priority**: Firefox bookmarks take precedence
   - **Chrome Priority**: Chrome bookmarks take precedence
   - **Smart Merge**: Intelligent merging with folder awareness
3. Writes the merged result to both browsers
4. Both browsers end up with the same merged bookmark collection

**When to use:**
- ✅ You want to combine bookmarks from both browsers
- ✅ You've added different bookmarks in each browser
- ✅ You want both browsers to have all your bookmarks
- ✅ You want to consolidate your bookmark collection

**Example:**
```
Firefox has: [Bookmark A, Bookmark B, Bookmark C]
Chrome has:  [Bookmark C, Bookmark D, Bookmark E]
(Bookmark C exists in both)

After Merge Sync (Keep All strategy):
Firefox has: [Bookmark A, Bookmark B, Bookmark C, Bookmark C (Chrome), Bookmark D, Bookmark E]
Chrome has:  [Bookmark A, Bookmark B, Bookmark C, Bookmark C (Chrome), Bookmark D, Bookmark E]
(Both browsers now have all bookmarks, duplicate C is renamed)
```

**Duplicate Handling:**
- The merge engine detects duplicates using:
  - Exact URL matching
  - Fuzzy URL matching (http vs https, www differences)
  - Name + URL matching
- Conflicts (same URL, different metadata) are detected and logged
- Duplicates are handled according to the merge strategy

**Benefits:**
- 🔄 Truly bidirectional - both browsers get updated
- 📚 Combines all your bookmarks
- 🎯 Intelligent duplicate detection
- ⚙️ Multiple merge strategies for different needs

---

## Comparison Table

| Feature | Full Sync | Incremental Sync | Merge Sync |
|---------|-----------|-----------------|------------|
| **Direction** | One-way | One-way or Bidirectional | Bidirectional |
| **Speed** | Slow (syncs everything) | Fast (only changes) | Medium (merges everything) |
| **Data Loss Risk** | High (replaces all) | Low (only changes) | Low (combines) |
| **First Use** | Immediate | Full sync first time | Immediate |
| **Best For** | Exact copy | Regular syncing | Combining bookmarks |
| **Duplicate Handling** | N/A | N/A | Yes (multiple strategies) |
| **Backup Recommended** | ⚠️ Essential | ✅ Recommended | ✅ Recommended |

---

## Recommendations

### For First-Time Setup:
1. **Start with Merge Sync** - Combines bookmarks from both browsers
2. Use "Keep All" strategy to see all duplicates
3. Review and clean up duplicates manually if needed

### For Regular Use:
1. **Use Incremental Sync** - Fast and efficient
2. Run it daily or weekly to keep browsers in sync
3. Use Merge Sync occasionally to handle any divergence

### For Clean Slate:
1. **Use Full Sync** - Start fresh with one browser's bookmarks
2. Make sure to backup first!
3. Use dry-run to preview changes

---

## Safety Features

All sync modes support:
- **Dry-run mode**: Preview changes without applying them
- **Backup before sync**: Automatic backups before any changes
- **Conflict detection**: Identifies when same URLs have different metadata
- **Logging**: Detailed logs of what was synced

**Always use dry-run first to see what will happen!**

---

## Technical Details

### Full Sync
- Uses `clear_existing=True` when writing bookmarks
- No metadata tracking needed
- Simple and straightforward

### Incremental Sync
- Uses `.sync_metadata.json` to track:
  - Last sync timestamp per browser
  - Hash of each bookmark (for change detection)
- Compares current state with last known state
- Only syncs differences

### Merge Sync
- Uses the merge engine to combine bookmark trees
- Applies merge strategy to handle duplicates
- Writes merged result to both browsers
- Both browsers end up identical

---

## Choosing the Right Mode

**Ask yourself:**
1. Do I want to replace all bookmarks? → **Full Sync**
2. Do I want to sync only changes? → **Incremental Sync**
3. Do I want to combine both browsers? → **Merge Sync**

**Remember:** You can always switch between modes. Start with Merge Sync to combine, then use Incremental Sync to keep them in sync!
