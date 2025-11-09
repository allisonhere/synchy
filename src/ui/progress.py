"""Progress indicators for sync operations."""

import sys
from typing import Optional
from datetime import datetime


class ProgressBar:
    """Simple progress bar for terminal."""
    
    def __init__(self, total: int, width: int = 50, desc: str = ""):
        """
        Initialize progress bar.
        
        Args:
            total: Total number of items
            width: Width of progress bar in characters
            desc: Description text
        """
        self.total = total
        self.width = width
        self.desc = desc
        self.current = 0
        self.start_time = datetime.now()
    
    def update(self, n: int = 1):
        """Update progress by n items."""
        self.current = min(self.current + n, self.total)
        self._draw()
    
    def set(self, value: int):
        """Set progress to specific value."""
        self.current = min(value, self.total)
        self._draw()
    
    def _draw(self):
        """Draw progress bar."""
        if self.total == 0:
            percent = 100
        else:
            percent = int(100 * self.current / self.total)
        
        filled = int(self.width * self.current / self.total) if self.total > 0 else self.width
        bar = '█' * filled + '░' * (self.width - filled)
        
        elapsed = (datetime.now() - self.start_time).total_seconds()
        if self.current > 0 and elapsed > 0:
            rate = self.current / elapsed
            eta = (self.total - self.current) / rate if rate > 0 else 0
            eta_str = f"ETA: {int(eta)}s" if eta > 0 else ""
        else:
            eta_str = ""
        
        sys.stdout.write(f'\r{self.desc} |{bar}| {self.current}/{self.total} ({percent}%) {eta_str}')
        sys.stdout.flush()
    
    def finish(self):
        """Finish progress bar."""
        self.set(self.total)
        sys.stdout.write('\n')
        sys.stdout.flush()


class StatusIndicator:
    """Status indicator for sync operations."""
    
    def __init__(self):
        """Initialize status indicator."""
        self.current_status = ""
    
    def update(self, status: str):
        """
        Update status message.
        
        Args:
            status: Status message
        """
        # Clear previous status
        if self.current_status:
            sys.stdout.write('\r' + ' ' * len(self.current_status) + '\r')
        
        # Write new status
        sys.stdout.write(f'\r{status}')
        sys.stdout.flush()
        self.current_status = status
    
    def finish(self, final_status: Optional[str] = None):
        """
        Finish status indicator.
        
        Args:
            final_status: Final status message (None to clear)
        """
        if final_status:
            self.update(final_status)
        sys.stdout.write('\n')
        sys.stdout.flush()
        self.current_status = ""


class ProgressTracker:
    """Track progress of sync operations."""
    
    def __init__(self, show_progress: bool = True):
        """
        Initialize progress tracker.
        
        Args:
            show_progress: Whether to show progress indicators
        """
        self.show_progress = show_progress
        self.status = StatusIndicator() if show_progress else None
        self.progress_bar: Optional[ProgressBar] = None
    
    def set_status(self, message: str):
        """Set status message."""
        if self.status:
            self.status.update(message)
    
    def set_progress(self, current: int, total: int, desc: str = ""):
        """Set progress bar."""
        if not self.show_progress:
            return
        
        if self.progress_bar is None:
            self.progress_bar = ProgressBar(total, desc=desc)
        self.progress_bar.set(current)
    
    def update_progress(self, n: int = 1):
        """Update progress."""
        if self.progress_bar:
            self.progress_bar.update(n)
    
    def finish(self, message: Optional[str] = None):
        """Finish progress tracking."""
        if self.progress_bar:
            self.progress_bar.finish()
        if self.status:
            self.status.finish(message)
