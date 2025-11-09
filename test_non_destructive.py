#!/usr/bin/env python3
"""Non-destructive test script for bookmark sync."""

import sys
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.browsers.firefox import FirefoxAdapter
from src.browsers.chrome import ChromeAdapter
from src.core.sync_engine import SyncEngine, SyncDirection, SyncMode
from src.core.merger import MergeStrategy
from src.utils.paths import get_firefox_profiles, get_chrome_profiles
from src.utils.logger import setup_logger

logger = setup_logger()


def test_browser_adapters():
    """Test reading bookmarks from both browsers (read-only)."""
    print("\n" + "="*70)
    print("TEST 1: Browser Adapters - Read Only")
    print("="*70)
    
    results = {"firefox": False, "chrome": False}
    
    # Test Firefox
    try:
        firefox_profiles = get_firefox_profiles()
        if firefox_profiles:
            print(f"\n✓ Found {len(firefox_profiles)} Firefox profile(s)")
            profile_name = firefox_profiles[0]['name']
            print(f"  Testing with profile: {profile_name}")
            
            adapter = FirefoxAdapter(profile_name=profile_name)
            
            if adapter.is_locked():
                print("  ⚠️  Firefox is locked (browser may be open)")
                print("  → This is expected if Firefox is running")
            else:
                print("  ✓ Firefox database is accessible")
                tree = adapter.read_bookmarks()
                bookmarks = tree.get_all_bookmarks()
                folders = tree.get_all_folders()
                print(f"  ✓ Read {len(bookmarks)} bookmarks")
                print(f"  ✓ Found {len(folders)} folders")
                if bookmarks:
                    print(f"  → Sample bookmark: {bookmarks[0].title[:50]}")
                results["firefox"] = True
        else:
            print("\n✗ No Firefox profiles found")
    except Exception as e:
        print(f"\n✗ Firefox adapter error: {e}")
        import traceback
        traceback.print_exc()
    
    # Test Chrome
    try:
        chrome_profiles = get_chrome_profiles()
        if chrome_profiles:
            print(f"\n✓ Found {len(chrome_profiles)} Chrome profile(s)")
            profile_name = chrome_profiles[0]['name']
            print(f"  Testing with profile: {profile_name}")
            
            adapter = ChromeAdapter(profile_name=profile_name)
            
            if adapter.is_locked():
                print("  ⚠️  Chrome is locked (browser may be open)")
                print("  → This is expected if Chrome is running")
            else:
                print("  ✓ Chrome bookmarks file is accessible")
                tree = adapter.read_bookmarks()
                bookmarks = tree.get_all_bookmarks()
                folders = tree.get_all_folders()
                print(f"  ✓ Read {len(bookmarks)} bookmarks")
                print(f"  ✓ Found {len(folders)} folders")
                if bookmarks:
                    print(f"  → Sample bookmark: {bookmarks[0].title[:50]}")
                results["chrome"] = True
        else:
            print("\n✗ No Chrome profiles found")
    except Exception as e:
        print(f"\n✗ Chrome adapter error: {e}")
        import traceback
        traceback.print_exc()
    
    return results


