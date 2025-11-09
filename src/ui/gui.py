"""GUI interface for bookmark sync."""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
from typing import Optional
from pathlib import Path
from datetime import datetime
from src.core.sync_engine import SyncEngine, SyncDirection, SyncMode
from src.core.merger import MergeStrategy
from src.utils.paths import get_firefox_profiles, get_chrome_profiles
from src.utils.logger import setup_logger

logger = setup_logger()


class BookmarkSyncGUI:
    """Main GUI window for bookmark sync."""
    
    def __init__(self, root: tk.Tk):
        """
        Initialize GUI.
        
        Args:
            root: Tkinter root window
        """
        self.root = root
        self.root.title("🔄 Bookmark Sync - Firefox ↔ Chrome")
        self.root.geometry("850x950")
        self.root.minsize(750, 800)
        
        # Center window on screen
        self.root.update_idletasks()
        width = 850
        height = 950
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')
        
        # Configure style
        self._configure_styles()
        
        # Set window icon (if available)
        try:
            self.root.iconname("Bookmark Sync")
        except:
            pass
        
        self.sync_thread: Optional[threading.Thread] = None
        self.sync_engine: Optional[SyncEngine] = None
        
        self._create_widgets()
        self._load_profiles()
    
    def _configure_styles(self):
        """Configure ttk styles for a modern look."""
        style = ttk.Style()
        
        # Try to use a modern theme
        try:
            style.theme_use('clam')  # Modern, clean theme
        except:
            pass
        
        # Configure colors
        style.configure('Title.TLabel', font=('Segoe UI', 20, 'bold'), foreground='#2c3e50')
        style.configure('Heading.TLabel', font=('Segoe UI', 10, 'bold'), foreground='#34495e')
        style.configure('Status.TLabel', font=('Segoe UI', 9), foreground='#7f8c8d')
        style.configure('Success.TLabel', font=('Segoe UI', 9, 'bold'), foreground='#27ae60')
        style.configure('Error.TLabel', font=('Segoe UI', 9, 'bold'), foreground='#e74c3c')
        
        # Button styles
        style.configure('Primary.TButton', font=('Segoe UI', 10, 'bold'), padding=10)
        style.configure('Secondary.TButton', font=('Segoe UI', 9), padding=8)
        
        # Frame styles
        style.configure('Card.TLabelframe', borderwidth=1, relief='solid')
        style.configure('Card.TLabelframe.Label', font=('Segoe UI', 10, 'bold'), foreground='#34495e')
    
    def _create_widgets(self):
        """Create GUI widgets."""
        # Use grid for better control
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        
        # Main container with padding
        main_container = tk.Frame(self.root, bg='#ecf0f1')
        main_container.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=15, pady=15)
        main_container.grid_rowconfigure(4, weight=1)  # Log area expands
        main_container.grid_columnconfigure(0, weight=1)
        
        # Header section
        header_frame = tk.Frame(main_container, bg='#ecf0f1')
        header_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 15))
        
        title_label = ttk.Label(header_frame, text="🔄 Bookmark Sync", style='Title.TLabel')
        title_label.pack(anchor=tk.W)
        
        subtitle_label = ttk.Label(header_frame, text="Synchronize bookmarks between Firefox and Chrome", 
                                   style='Status.TLabel')
        subtitle_label.pack(anchor=tk.W, pady=(5, 0))
        
        # Profile selection card
        profile_frame = ttk.LabelFrame(main_container, text="🌐 Browser Profiles", 
                                       style='Card.TLabelframe', padding=15)
        profile_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Firefox profile
        firefox_row = tk.Frame(profile_frame)
        firefox_row.pack(fill=tk.X, pady=8)
        ttk.Label(firefox_row, text="🦊 Firefox Profile:", style='Heading.TLabel').pack(side=tk.LEFT, padx=(0, 10))
        self.firefox_profile_var = tk.StringVar()
        self.firefox_combo = ttk.Combobox(firefox_row, textvariable=self.firefox_profile_var, 
                                         state="readonly", width=35)
        self.firefox_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        
        # Chrome profile
        chrome_row = tk.Frame(profile_frame)
        chrome_row.pack(fill=tk.X, pady=8)
        ttk.Label(chrome_row, text="⚡ Chrome Profile:", style='Heading.TLabel').pack(side=tk.LEFT, padx=(0, 10))
        self.chrome_profile_var = tk.StringVar()
        self.chrome_combo = ttk.Combobox(chrome_row, textvariable=self.chrome_profile_var, 
                                        state="readonly", width=35)
        self.chrome_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        
        # Sync options card
        options_frame = ttk.LabelFrame(main_container, text="⚙️ Sync Options", 
                                      style='Card.TLabelframe', padding=15)
        options_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Direction selection
        direction_row = tk.Frame(options_frame)
        direction_row.pack(fill=tk.X, pady=8)
        ttk.Label(direction_row, text="Direction:", style='Heading.TLabel', width=15).pack(side=tk.LEFT, padx=(0, 10))
        self.direction_var = tk.StringVar(value="bidirectional")
        direction_container = tk.Frame(direction_row)
        direction_container.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        ttk.Radiobutton(direction_container, text="🦊 → ⚡ Firefox to Chrome", 
                       variable=self.direction_var, value="firefox_to_chrome").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(direction_container, text="⚡ → 🦊 Chrome to Firefox", 
                       variable=self.direction_var, value="chrome_to_firefox").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(direction_container, text="🔄 Bidirectional", 
                       variable=self.direction_var, value="bidirectional").pack(side=tk.LEFT, padx=5)
        
        # Sync mode
        mode_row = tk.Frame(options_frame)
        mode_row.pack(fill=tk.X, pady=8)
        ttk.Label(mode_row, text="Sync Mode:", style='Heading.TLabel', width=15).pack(side=tk.LEFT, padx=(0, 10))
        self.sync_mode_var = tk.StringVar(value="Full Sync")
        sync_mode_combo = ttk.Combobox(mode_row, textvariable=self.sync_mode_var, state="readonly",
                                      values=["Full Sync", "Incremental Sync", "Merge Sync"], width=30)
        sync_mode_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        sync_mode_combo.bind('<<ComboboxSelected>>', lambda e: self._on_sync_mode_change())
        
        # Merge strategy
        strategy_row = tk.Frame(options_frame)
        strategy_row.pack(fill=tk.X, pady=8)
        ttk.Label(strategy_row, text="Merge Strategy:", style='Heading.TLabel', width=15).pack(side=tk.LEFT, padx=(0, 10))
        self.merge_strategy_var = tk.StringVar(value="Keep All (rename duplicates)")
        merge_combo = ttk.Combobox(strategy_row, textvariable=self.merge_strategy_var, state="readonly",
                                  values=["Keep All (rename duplicates)", "Keep Newer (timestamp)", 
                                         "Firefox Priority", "Chrome Priority", "Smart Merge"], width=30)
        merge_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Options checkboxes
        checkbox_row = tk.Frame(options_frame)
        checkbox_row.pack(fill=tk.X, pady=(10, 0))
        
        self.backup_var = tk.BooleanVar(value=True)
        backup_cb = ttk.Checkbutton(checkbox_row, text="💾 Backup before sync", 
                                    variable=self.backup_var)
        backup_cb.pack(side=tk.LEFT, padx=(0, 20))
        
        self.dry_run_var = tk.BooleanVar(value=False)
        dry_run_cb = ttk.Checkbutton(checkbox_row, text="👁️ Dry run (preview only)", 
                                     variable=self.dry_run_var)
        dry_run_cb.pack(side=tk.LEFT)
        
        # Status and progress card
        status_frame = ttk.LabelFrame(main_container, text="📊 Status", 
                                      style='Card.TLabelframe', padding=15)
        status_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        self.progress_var = tk.StringVar(value="✨ Ready to sync")
        self.progress_label = ttk.Label(status_frame, textvariable=self.progress_var, 
                                       style='Status.TLabel', font=('Segoe UI', 10))
        self.progress_label.pack(anchor=tk.W, pady=(0, 10))
        
        self.progress_bar = ttk.Progressbar(status_frame, mode='indeterminate', length=400)
        self.progress_bar.pack(fill=tk.X, pady=(0, 5))
        
        # Log output card - fixed height, no expansion
        log_frame = ttk.LabelFrame(main_container, text="📝 Activity Log", 
                                   style='Card.TLabelframe', padding=10)
        log_frame.grid(row=4, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        log_frame.grid_rowconfigure(0, weight=1)
        log_frame.grid_columnconfigure(0, weight=1)
        
        # Configure log text widget with better styling - fixed height
        self.log_text = scrolledtext.ScrolledText(log_frame, height=6, width=75, 
                                                  font=('Consolas', 9),
                                                  bg='#2c3e50', fg='#ecf0f1',
                                                  insertbackground='#ecf0f1',
                                                  selectbackground='#3498db',
                                                  wrap=tk.WORD)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure tags for colored log messages
        self.log_text.tag_config('info', foreground='#3498db')
        self.log_text.tag_config('success', foreground='#27ae60')
        self.log_text.tag_config('error', foreground='#e74c3c')
        self.log_text.tag_config('warning', foreground='#f39c12')
        
        # Buttons section - always at bottom, never hidden
        button_frame = tk.Frame(main_container, bg='#ecf0f1')
        button_frame.grid(row=5, column=0, sticky=(tk.W, tk.E), pady=(10, 0))
        
        # Primary action button
        self.sync_button = ttk.Button(button_frame, text="🚀 Start Sync", 
                                     command=self._start_sync, style='Primary.TButton')
        self.sync_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # Secondary buttons
        ttk.Button(button_frame, text="🗑️ Clear Log", 
                  command=self._clear_log, style='Secondary.TButton').pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="❌ Exit", 
                  command=self.root.quit, style='Secondary.TButton').pack(side=tk.RIGHT, padx=5)
    
    def _on_sync_mode_change(self):
        """Handle sync mode change to update merge strategy visibility."""
        mode = self.sync_mode_var.get()
        # Merge strategy is most relevant for merge mode
        pass
    
    def _load_profiles(self):
        """Load browser profiles."""
        firefox_profiles = get_firefox_profiles()
        chrome_profiles = get_chrome_profiles()
        
        if firefox_profiles:
            firefox_names = [p['name'] for p in firefox_profiles]
            self.firefox_combo['values'] = firefox_names
            self.firefox_combo.current(0)
        else:
            self.log("⚠️ WARNING: No Firefox profiles found", 'warning')
        
        if chrome_profiles:
            chrome_names = [p['name'] for p in chrome_profiles]
            self.chrome_combo['values'] = chrome_names
            self.chrome_combo.current(0)
        else:
            self.log("⚠️ WARNING: No Chrome profiles found", 'warning')
    
    def log(self, message: str, tag: str = 'info'):
        """
        Add message to log with styling.
        
        Args:
            message: Log message
            tag: Tag for styling ('info', 'success', 'error', 'warning')
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n", tag)
        self.log_text.see(tk.END)
        self.root.update_idletasks()
    
    def _clear_log(self):
        """Clear log output."""
        self.log_text.delete(1.0, tk.END)
    
    def _start_sync(self):
        """Start sync operation."""
        if self.sync_thread and self.sync_thread.is_alive():
            messagebox.showwarning("Sync in Progress", "A sync operation is already running!")
            return
        
        # Get configuration
        firefox_profile = self.firefox_profile_var.get() or None
        chrome_profile = self.chrome_profile_var.get() or None
        
        if not firefox_profile or not chrome_profile:
            messagebox.showerror("Error", "Please select both Firefox and Chrome profiles!")
            return
        
        direction_str = self.direction_var.get()
        direction_map = {
            "firefox_to_chrome": SyncDirection.FIREFOX_TO_CHROME,
            "chrome_to_firefox": SyncDirection.CHROME_TO_FIREFOX,
            "bidirectional": SyncDirection.BIDIRECTIONAL
        }
        direction = direction_map[direction_str]
        
        # Map display names to enum values
        sync_mode_map = {
            "Full Sync": "full",
            "Incremental Sync": "incremental",
            "Merge Sync": "merge"
        }
        sync_mode_str = sync_mode_map.get(self.sync_mode_var.get(), "full")
        sync_mode = SyncMode(sync_mode_str)
        
        merge_strategy_map = {
            "Keep All (rename duplicates)": "keep_all",
            "Keep Newer (timestamp)": "timestamp",
            "Firefox Priority": "firefox_priority",
            "Chrome Priority": "chrome_priority",
            "Smart Merge": "smart"
        }
        merge_strategy_str = merge_strategy_map.get(self.merge_strategy_var.get(), "keep_all")
        merge_strategy = MergeStrategy(merge_strategy_str)
        
        backup_before_sync = self.backup_var.get()
        dry_run = self.dry_run_var.get()
        
        # Disable sync button and update UI
        self.sync_button.config(state='disabled')
        self.progress_bar.start(10)
        self.progress_var.set("🔄 Syncing bookmarks...")
        self.log("=" * 60, 'info')
        self.log("Starting bookmark synchronization...", 'info')
        
        # Start sync in thread
        self.sync_thread = threading.Thread(
            target=self._sync_worker,
            args=(firefox_profile, chrome_profile, direction, sync_mode, merge_strategy, backup_before_sync, dry_run),
            daemon=True
        )
        self.sync_thread.start()
    
    def _sync_worker(self, firefox_profile: str, chrome_profile: str, direction: SyncDirection,
                    sync_mode: SyncMode, merge_strategy: MergeStrategy, backup_before_sync: bool, dry_run: bool):
        """Worker thread for sync operation."""
        try:
            self.log(f"📋 Configuration:", 'info')
            self.log(f"   Direction: {direction.value}", 'info')
            self.log(f"   Firefox profile: {firefox_profile}", 'info')
            self.log(f"   Chrome profile: {chrome_profile}", 'info')
            self.log(f"   Sync mode: {sync_mode.value}", 'info')
            self.log(f"   Merge strategy: {merge_strategy.value}", 'info')
            self.log(f"   Backup: {'Yes' if backup_before_sync else 'No'}", 'info')
            self.log(f"   Dry run: {'Yes' if dry_run else 'No'}", 'info')
            self.log("", 'info')
            
            if backup_before_sync:
                self.log("💾 Creating backups...", 'info')
            
            self.log("🔄 Initializing sync engine...", 'info')
            engine = SyncEngine(
                firefox_profile=firefox_profile,
                chrome_profile=chrome_profile,
                merge_strategy=merge_strategy,
                backup_before_sync=backup_before_sync,
                sync_mode=sync_mode
            )
            
            self.sync_engine = engine
            
            self.log("🚀 Starting synchronization...", 'info')
            success = engine.sync(direction=direction, dry_run=dry_run)
            
            if success:
                self.log("", 'info')
                self.log("✅ Sync completed successfully!", 'success')
                self.log("=" * 60, 'info')
                self.progress_var.set("✅ Sync completed successfully!")
                self.root.after(0, lambda: messagebox.showinfo("Success", 
                    "Bookmark sync completed successfully!\n\nCheck the log for details."))
            else:
                self.log("", 'info')
                self.log("❌ Sync failed! Check the log for details.", 'error')
                self.log("=" * 60, 'info')
                self.progress_var.set("❌ Sync failed!")
                self.root.after(0, lambda: messagebox.showerror("Error", 
                    "Bookmark sync failed. Check the log for details."))
        
        except Exception as e:
            self.log("", 'info')
            self.log(f"❌ Error: {str(e)}", 'error')
            self.log("=" * 60, 'info')
            self.progress_var.set(f"❌ Error: {str(e)}")
            self.root.after(0, lambda: messagebox.showerror("Error", f"Sync failed:\n{str(e)}"))
        
        finally:
            # Re-enable sync button
            self.root.after(0, self._sync_finished)
    
    def _sync_finished(self):
        """Called when sync finishes."""
        self.progress_bar.stop()
        self.sync_button.config(state='normal')
        if "Syncing" in self.progress_var.get():
            self.progress_var.set("✨ Ready to sync")


def run_gui():
    """Run the GUI application."""
    root = tk.Tk()
    app = BookmarkSyncGUI(root)
    root.mainloop()


if __name__ == "__main__":
    run_gui()
