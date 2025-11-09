"""Browser path detection utilities."""

import os
import json
import sqlite3
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import platform


def get_home_dir() -> Path:
    """Get user home directory."""
    return Path.home()


def get_firefox_profiles() -> List[Dict[str, str]]:
    """
    Detect Firefox profiles.
    
    Returns:
        List of dicts with 'name' and 'path' keys
    """
    profiles = []
    system = platform.system()
    
    if system == "Linux":
        base_path = get_home_dir() / ".mozilla" / "firefox"
    elif system == "Darwin":  # macOS
        base_path = get_home_dir() / "Library" / "Application Support" / "Firefox"
    elif system == "Windows":
        base_path = Path(os.environ.get("APPDATA", "")) / "Mozilla" / "Firefox"
    else:
        return profiles
    
    if not base_path.exists():
        return profiles
    
    # Read profiles.ini
    profiles_ini = base_path / "profiles.ini"
    if not profiles_ini.exists():
        return profiles
    
    current_profile = None
    with open(profiles_ini, 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith('[Profile'):
                if current_profile:
                    profiles.append(current_profile)
                current_profile = {}
            elif line.startswith('Name=') and current_profile is not None:
                current_profile['name'] = line.split('=', 1)[1]
            elif line.startswith('Path=') and current_profile is not None:
                path = line.split('=', 1)[1]
                if path.startswith('/'):
                    # Absolute path
                    current_profile['path'] = Path(path)
                else:
                    # Relative path
                    current_profile['path'] = base_path / path
            elif line.startswith('IsRelative=') and current_profile is not None:
                current_profile['is_relative'] = line.split('=', 1)[1] == '1'
    
    if current_profile:
        profiles.append(current_profile)
    
    # Verify profiles have places.sqlite
    valid_profiles = []
    for profile in profiles:
        places_db = profile['path'] / "places.sqlite"
        if places_db.exists():
            valid_profiles.append(profile)
    
    return valid_profiles


def get_chrome_profiles() -> List[Dict[str, str]]:
    """
    Detect Chrome/Chromium profiles.
    
    Returns:
        List of dicts with 'name' and 'path' keys
    """
    profiles = []
    system = platform.system()
    
    chrome_paths = []
    if system == "Linux":
        chrome_paths = [
            (get_home_dir() / ".config" / "google-chrome", "Google Chrome"),
            (get_home_dir() / ".config" / "chromium", "Chromium"),
        ]
    elif system == "Darwin":  # macOS
        chrome_paths = [
            (get_home_dir() / "Library" / "Application Support" / "Google" / "Chrome", "Google Chrome"),
        ]
    elif system == "Windows":
        appdata = os.environ.get("LOCALAPPDATA", "")
        chrome_paths = [
            (Path(appdata) / "Google" / "Chrome" / "User Data", "Google Chrome"),
        ]
    
    for base_path, browser_name in chrome_paths:
        if not base_path.exists():
            continue
        
        # Check for Default profile
        default_profile = base_path / "Default"
        if (default_profile / "Bookmarks").exists():
            profiles.append({
                'name': 'Default',
                'path': default_profile,
                'browser': browser_name
            })
        
        # Check for other profiles (Profile 1, Profile 2, etc.)
        for item in base_path.iterdir():
            if item.is_dir() and item.name.startswith("Profile "):
                bookmarks_file = item / "Bookmarks"
                if bookmarks_file.exists():
                    profiles.append({
                        'name': item.name,
                        'path': item,
                        'browser': browser_name
                    })
    
    return profiles


def get_firefox_profile_path(profile_name: Optional[str] = None) -> Optional[Path]:
    """Get path to Firefox profile directory."""
    profiles = get_firefox_profiles()
    if not profiles:
        return None
    
    if profile_name:
        for profile in profiles:
            if profile['name'] == profile_name:
                return profile['path']
    
    # Return first profile (usually default)
    return profiles[0]['path'] if profiles else None


def get_chrome_profile_path(profile_name: Optional[str] = None) -> Optional[Path]:
    """Get path to Chrome profile directory."""
    profiles = get_chrome_profiles()
    if not profiles:
        return None
    
    if profile_name:
        for profile in profiles:
            if profile['name'] == profile_name:
                return profile['path']
    
    # Return Default profile or first available
    for profile in profiles:
        if profile['name'] == 'Default':
            return profile['path']
    
    return profiles[0]['path'] if profiles else None


def get_firefox_places_db(profile_name: Optional[str] = None) -> Optional[Path]:
    """Get path to Firefox places.sqlite database."""
    profile_path = get_firefox_profile_path(profile_name)
    if not profile_path:
        return None
    places_db = profile_path / "places.sqlite"
    return places_db if places_db.exists() else None


def get_chrome_bookmarks_file(profile_name: Optional[str] = None) -> Optional[Path]:
    """Get path to Chrome Bookmarks file."""
    profile_path = get_chrome_profile_path(profile_name)
    if not profile_path:
        return None
    bookmarks_file = profile_path / "Bookmarks"
    return bookmarks_file if bookmarks_file.exists() else None


def is_firefox_locked(profile_name: Optional[str] = None) -> bool:
    """Check if Firefox database is locked (browser is running)."""
    places_db = get_firefox_places_db(profile_name)
    if not places_db:
        return False
    
    try:
        # Try to open database in exclusive mode
        conn = sqlite3.connect(str(places_db))
        conn.execute("BEGIN EXCLUSIVE")
        conn.rollback()
        conn.close()
        return False
    except sqlite3.OperationalError:
        return True


def is_chrome_locked(profile_name: Optional[str] = None) -> bool:
    """Check if Chrome Bookmarks file is locked (browser is running)."""
    bookmarks_file = get_chrome_bookmarks_file(profile_name)
    if not bookmarks_file:
        return False
    
    # On Linux, check if file is open by another process
    # Simple check: try to open in write mode
    try:
        # Try to open file in append mode (less intrusive)
        with open(bookmarks_file, 'a'):
            pass
        return False
    except (IOError, OSError):
        return True