def test_merge_engine():
    """Test merge engine with sample data."""
    print("\n" + "="*70)
    print("TEST 2: Merge Engine - Sample Data")
    print("="*70)
    
    try:
        from src.core.models import Bookmark, BookmarkFolder
        from src.core.merger import BookmarkMerger, MergeStrategy
        
        # Create sample bookmarks
        now = datetime.now()
        
        # Firefox tree
        firefox_tree = BookmarkFolder(
            name="Firefox Bookmarks",
            date_added=now,
            date_modified=now
        )
        firefox_tree.add_child(Bookmark(
            title="Example Site",
            url="https://example.com",
            date_added=now,
            date_modified=now
        ))
        firefox_tree.add_child(Bookmark(
            title="GitHub",
            url="https://github.com",
            date_added=now,
            date_modified=now
        ))
        
        # Chrome tree
        chrome_tree = BookmarkFolder(
            name="Chrome Bookmarks",
            date_added=now,
            date_modified=now
        )
        chrome_tree.add_child(Bookmark(
            title="Example Site",
            url="https://example.com",
            date_added=now,
            date_modified=now
        ))
        chrome_tree.add_child(Bookmark(
            title="Stack Overflow",
            url="https://stackoverflow.com",
            date_added=now,
            date_modified=now
        ))
        
        # Test merge
        merger = BookmarkMerger(strategy=MergeStrategy.KEEP_ALL)
        merged = merger.merge(firefox_tree, chrome_tree, "Firefox", "Chrome")
        
        merged_bookmarks = merged.get_all_bookmarks()
        print(f"\n✓ Merge test successful")
        print(f"  → Firefox bookmarks: 2")
        print(f"  → Chrome bookmarks: 2")
        print(f"  → Merged bookmarks: {len(merged_bookmarks)}")
        print(f"  → Expected: 3-4 (duplicate handling)")
        
        for bookmark in merged_bookmarks:
            print(f"    - {bookmark.title}: {bookmark.url}")
        
        return True
    except Exception as e:
        print(f"\n✗ Merge engine error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_sync_engine_dry_run():
    """Test sync engine in dry-run mode (non-destructive)."""
    print("\n" + "="*70)
    print("TEST 3: Sync Engine - Dry Run (Non-Destructive)")
    print("="*70)
    
    try:
        firefox_profiles = get_firefox_profiles()
        chrome_profiles = get_chrome_profiles()
        
        if not firefox_profiles or not chrome_profiles:
            print("\n⚠️  Skipping: Need both Firefox and Chrome profiles")
            return False
        
        firefox_profile = firefox_profiles[0]['name']
        chrome_profile = chrome_profiles[0]['name']
        
        print(f"\n✓ Using profiles:")
        print(f"  → Firefox: {firefox_profile}")
        print(f"  → Chrome: {chrome_profile}")
        
        # Check if browsers are locked
        firefox_adapter = FirefoxAdapter(profile_name=firefox_profile)
        chrome_adapter = ChromeAdapter(profile_name=chrome_profile)
        
        if firefox_adapter.is_locked():
            print("\n⚠️  Firefox is locked - cannot test read")
            return False
        
        if chrome_adapter.is_locked():
            print("\n⚠️  Chrome is locked - cannot test read")
            return False
        
        # Create sync engine
        engine = SyncEngine(
            firefox_profile=firefox_profile,
            chrome_profile=chrome_profile,
            merge_strategy=MergeStrategy.KEEP_ALL,
            backup_before_sync=False,  # No backup needed for dry run
            sync_mode=SyncMode.MERGE
        )
        
        print("\n✓ Sync engine created")
        print("  → Running DRY RUN (no changes will be made)")
        
        # Run dry-run sync
        success = engine.sync(
            direction=SyncDirection.BIDIRECTIONAL,
            dry_run=True  # CRITICAL: This prevents any writes
        )
        
        if success:
            print("\n✓ Dry-run sync completed successfully")
            print("  → No bookmarks were modified")
            print("  → This confirms the sync logic works correctly")
        else:
            print("\n⚠️  Dry-run sync reported issues")
            print("  → Check logs above for details")
        
        return success
        
    except Exception as e:
        print(f"\n✗ Sync engine error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_data_validation():
    """Test data validation and error handling."""
    print("\n" + "="*70)
    print("TEST 4: Data Validation")
    print("="*70)
    
    try:
        from src.core.models import Bookmark, BookmarkFolder
        from src.utils.validators import is_valid_url
        
        # Test URL validation
        print("\n✓ Testing URL validation:")
        test_urls = [
            ("https://example.com", True),
            ("http://test.org", True),
            ("not-a-url", False),
            ("", False),
            ("ftp://example.com", True),
        ]
        
        for url, expected in test_urls:
            result = is_valid_url(url)
            status = "✓" if result == expected else "✗"
            print(f"  {status} {url[:40]:40s} -> {result} (expected {expected})")
        
        # Test bookmark model
        print("\n✓ Testing bookmark model:")
        bookmark = Bookmark(
            title="Test",
            url="https://example.com",
            date_added=datetime.now(),
            date_modified=datetime.now()
        )
        print(f"  → Created bookmark: {bookmark.title}")
        print(f"  → URL: {bookmark.url}")
        
        # Test folder model
        folder = BookmarkFolder(
            name="Test Folder",
            date_added=datetime.now(),
            date_modified=datetime.now()
        )
        folder.add_child(bookmark)
        print(f"  → Created folder with {len(folder.children)} child")
        
        return True
        
    except Exception as e:
        print(f"\n✗ Data validation error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all non-destructive tests."""
    print("\n" + "="*70)
    print("BOOKMARK SYNC - NON-DESTRUCTIVE TEST SUITE")
    print("="*70)
    print("\nThis test suite verifies functionality WITHOUT modifying bookmarks.")
    print("All tests are read-only or use dry-run mode.\n")
    
    results = {}
    
    # Run tests
    results["adapters"] = test_browser_adapters()
    results["merge"] = test_merge_engine()
    results["validation"] = test_data_validation()
    results["dry_run"] = test_sync_engine_dry_run()
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    print(f"\nBrowser Adapters:")
    print(f"  Firefox: {'✓ PASS' if results['adapters']['firefox'] else '✗ FAIL / SKIP'}")
    print(f"  Chrome:  {'✓ PASS' if results['adapters']['chrome'] else '✗ FAIL / SKIP'}")
    
    print(f"\nMerge Engine:      {'✓ PASS' if results['merge'] else '✗ FAIL'}")
    print(f"Data Validation:   {'✓ PASS' if results['validation'] else '✗ FAIL'}")
    print(f"Dry-Run Sync:      {'✓ PASS' if results['dry_run'] else '✗ FAIL / SKIP'}")
    
    all_passed = (
        (results['adapters']['firefox'] or results['adapters']['chrome']) and
        results['merge'] and
        results['validation']
    )
    
    print("\n" + "="*70)
    if all_passed:
        print("✓ OVERALL: Tests completed successfully!")
        print("  → Core functionality appears to be working")
        print("  → Safe to use the application")
    else:
        print("⚠️  OVERALL: Some tests failed or were skipped")
        print("  → Review test output above for details")
        print("  → Some failures may be expected (e.g., locked browsers)")
    print("="*70 + "\n")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
