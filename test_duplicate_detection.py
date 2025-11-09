#!/usr/bin/env python3
"""Test duplicate detection accuracy."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.browsers.firefox import FirefoxAdapter
from src.browsers.chrome import ChromeAdapter
from src.core.merger import BookmarkMerger, MergeStrategy
from src.utils.paths import get_firefox_profiles, get_chrome_profiles
from src.utils.logger import setup_logger

logger = setup_logger()


def analyze_duplicates():
    """Analyze duplicates between Firefox and Chrome bookmarks."""
    print("\n" + "="*70)
    print("DUPLICATE DETECTION ANALYSIS")
    print("="*70)
    
    firefox_profiles = get_firefox_profiles()
    chrome_profiles = get_chrome_profiles()
    
    if not firefox_profiles or not chrome_profiles:
        print("Need both Firefox and Chrome profiles")
        return
    
    firefox_profile = firefox_profiles[0]['name']
    chrome_profile = chrome_profiles[0]['name']
    
    print(f"\nFirefox profile: {firefox_profile}")
    print(f"Chrome profile: {chrome_profile}\n")
    
    # Read bookmarks
    try:
        firefox_adapter = FirefoxAdapter(profile_name=firefox_profile)
        if firefox_adapter.is_locked():
            print("Firefox is locked - close Firefox first")
            return
        
        chrome_adapter = ChromeAdapter(profile_name=chrome_profile)
        if chrome_adapter.is_locked():
            print("Chrome is locked - close Chrome first")
            return
        
        print("Reading Firefox bookmarks...")
        firefox_tree = firefox_adapter.read_bookmarks()
        firefox_bookmarks = firefox_tree.get_all_bookmarks()
        print(f"✓ Firefox: {len(firefox_bookmarks)} bookmarks")
        
        print("Reading Chrome bookmarks...")
        chrome_tree = chrome_adapter.read_bookmarks()
        chrome_bookmarks = chrome_tree.get_all_bookmarks()
        print(f"✓ Chrome: {len(chrome_bookmarks)} bookmarks\n")
        
        # Manual duplicate detection
        print("="*70)
        print("MANUAL DUPLICATE DETECTION (Exact URL Match)")
        print("="*70)
        
        firefox_urls = {bm.url.lower().rstrip('/') for bm in firefox_bookmarks}
        chrome_urls = {bm.url.lower().rstrip('/') for bm in chrome_bookmarks}
        
        exact_duplicates = firefox_urls & chrome_urls
        print(f"\nExact URL matches (case-insensitive, trailing slash ignored):")
        print(f"  → {len(exact_duplicates)} duplicates found")
        
        # Show some examples
        if exact_duplicates:
            print(f"\nSample duplicates:")
            for i, url in enumerate(list(exact_duplicates)[:10], 1):
                print(f"  {i}. {url[:70]}")
            if len(exact_duplicates) > 10:
                print(f"  ... and {len(exact_duplicates) - 10} more")
        
        # Test with merger
        print("\n" + "="*70)
        print("MERGER DUPLICATE DETECTION")
        print("="*70)
        
        merger = BookmarkMerger(strategy=MergeStrategy.KEEP_ALL, enable_fuzzy_matching=True, enable_name_matching=True)
        merged = merger.merge(firefox_tree, chrome_tree, "Firefox", "Chrome")
        
        duplicate_matches = merger.get_duplicate_matches()
        print(f"\nMerger found: {len(duplicate_matches)} duplicate matches")
        
        # Count by match type
        match_types = {}
        for b1, b2, match_type in duplicate_matches:
            match_types[match_type] = match_types.get(match_type, 0) + 1
        
        print(f"\nBreakdown by match type:")
        for match_type, count in sorted(match_types.items()):
            print(f"  → {match_type}: {count}")
        
        # Get unique duplicate URLs (from tree2_duplicates equivalent)
        unique_duplicate_urls = set()
        for b1, b2, match_type in duplicate_matches:
            unique_duplicate_urls.add(b2.url.lower().rstrip('/'))
        
        print(f"\nUnique duplicate URLs: {len(unique_duplicate_urls)}")
        
        # Compare
        print("\n" + "="*70)
        print("COMPARISON")
        print("="*70)
        print(f"Manual detection (exact URL): {len(exact_duplicates)}")
        print(f"Merger unique duplicates: {len(unique_duplicate_urls)}")
        print(f"Merger total matches: {len(duplicate_matches)}")
        
        if len(unique_duplicate_urls) < len(exact_duplicates):
            print(f"\n⚠️  WARNING: Merger found {len(exact_duplicates) - len(unique_duplicate_urls)} fewer unique duplicates!")
            print("   This suggests some duplicates are being missed.")
            
            # Find missing duplicates
            missing = exact_duplicates - {url.lower().rstrip('/') for url in unique_duplicate_urls}
            if missing:
                print(f"\n   Missing duplicates (first 10):")
                for i, url in enumerate(list(missing)[:10], 1):
                    print(f"     {i}. {url[:70]}")
        elif len(unique_duplicate_urls) > len(exact_duplicates):
            print(f"\n✓ Merger found {len(unique_duplicate_urls) - len(exact_duplicates)} additional unique duplicates")
            print("  (likely using fuzzy matching for http/https, www differences)")
        else:
            print(f"\n✓ Duplicate counts match!")
        
        if len(duplicate_matches) > len(unique_duplicate_urls):
            print(f"\nNote: {len(duplicate_matches) - len(unique_duplicate_urls)} matches are multiple detection methods")
            print("      for the same bookmark (e.g., both exact URL and fuzzy match)")
        
        # Check for fuzzy matches
        print("\n" + "="*70)
        print("FUZZY MATCHING ANALYSIS")
        print("="*70)
        
        # Normalize URLs for comparison
        def normalize_url(url):
            url = url.lower()
            if url.startswith('https://'):
                url = 'http://' + url[8:]
            if url.startswith('www.'):
                url = url[4:]
            return url.rstrip('/')
        
        firefox_normalized = {normalize_url(bm.url): bm for bm in firefox_bookmarks}
        chrome_normalized = {normalize_url(bm.url): bm for bm in chrome_bookmarks}
        
        # Find potential fuzzy matches
        potential_fuzzy = []
        for f_url, f_bm in firefox_normalized.items():
            for c_url, c_bm in chrome_normalized.items():
                if f_url != c_url:
                    # Check if they're similar (same domain, different protocol or www)
                    f_domain = f_url.split('/')[2] if '/' in f_url else f_url
                    c_domain = c_url.split('/')[2] if '/' in c_url else c_url
                    if f_domain == c_domain:
                        potential_fuzzy.append((f_bm.url, c_bm.url))
        
        print(f"\nPotential fuzzy matches (same domain, different protocol/www): {len(potential_fuzzy)}")
        if potential_fuzzy:
            print("Sample fuzzy matches:")
            for i, (f_url, c_url) in enumerate(potential_fuzzy[:5], 1):
                print(f"  {i}. Firefox: {f_url[:50]}")
                print(f"     Chrome:  {c_url[:50]}")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    analyze_duplicates()
