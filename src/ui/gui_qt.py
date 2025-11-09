"""PyQt6 GUI interface for bookmark sync."""

import sys
from typing import Optional
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QRadioButton, QButtonGroup,
    QCheckBox, QProgressBar, QTextEdit, QGroupBox, QMessageBox,
    QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QTextCharFormat, QColor, QPalette, QIcon, QPixmap, QPainter
from PyQt6.QtSvg import QSvgRenderer

from src.core.sync_engine import SyncEngine, SyncDirection, SyncMode
from src.core.merger import MergeStrategy
from src.utils.paths import get_firefox_profiles, get_chrome_profiles
from src.utils.logger import setup_logger
from src.backup.backup_manager import BackupManager
from src.backup.restore_manager import RestoreManager
from pathlib import Path

logger = setup_logger()


class SyncWorker(QThread):
    """Worker thread for sync operations."""
    
    finished = pyqtSignal(bool, str)  # success, message
    log_message = pyqtSignal(str, str)  # message, level (info/success/error/warning)
    
    def __init__(self, firefox_profile: str, chrome_profile: str, direction: SyncDirection,
                 sync_mode: SyncMode, merge_strategy: MergeStrategy, 
                 backup_before_sync: bool, dry_run: bool):
        super().__init__()
        self.firefox_profile = firefox_profile
        self.chrome_profile = chrome_profile
        self.direction = direction
        self.sync_mode = sync_mode
        self.merge_strategy = merge_strategy
        self.backup_before_sync = backup_before_sync
        self.dry_run = dry_run
    
    def run(self):
        """Run sync operation."""
        try:
            self.log_message.emit("=" * 60, "info")
            self.log_message.emit("Starting bookmark synchronization...", "info")
            self.log_message.emit("", "info")
            self.log_message.emit("📋 Configuration:", "info")
            self.log_message.emit(f"   Direction: {self.direction.value}", "info")
            self.log_message.emit(f"   Firefox profile: {self.firefox_profile}", "info")
            self.log_message.emit(f"   Chrome profile: {self.chrome_profile}", "info")
            self.log_message.emit(f"   Sync mode: {self.sync_mode.value}", "info")
            self.log_message.emit(f"   Merge strategy: {self.merge_strategy.value}", "info")
            self.log_message.emit(f"   Backup: {'Yes' if self.backup_before_sync else 'No'}", "info")
            self.log_message.emit(f"   Dry run: {'Yes' if self.dry_run else 'No'}", "info")
            self.log_message.emit("", "info")
            
            if self.backup_before_sync:
                self.log_message.emit("💾 Creating backups...", "info")
            
            self.log_message.emit("🔄 Initializing sync engine...", "info")
            engine = SyncEngine(
                firefox_profile=self.firefox_profile,
                chrome_profile=self.chrome_profile,
                merge_strategy=self.merge_strategy,
                backup_before_sync=self.backup_before_sync,
                sync_mode=self.sync_mode
            )
            
            self.log_message.emit("🚀 Starting synchronization...", "info")
            success = engine.sync(direction=self.direction, dry_run=self.dry_run)
            
            if success:
                self.log_message.emit("", "info")
                self.log_message.emit("✅ Sync completed successfully!", "success")
                self.log_message.emit("=" * 60, "info")
                self.finished.emit(True, "Bookmark sync completed successfully!")
            else:
                self.log_message.emit("", "info")
                self.log_message.emit("❌ Sync failed! Check the log for details.", "error")
                self.log_message.emit("=" * 60, "info")
                self.finished.emit(False, "Bookmark sync failed. Check the log for details.")
        
        except Exception as e:
            self.log_message.emit("", "info")
            self.log_message.emit(f"❌ Error: {str(e)}", "error")
            self.log_message.emit("=" * 60, "info")
            self.finished.emit(False, f"Sync failed: {str(e)}")


