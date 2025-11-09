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
from src.ui.theme import THEME

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
        
        self.colors = THEME.copy()
        self.root.configure(bg=self.colors["background"])
        
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
        colors = self.colors
        style = ttk.Style()
        
        try:
            style.theme_use('clam')
        except tk.TclError:
            pass
        
        style.configure('TFrame', background=colors["background"])
        style.configure('TLabel', background=colors["background"], foreground=colors["text"])
        
        style.configure('Title.TLabel', font=('Segoe UI', 22, 'bold'),
                        foreground=colors["accent"], background=colors["background"])
        style.configure('Subtitle.TLabel', font=('Segoe UI', 11),
                        foreground=colors["muted_text"], background=colors["background"])
        style.configure('Heading.TLabel', font=('Segoe UI', 10, 'bold'),
                        foreground=colors["text"], background=colors["surface"])
        style.configure('StatusCard.TLabel', font=('Segoe UI', 10),
                        foreground=colors["muted_text"], background=colors["surface"])
        
        style.configure('Card.TLabelframe',
                        background=colors["surface"],
                        borderwidth=1,
                        relief='solid',
                        foreground=colors["accent"])
        style.configure('Card.TLabelframe.Label',
                        background=colors["surface"],
                        foreground=colors["accent"],
                        font=('Segoe UI', 11, 'bold'))
        
        style.configure('Primary.TButton',
                        font=('Segoe UI', 11, 'bold'),
                        padding=10,
                        foreground=colors["background"],
                        background=colors["accent"],
                        borderwidth=0)
        style.map('Primary.TButton',
                  background=[('active', colors["accent_hover"]),
                              ('disabled', colors["border"])],
                  foreground=[('disabled', colors["muted_text"])])
        
        style.configure('Secondary.TButton',
                        font=('Segoe UI', 10),
                        padding=8,
                        foreground=colors["text"],
                        background=colors["surface_alt"])
        style.map('Secondary.TButton',
                  background=[('active', colors["border"])])
        
        style.configure('Accent.Horizontal.TProgressbar',
                        background=colors["accent"],
                        troughcolor=colors["surface"],
                        bordercolor=colors["surface"])
        
        style.configure('Modern.TCombobox',
                        fieldbackground=colors["surface_alt"],
                        background=colors["surface_alt"],
                        foreground=colors["text"],
                        bordercolor=colors["border"],
                        padding=4)
        style.map('Modern.TCombobox',
                  fieldbackground=[('readonly', colors["surface_alt"])],
                  foreground=[('readonly', colors["text"])])
        style.configure('TRadiobutton', background=colors["surface"], foreground=colors["text"])
        style.configure('TCheckbutton', background=colors["surface"], foreground=colors["text"])
    
    def _create_widgets(self):
        """Create GUI widgets."""
        # Use grid for better control
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        
        card_bg = self.colors["surface"]
        accent = self.colors["accent"]
        
        # Main container with padding
        main_container = tk.Frame(self.root, bg=self.colors["background"])
        main_container.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=15, pady=15)
        main_container.grid_rowconfigure(4, weight=1)  # Log area expands
        main_container.grid_columnconfigure(0, weight=1)
        
        # Header section
        header_frame = tk.Frame(main_container, bg=self.colors["background"])
        header_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 15))
        
        title_label = ttk.Label(header_frame, text="🔄 Bookmark Sync", style='Title.TLabel')
        title_label.pack(anchor=tk.W)
        
        subtitle_label = ttk.Label(
            header_frame,
            text="Synchronize bookmarks between Firefox and Chrome",
            style='Subtitle.TLabel'
        )
        subtitle_label.pack(anchor=tk.W, pady=(5, 0))
        
        # Profile selection card
        profile_frame = ttk.LabelFrame(main_container, text="🌐 Browser Profiles", 
                                       style='Card.TLabelframe', padding=15)
        profile_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Firefox profile
        firefox_row = tk.Frame(profile_frame, bg=card_bg)
        firefox_row.pack(fill=tk.X, pady=8)
        ttk.Label(firefox_row, text="🦊 Firefox Profile:", style='Heading.TLabel').pack(side=tk.LEFT, padx=(0, 10))
        self.firefox_profile_var = tk.StringVar()
        self.firefox_combo = ttk.Combobox(
            firefox_row,
            textvariable=self.firefox_profile_var,
            state="readonly",
            width=35,
            style='Modern.TCombobox'
        )
        self.firefox_profile_value = ttk.Label(firefox_row, text="", style='StatusCard.TLabel')
        
        # Chrome profile
        chrome_row = tk.Frame(profile_frame, bg=card_bg)
        chrome_row.pack(fill=tk.X, pady=8)
        ttk.Label(chrome_row, text="⚡ Chrome Profile:", style='Heading.TLabel').pack(side=tk.LEFT, padx=(0, 10))
        self.chrome_profile_var = tk.StringVar()
        self.chrome_combo = ttk.Combobox(
            chrome_row,
            textvariable=self.chrome_profile_var,
            state="readonly",
            width=35,
            style='Modern.TCombobox'
        )
        self.chrome_profile_value = ttk.Label(chrome_row, text="", style='StatusCard.TLabel')

        self.profile_widgets = {
            "firefox": {
                "combo": self.firefox_combo,
                "label": self.firefox_profile_value,
                "pack": dict(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
            },
            "chrome": {
                "combo": self.chrome_combo,
                "label": self.chrome_profile_value,
                "pack": dict(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
            }
        }
        self._set_profile_display("firefox", [], "Detecting Firefox profiles…")
        self._set_profile_display("chrome", [], "Detecting Chrome profiles…")
        
        # Sync options card
        options_frame = ttk.LabelFrame(main_container, text="⚙️ Sync Options", 
                                      style='Card.TLabelframe', padding=15)
        options_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Direction selection
        direction_row = tk.Frame(options_frame, bg=card_bg)
        direction_row.pack(fill=tk.X, pady=8)
        ttk.Label(direction_row, text="Direction:", style='Heading.TLabel', width=15).pack(side=tk.LEFT, padx=(0, 10))
        self.direction_var = tk.StringVar(value="bidirectional")
        direction_container = tk.Frame(direction_row, bg=card_bg)
        direction_container.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        ttk.Radiobutton(direction_container, text="🦊 → ⚡ Firefox to Chrome", 
                       variable=self.direction_var, value="firefox_to_chrome").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(direction_container, text="⚡ → 🦊 Chrome to Firefox", 
                       variable=self.direction_var, value="chrome_to_firefox").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(direction_container, text="🔄 Bidirectional", 
                       variable=self.direction_var, value="bidirectional").pack(side=tk.LEFT, padx=5)
        
        # Sync mode
        mode_row = tk.Frame(options_frame, bg=card_bg)
        mode_row.pack(fill=tk.X, pady=8)
        ttk.Label(mode_row, text="Sync Mode:", style='Heading.TLabel', width=15).pack(side=tk.LEFT, padx=(0, 10))
        self.sync_mode_var = tk.StringVar(value="Full Sync")
        sync_mode_combo = ttk.Combobox(
            mode_row,
            textvariable=self.sync_mode_var,
            state="readonly",
            values=["Full Sync", "Incremental Sync", "Merge Sync"],
            width=30,
            style='Modern.TCombobox'
        )
        sync_mode_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        sync_mode_combo.bind('<<ComboboxSelected>>', lambda e: self._on_sync_mode_change())
        
        # Merge strategy
        strategy_row = tk.Frame(options_frame, bg=card_bg)
        strategy_row.pack(fill=tk.X, pady=8)
        ttk.Label(strategy_row, text="Merge Strategy:", style='Heading.TLabel', width=15).pack(side=tk.LEFT, padx=(0, 10))
        self.merge_strategy_var = tk.StringVar(value="Keep All (rename duplicates)")
        merge_combo = ttk.Combobox(
            strategy_row,
            textvariable=self.merge_strategy_var,
            state="readonly",
            values=[
                "Keep All (rename duplicates)",
                "Keep Newer (timestamp)",
                "Firefox Priority",
                "Chrome Priority",
                "Smart Merge"
            ],
            width=30,
            style='Modern.TCombobox'
        )
        merge_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Options checkboxes
        checkbox_row = tk.Frame(options_frame, bg=card_bg)
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
                                       style='StatusCard.TLabel', font=('Segoe UI', 10))
        self.progress_label.pack(anchor=tk.W, pady=(0, 10))
        
        self.progress_bar = ttk.Progressbar(status_frame, mode='indeterminate', length=400,
                                            style='Accent.Horizontal.TProgressbar')
        self.progress_bar.pack(fill=tk.X, pady=(0, 5))
        
        # Log output card - fixed height, no expansion
        log_frame = ttk.LabelFrame(main_container, text="📝 Activity Log", 
                                   style='Card.TLabelframe', padding=10)
        log_frame.grid(row=4, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        log_frame.grid_rowconfigure(0, weight=1)
        log_frame.grid_columnconfigure(0, weight=1)
        
        # Configure log text widget with better styling - fixed height
        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            height=6,
            width=75,
            font=('Consolas', 9),
            bg=self.colors["log_bg"],
            fg=self.colors["text"],
            insertbackground=self.colors["accent"],
            selectbackground=self.colors["accent_soft"],
            selectforeground=self.colors["text"],
            wrap=tk.WORD,
            borderwidth=0,
            highlightthickness=1,
            highlightbackground=self.colors["border"]
        )
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure tags for colored log messages
        self.log_text.tag_config('info', foreground=self.colors["accent"])
        self.log_text.tag_config('success', foreground=self.colors["success"])
        self.log_text.tag_config('error', foreground=self.colors["danger"])
        self.log_text.tag_config('warning', foreground=self.colors["warning"])
        
        # Buttons section - always at bottom, never hidden
        button_frame = tk.Frame(main_container, bg=self.colors["background"])
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
    
    def _set_profile_display(self, browser: str, names: list[str], empty_message: str):
        """Show either a combobox or static label depending on profile count."""
        widgets = self.profile_widgets[browser]
        combo = widgets["combo"]
        label = widgets["label"]
        pack_args = widgets["pack"]
        
        combo.pack_forget()
        label.pack_forget()
        
        if names:
            combo['values'] = names
            combo.current(0)
        
        if not names:
            label.config(text=empty_message)
            label.pack(**pack_args)
        elif len(names) == 1:
            label.config(text=f"Using profile: {names[0]}")
            label.pack(**pack_args)
        else:
            combo.pack(**pack_args)
    
    def _load_profiles(self):
        """Load browser profiles."""
        firefox_profiles = get_firefox_profiles()
        chrome_profiles = get_chrome_profiles()
        
        if firefox_profiles:
            firefox_names = [p['name'] for p in firefox_profiles]
            self._set_profile_display("firefox", firefox_names, "No Firefox profiles found")
        else:
            self.log("⚠️ WARNING: No Firefox profiles found", 'warning')
            self._set_profile_display("firefox", [], "No Firefox profiles found")
        
        if chrome_profiles:
            chrome_names = [p['name'] for p in chrome_profiles]
            self._set_profile_display("chrome", chrome_names, "No Chrome profiles found")
        else:
            self.log("⚠️ WARNING: No Chrome profiles found", 'warning')
            self._set_profile_display("chrome", [], "No Chrome profiles found")
    
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