class BookmarkSyncGUI(QMainWindow):
    """Main GUI window for bookmark sync."""
    
    def __init__(self):
        super().__init__()
        self.sync_worker: Optional[SyncWorker] = None
        self._load_icons()
        self._init_ui()
        self._load_profiles()
    
    def _load_icons(self):
        """Load SVG icons for Firefox and Chrome."""
        self.firefox_icon = None
        self.chrome_icon = None
        self.firefox_pixmap = None
        self.chrome_pixmap = None
        
        try:
            # Get project root directory - try multiple paths
            current_file = Path(__file__)
            project_root = current_file.parent.parent.parent
            
            # Also try current working directory
            cwd = Path.cwd()
            
            # Debug: log paths
            logger.debug(f"Looking for icons. Project root: {project_root}, CWD: {cwd}")
            
            # Load Firefox icon
            for root in [project_root, cwd]:
                firefox_svg = root / "firefox.svg"
                logger.debug(f"Checking Firefox SVG at: {firefox_svg} (exists: {firefox_svg.exists()})")
                if firefox_svg.exists():
                    renderer = QSvgRenderer(str(firefox_svg))
                    if renderer.isValid():
                        # Create larger pixmap for better quality
                        pixmap = QPixmap(48, 48)
                        # Use a light background for better visibility on dark theme
                        pixmap.fill(QColor(45, 45, 45, 200))  # Semi-transparent dark gray
                        painter = QPainter(pixmap)
                        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
                        renderer.render(painter)
                        painter.end()
                        self.firefox_icon = QIcon(pixmap)
                        self.firefox_pixmap = pixmap
                        logger.info(f"✓ Loaded Firefox icon from {firefox_svg}")
                        break
                    else:
                        logger.warning(f"Firefox SVG renderer is not valid: {firefox_svg}")
            
            # Load Chrome icon
            for root in [project_root, cwd]:
                chrome_svg = root / "chrome.svg"
                logger.debug(f"Checking Chrome SVG at: {chrome_svg} (exists: {chrome_svg.exists()})")
                if chrome_svg.exists():
                    renderer = QSvgRenderer(str(chrome_svg))
                    if renderer.isValid():
                        # Create larger pixmap for better quality
                        pixmap = QPixmap(48, 48)
                        # Use a light background for better visibility on dark theme
                        pixmap.fill(QColor(45, 45, 45, 200))  # Semi-transparent dark gray
                        painter = QPainter(pixmap)
                        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
                        renderer.render(painter)
                        painter.end()
                        self.chrome_icon = QIcon(pixmap)
                        self.chrome_pixmap = pixmap
                        logger.info(f"✓ Loaded Chrome icon from {chrome_svg}")
                        break
                    else:
                        logger.warning(f"Chrome SVG renderer is not valid: {chrome_svg}")
        except Exception as e:
            logger.warning(f"Could not load SVG icons: {e}")
            import traceback
            logger.debug(traceback.format_exc())
    
    def _init_ui(self):
        """Initialize the UI."""
        self.setWindowTitle("Bookmark Sync - Firefox ↔ Chrome")
        self.setGeometry(100, 100, 900, 900)
        self.setMinimumSize(750, 700)
        
        # Set window icon if available
        if self.firefox_icon:
            self.setWindowIcon(self.firefox_icon)
        
        # Apply dark theme to window
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e1e;
            }
            QWidget {
                background-color: #1e1e1e;
                color: #e0e0e0;
            }
        """)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # Header with icons
        header_layout = QHBoxLayout()
        header_text_layout = QVBoxLayout()
        
        # Icons side by side above title
        if self.firefox_pixmap and self.chrome_pixmap:
            icons_layout = QHBoxLayout()
            icons_layout.setSpacing(15)
            icons_layout.setContentsMargins(0, 0, 0, 5)
            firefox_header_icon = QLabel()
            firefox_scaled = self.firefox_pixmap.scaled(48, 48, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            firefox_header_icon.setPixmap(firefox_scaled)
            firefox_header_icon.setFixedSize(48, 48)
            chrome_header_icon = QLabel()
            chrome_scaled = self.chrome_pixmap.scaled(48, 48, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            chrome_header_icon.setPixmap(chrome_scaled)
            chrome_header_icon.setFixedSize(48, 48)
            icons_layout.addStretch()
            icons_layout.addWidget(firefox_header_icon)
            icons_layout.addWidget(chrome_header_icon)
            icons_layout.addStretch()
            header_text_layout.addLayout(icons_layout)
        
        title = QLabel("Bookmark Sync")
        title_font = QFont()
        title_font.setPointSize(24)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("color: #64b5f6; margin-bottom: 5px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        subtitle = QLabel("Synchronize bookmarks between Firefox and Chrome")
        subtitle.setStyleSheet("color: #9e9e9e; font-size: 12px;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        header_text_layout.addWidget(title)
        header_text_layout.addWidget(subtitle)
        header_layout.addLayout(header_text_layout)
        main_layout.addLayout(header_layout)
        
        # Browser Profiles Group
        profiles_group = QGroupBox("🌐 Browser Profiles")
        profiles_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 13px;
                color: #e0e0e0;
                border: 2px solid #424242;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 15px;
                background-color: #2d2d2d;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #64b5f6;
            }
        """)
        profiles_layout = QVBoxLayout()
        profiles_layout.setSpacing(10)
        
        # Firefox profile
        firefox_layout = QHBoxLayout()
        firefox_label_layout = QHBoxLayout()
        firefox_label_layout.setContentsMargins(0, 0, 0, 0)
        firefox_label_layout.setSpacing(8)
        
        if self.firefox_pixmap:
            firefox_icon_label = QLabel()
            scaled_pixmap = self.firefox_pixmap.scaled(24, 24, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            firefox_icon_label.setPixmap(scaled_pixmap)
            firefox_icon_label.setFixedSize(24, 24)
            firefox_label_layout.addWidget(firefox_icon_label)
        
        firefox_label = QLabel("Firefox Profile:")
        firefox_label.setMinimumWidth(150)
        firefox_label.setStyleSheet("font-weight: bold; color: #e0e0e0;")
        firefox_label_layout.addWidget(firefox_label)
        firefox_label_layout.addStretch()
        firefox_layout.addLayout(firefox_label_layout)
        
        self.firefox_combo = QComboBox()
        self.firefox_combo.setMinimumHeight(30)
        self.firefox_combo.setStyleSheet("""
            QComboBox {
                background-color: #3d3d3d;
                color: #e0e0e0;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 5px;
            }
            QComboBox:hover {
                border: 1px solid #64b5f6;
            }
            QComboBox::drop-down {
                border: none;
                background-color: #3d3d3d;
            }
            QComboBox QAbstractItemView {
                background-color: #3d3d3d;
                color: #e0e0e0;
                selection-background-color: #64b5f6;
                selection-color: #ffffff;
            }
        """)
        firefox_layout.addWidget(self.firefox_combo)
        profiles_layout.addLayout(firefox_layout)
        
        # Chrome profile
        chrome_layout = QHBoxLayout()
        chrome_label_layout = QHBoxLayout()
        chrome_label_layout.setContentsMargins(0, 0, 0, 0)
        chrome_label_layout.setSpacing(8)
        
        if self.chrome_pixmap:
            chrome_icon_label = QLabel()
            scaled_pixmap = self.chrome_pixmap.scaled(24, 24, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            chrome_icon_label.setPixmap(scaled_pixmap)
            chrome_icon_label.setFixedSize(24, 24)
            chrome_label_layout.addWidget(chrome_icon_label)
        
        chrome_label = QLabel("Chrome Profile:")
        chrome_label.setMinimumWidth(150)
        chrome_label.setStyleSheet("font-weight: bold; color: #e0e0e0;")
        chrome_label_layout.addWidget(chrome_label)
        chrome_label_layout.addStretch()
        chrome_layout.addLayout(chrome_label_layout)
        
        self.chrome_combo = QComboBox()
        self.chrome_combo.setMinimumHeight(30)
        self.chrome_combo.setStyleSheet(self.firefox_combo.styleSheet())
        chrome_layout.addWidget(self.chrome_combo)
        profiles_layout.addLayout(chrome_layout)
        
        profiles_group.setLayout(profiles_layout)
        main_layout.addWidget(profiles_group)
        
        # Sync Options Group
        options_group = QGroupBox("⚙️ Sync Options")
        options_group.setStyleSheet(profiles_group.styleSheet())
        
        # Style radio buttons
        radio_style = """
            QRadioButton {
                color: #e0e0e0;
                font-size: 12px;
            }
            QRadioButton::indicator {
                width: 18px;
                height: 18px;
                border: 2px solid #555555;
                border-radius: 9px;
                background-color: #3d3d3d;
            }
            QRadioButton::indicator:hover {
                border: 2px solid #64b5f6;
            }
            QRadioButton::indicator:checked {
                background-color: #64b5f6;
                border: 2px solid #64b5f6;
            }
        """
        options_layout = QVBoxLayout()
        options_layout.setSpacing(10)
        
        # Direction
        direction_label = QLabel("Direction:")
        direction_label.setMinimumWidth(150)
        direction_label.setStyleSheet("font-weight: bold; color: #e0e0e0;")
        direction_layout = QHBoxLayout()
        direction_layout.addWidget(direction_label)
        
        self.direction_group = QButtonGroup()
        
        # Create radio buttons with icons
        self.direction_firefox_to_chrome = QRadioButton("Firefox → Chrome")
        self.direction_firefox_to_chrome.setStyleSheet(radio_style)
        if self.firefox_icon:
            self.direction_firefox_to_chrome.setIcon(self.firefox_icon)
        
        self.direction_chrome_to_firefox = QRadioButton("Chrome → Firefox")
        self.direction_chrome_to_firefox.setStyleSheet(radio_style)
        if self.chrome_icon:
            self.direction_chrome_to_firefox.setIcon(self.chrome_icon)
        
        self.direction_bidirectional = QRadioButton("🔄 Bidirectional")
        self.direction_bidirectional.setStyleSheet(radio_style)
        self.direction_bidirectional.setChecked(True)
        
        self.direction_group.addButton(self.direction_firefox_to_chrome, 0)
        self.direction_group.addButton(self.direction_chrome_to_firefox, 1)
        self.direction_group.addButton(self.direction_bidirectional, 2)
        
        direction_buttons_layout = QHBoxLayout()
        direction_buttons_layout.addWidget(self.direction_firefox_to_chrome)
        direction_buttons_layout.addWidget(self.direction_chrome_to_firefox)
        direction_buttons_layout.addWidget(self.direction_bidirectional)
        direction_buttons_layout.addStretch()
        
        direction_layout.addLayout(direction_buttons_layout)
        direction_layout.addStretch()
        options_layout.addLayout(direction_layout)
        
        # Sync Mode
        mode_layout = QHBoxLayout()
        mode_label = QLabel("Sync Mode:")
        mode_label.setMinimumWidth(150)
        mode_label.setStyleSheet("font-weight: bold; color: #e0e0e0;")
        self.sync_mode_combo = QComboBox()
        self.sync_mode_combo.addItems(["Full Sync", "Incremental Sync", "Merge Sync"])
        self.sync_mode_combo.setMinimumHeight(30)
        self.sync_mode_combo.setStyleSheet(self.firefox_combo.styleSheet())
        mode_layout.addWidget(mode_label)
        mode_layout.addWidget(self.sync_mode_combo)
        mode_layout.addStretch()
        options_layout.addLayout(mode_layout)
        
        # Merge Strategy
        strategy_layout = QHBoxLayout()
        strategy_label = QLabel("Merge Strategy:")
        strategy_label.setMinimumWidth(150)
        strategy_label.setStyleSheet("font-weight: bold; color: #e0e0e0;")
        self.merge_strategy_combo = QComboBox()
        self.merge_strategy_combo.addItems([
            "Keep All (rename duplicates)",
            "Keep Newer (timestamp)",
            "Firefox Priority",
            "Chrome Priority",
            "Smart Merge"
        ])
        self.merge_strategy_combo.setMinimumHeight(30)
        self.merge_strategy_combo.setStyleSheet(self.firefox_combo.styleSheet())
        strategy_layout.addWidget(strategy_label)
        strategy_layout.addWidget(self.merge_strategy_combo)
        strategy_layout.addStretch()
        options_layout.addLayout(strategy_layout)
        
        # Checkboxes
        checkbox_style = """
            QCheckBox {
                color: #e0e0e0;
                font-size: 12px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 2px solid #555555;
                border-radius: 3px;
                background-color: #3d3d3d;
            }
            QCheckBox::indicator:hover {
                border: 2px solid #64b5f6;
            }
            QCheckBox::indicator:checked {
                background-color: #64b5f6;
                border: 2px solid #64b5f6;
            }
        """
        checkbox_layout = QHBoxLayout()
        self.backup_checkbox = QCheckBox("💾 Backup before sync")
        self.backup_checkbox.setChecked(True)
        self.backup_checkbox.setStyleSheet(checkbox_style)
        
        # Small restore button next to backup checkbox
        restore_button = QPushButton("💾 Restore")
        restore_button.setMaximumHeight(28)
        restore_button.setMaximumWidth(100)
        restore_button.setStyleSheet("""
            QPushButton {
                background-color: #81c784;
                color: #ffffff;
                font-weight: bold;
                font-size: 10px;
                border: none;
                border-radius: 4px;
                padding: 4px 8px;
            }
            QPushButton:hover {
                background-color: #66bb6a;
            }
        """)
        restore_button.clicked.connect(self._show_restore_dialog)
        restore_button.setToolTip("Restore from backup")
        
        checkbox_layout.addWidget(self.backup_checkbox)
        checkbox_layout.addWidget(restore_button)
        checkbox_layout.addSpacing(20)
        
        self.dry_run_checkbox = QCheckBox("👁️ Dry run (preview only)")
        self.dry_run_checkbox.setStyleSheet(checkbox_style)
        checkbox_layout.addWidget(self.dry_run_checkbox)
        checkbox_layout.addStretch()
        options_layout.addLayout(checkbox_layout)
        
        options_group.setLayout(options_layout)
        main_layout.addWidget(options_group)
        
        # Status Group
        status_group = QGroupBox("📊 Status")
        status_group.setStyleSheet(profiles_group.styleSheet())
        status_layout = QVBoxLayout()
        status_layout.setSpacing(10)
        
        self.status_label = QLabel("✨ Ready to sync")
        self.status_label.setStyleSheet("font-size: 11px; color: #9e9e9e;")
        status_layout.addWidget(self.status_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimumHeight(25)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #424242;
                border-radius: 5px;
                text-align: center;
                background-color: #2d2d2d;
            }
            QProgressBar::chunk {
                background-color: #64b5f6;
                border-radius: 3px;
            }
        """)
        status_layout.addWidget(self.progress_bar)
        
        status_group.setLayout(status_layout)
        main_layout.addWidget(status_group)
        
        # Log Group
        log_group = QGroupBox("📝 Activity Log")
        log_group.setStyleSheet(profiles_group.styleSheet())
        log_layout = QVBoxLayout()
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #1a1a1a;
                color: #e0e0e0;
                border: 2px solid #424242;
                border-radius: 5px;
                padding: 10px;
            }
        """)
        log_layout.addWidget(self.log_text)
        
        log_group.setLayout(log_layout)
        main_layout.addWidget(log_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.sync_button = QPushButton("🚀 Start Sync")
        self.sync_button.setMinimumHeight(40)
        self.sync_button.setMinimumWidth(150)
        self.sync_button.setStyleSheet("""
            QPushButton {
                background-color: #64b5f6;
                color: #ffffff;
                font-weight: bold;
                font-size: 13px;
                border: none;
                border-radius: 5px;
                padding: 10px;
            }
            QPushButton:hover {
                background-color: #42a5f5;
            }
            QPushButton:disabled {
                background-color: #555555;
                color: #888888;
            }
        """)
        self.sync_button.clicked.connect(self._start_sync)
        button_layout.addWidget(self.sync_button)
        
        clear_button = QPushButton("🗑️ Clear Log")
        clear_button.setMinimumHeight(35)
        clear_button.setStyleSheet("""
            QPushButton {
                background-color: #555555;
                color: #e0e0e0;
                font-weight: bold;
                border: none;
                border-radius: 5px;
                padding: 8px;
            }
            QPushButton:hover {
                background-color: #666666;
            }
        """)
        clear_button.clicked.connect(self._clear_log)
        button_layout.addWidget(clear_button)
        
        exit_button = QPushButton("❌ Exit")
        exit_button.setMinimumHeight(35)
        exit_button.setStyleSheet(clear_button.styleSheet())
        exit_button.clicked.connect(self.close)
        button_layout.addWidget(exit_button)
        
        main_layout.addLayout(button_layout)
        
        # Set main layout
        central_widget.setLayout(main_layout)
        
        # Configure log text colors
        self._setup_log_colors()
    
    def _setup_log_colors(self):
        """Setup color formatting for log messages."""
        # Colors are applied via HTML in log messages
        pass
    
    def _load_profiles(self):
        """Load browser profiles."""
        firefox_profiles = get_firefox_profiles()
        chrome_profiles = get_chrome_profiles()
        
        if firefox_profiles:
            firefox_names = [p['name'] for p in firefox_profiles]
            self.firefox_combo.addItems(firefox_names)
        else:
            self._log("⚠️ WARNING: No Firefox profiles found", "warning")
        
        if chrome_profiles:
            chrome_names = [p['name'] for p in chrome_profiles]
            self.chrome_combo.addItems(chrome_names)
        else:
            self._log("⚠️ WARNING: No Chrome profiles found", "warning")
    
    def _log(self, message: str, level: str = "info"):
        """
        Add message to log with styling.
        
        Args:
            message: Log message
            level: Log level (info, success, error, warning)
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Color mapping for dark theme
        colors = {
            "info": "#64b5f6",      # Light blue
            "success": "#81c784",   # Light green
            "error": "#e57373",      # Light red
            "warning": "#ffb74d"     # Light orange
        }
        color = colors.get(level, "#e0e0e0")
        
        # Format message with HTML
        formatted = f'<span style="color: {color};">[{timestamp}] {message}</span>'
        self.log_text.append(formatted)
        
        # Auto-scroll to bottom
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def _clear_log(self):
        """Clear log output."""
        self.log_text.clear()
    
    def _start_sync(self):
        """Start sync operation."""
        if self.sync_worker and self.sync_worker.isRunning():
            QMessageBox.warning(self, "Sync in Progress", "A sync operation is already running!")
            return
        
        # Get configuration
        firefox_profile = self.firefox_combo.currentText() or None
        chrome_profile = self.chrome_combo.currentText() or None
        
        if not firefox_profile or not chrome_profile:
            QMessageBox.critical(self, "Error", "Please select both Firefox and Chrome profiles!")
            return
        
        # Get direction
        checked_button = self.direction_group.checkedButton()
        if checked_button == self.direction_firefox_to_chrome:
            direction = SyncDirection.FIREFOX_TO_CHROME
        elif checked_button == self.direction_chrome_to_firefox:
            direction = SyncDirection.CHROME_TO_FIREFOX
        else:
            direction = SyncDirection.BIDIRECTIONAL
        
        # Get sync mode
        sync_mode_map = {
            "Full Sync": "full",
            "Incremental Sync": "incremental",
            "Merge Sync": "merge"
        }
        sync_mode_str = sync_mode_map.get(self.sync_mode_combo.currentText(), "full")
        sync_mode = SyncMode(sync_mode_str)
        
        # Get merge strategy
        merge_strategy_map = {
            "Keep All (rename duplicates)": "keep_all",
            "Keep Newer (timestamp)": "timestamp",
            "Firefox Priority": "firefox_priority",
            "Chrome Priority": "chrome_priority",
            "Smart Merge": "smart"
        }
        merge_strategy_str = merge_strategy_map.get(self.merge_strategy_combo.currentText(), "keep_all")
        merge_strategy = MergeStrategy(merge_strategy_str)
        
        backup_before_sync = self.backup_checkbox.isChecked()
        dry_run = self.dry_run_checkbox.isChecked()
        
        # Disable sync button and update UI
        self.sync_button.setEnabled(False)
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        self.status_label.setText("🔄 Syncing bookmarks...")
        self.status_label.setStyleSheet("font-size: 11px; color: #3498db; font-weight: bold;")
        
        # Create and start worker thread
        self.sync_worker = SyncWorker(
            firefox_profile, chrome_profile, direction, sync_mode,
            merge_strategy, backup_before_sync, dry_run
        )
        self.sync_worker.log_message.connect(self._log)
        self.sync_worker.finished.connect(self._sync_finished)
        self.sync_worker.start()
    
    def _sync_finished(self, success: bool, message: str):
        """Called when sync finishes."""
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(1)
        self.sync_button.setEnabled(True)
        
        if success:
            self.status_label.setText("✅ Sync completed successfully!")
            self.status_label.setStyleSheet("font-size: 11px; color: #81c784; font-weight: bold;")
            QMessageBox.information(self, "Success", message)
        else:
            self.status_label.setText("❌ Sync failed!")
            self.status_label.setStyleSheet("font-size: 11px; color: #e57373; font-weight: bold;")
            QMessageBox.critical(self, "Error", message)
    
    def _show_restore_dialog(self):
        """Show restore backup dialog."""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QLabel, QPushButton
        
        backup_manager = BackupManager()
        backups = backup_manager.list_backups()
        
        if not backups:
            QMessageBox.information(self, "No Backups", 
                f"No backups found.\n\nBackup directory: {backup_manager.backup_dir.absolute()}\n\n"
                "Backups are created automatically before syncing.")
            return
        
        # Create dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("💾 Restore Backup")
        dialog.setMinimumWidth(700)
        dialog.setMinimumHeight(500)
        dialog.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
            }
            QLabel {
                color: #e0e0e0;
            }
            QListWidget {
                background-color: #2d2d2d;
                color: #e0e0e0;
                border: 2px solid #424242;
                border-radius: 5px;
                padding: 5px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #424242;
            }
            QListWidget::item:selected {
                background-color: #64b5f6;
                color: #ffffff;
            }
            QListWidget::item:hover {
                background-color: #3d3d3d;
            }
        """)
        
        layout = QVBoxLayout(dialog)
        
        # Header
        header_label = QLabel(f"📁 Backup Directory: {backup_manager.backup_dir.absolute()}")
        header_label.setStyleSheet("color: #9e9e9e; font-size: 11px; padding: 10px;")
        layout.addWidget(header_label)
        
        # Instructions
        info_label = QLabel("Select a backup to restore:")
        info_label.setStyleSheet("color: #e0e0e0; font-size: 12px; font-weight: bold; padding: 5px;")
        layout.addWidget(info_label)
        
        # Backup list
        backup_list = QListWidget()
        for backup in backups:
            timestamp = backup.get('timestamp', 'Unknown')
            source = backup.get('source', 'unknown').upper()
            profile = backup.get('profile', 'unknown')
            file = backup.get('file', 'unknown')
            size = backup.get('size', 0)
            size_mb = size / (1024 * 1024) if size else 0
            
            item_text = f"{source} - {profile}\n"
            item_text += f"  📅 {timestamp[:19]}\n"
            item_text += f"  📄 {file}\n"
            item_text += f"  💾 {size_mb:.2f} MB"
            
            backup_list.addItem(item_text)
            # Store backup data in item
            backup_list.item(backup_list.count() - 1).setData(256, backup)  # UserRole
        
        layout.addWidget(backup_list)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_button = QPushButton("Cancel")
        cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #555555;
                color: #e0e0e0;
                font-weight: bold;
                border: none;
                border-radius: 5px;
                padding: 8px 20px;
            }
            QPushButton:hover {
                background-color: #666666;
            }
        """)
        cancel_button.clicked.connect(dialog.reject)
        button_layout.addWidget(cancel_button)
        
        restore_button = QPushButton("💾 Restore Selected")
        restore_button.setStyleSheet("""
            QPushButton {
                background-color: #81c784;
                color: #ffffff;
                font-weight: bold;
                border: none;
                border-radius: 5px;
                padding: 8px 20px;
            }
            QPushButton:hover {
                background-color: #66bb6a;
            }
        """)
        restore_button.clicked.connect(lambda: self._restore_backup(backup_list, dialog, backup_manager))
        button_layout.addWidget(restore_button)
        
        layout.addLayout(button_layout)
        
        dialog.exec()
    
    def _restore_backup(self, backup_list, dialog, backup_manager):
        """Restore selected backup."""
        current_item = backup_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "No Selection", "Please select a backup to restore.")
            return
        
        backup = current_item.data(256)  # Get backup data
        if not backup:
            QMessageBox.critical(self, "Error", "Invalid backup data.")
            return
        
        backup_path = Path(backup['path'])
        source = backup['source']
        profile_name = backup['profile']
        
        # Confirm restore
        reply = QMessageBox.question(
            self,
            "Confirm Restore",
            f"⚠️ This will replace current {source.upper()} bookmarks with the backup.\n\n"
            f"Backup: {backup['file']}\n"
            f"Date: {backup['timestamp'][:19]}\n"
            f"Profile: {profile_name}\n\n"
            f"A backup of your current bookmarks will be created first.\n\n"
            f"Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        # Get profile path
        try:
            if source == "firefox":
                from src.browsers.firefox import FirefoxAdapter
                adapter = FirefoxAdapter(profile_name)
                profile_path = adapter.get_profile_path()
                
                if adapter.is_locked():
                    QMessageBox.critical(self, "Browser Locked", 
                        "Firefox is currently running. Please close Firefox and try again.")
                    return
            else:
                from src.browsers.chrome import ChromeAdapter
                adapter = ChromeAdapter(profile_name)
                profile_path = adapter.get_profile_path()
                
                if adapter.is_locked():
                    QMessageBox.critical(self, "Browser Locked", 
                        "Chrome is currently running. Please close Chrome and try again.")
                    return
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to get profile: {e}")
            return
        
        # Restore
        restore_manager = RestoreManager(backup_manager)
        self.log(f"🔄 Restoring {source} from backup...", "info")
        self.log(f"   Backup: {backup['file']}", "info")
        self.log(f"   Profile: {profile_name}", "info")
        
        dialog.accept()
        
        if source == "firefox":
            success = restore_manager.restore_firefox(backup_path, profile_path)
        else:
            success = restore_manager.restore_chrome(backup_path, profile_path)
        
        if success:
            self.log("✅ Restore completed successfully!", "success")
            self.status_label.setText("✅ Restore completed successfully!")
            self.status_label.setStyleSheet("font-size: 11px; color: #81c784; font-weight: bold;")
            QMessageBox.information(self, "Success", 
                f"Successfully restored {source.upper()} bookmarks from backup!\n\n"
                f"Backup: {backup['file']}\n"
                f"Profile: {profile_name}")
        else:
            self.log("❌ Restore failed!", "error")
            self.status_label.setText("❌ Restore failed!")
            self.status_label.setStyleSheet("font-size: 11px; color: #e57373; font-weight: bold;")
            QMessageBox.critical(self, "Error", "Failed to restore backup. Check the log for details.")


def run_gui():
    """Run the PyQt6 GUI application."""
    app = QApplication(sys.argv)
    
    # Set application style
    app.setStyle('Fusion')
    
    # Set dark palette
    palette = QPalette()
    
    # Window colors
    palette.setColor(QPalette.ColorRole.Window, QColor(30, 30, 30))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(224, 224, 224))
    
    # Base colors
    palette.setColor(QPalette.ColorRole.Base, QColor(45, 45, 45))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(61, 61, 61))
    
    # Text colors
    palette.setColor(QPalette.ColorRole.Text, QColor(224, 224, 224))
    palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 255, 255))
    
    # Button colors
    palette.setColor(QPalette.ColorRole.Button, QColor(61, 61, 61))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(224, 224, 224))
    
    # Highlight colors
    palette.setColor(QPalette.ColorRole.Highlight, QColor(100, 181, 246))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    
    # Disabled colors
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(85, 85, 85))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(136, 136, 136))
    
    app.setPalette(palette)
    
    window = BookmarkSyncGUI()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    run_gui()
