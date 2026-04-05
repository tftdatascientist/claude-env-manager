"""Entry point for Claude Environment Manager."""

import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from src.ui.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Claude Environment Manager")
    app.setApplicationVersion("0.1.0")

    # Dark theme stylesheet
    app.setStyleSheet("""
        QMainWindow {
            background-color: #1e1e1e;
        }
        QTreeView {
            background-color: #252526;
            color: #cccccc;
            border: none;
            font-size: 13px;
        }
        QTreeView::item:selected {
            background-color: #094771;
        }
        QTreeView::item:hover {
            background-color: #2a2d2e;
        }
        QHeaderView::section {
            background-color: #333333;
            color: #cccccc;
            padding: 4px;
            border: none;
        }
        QPlainTextEdit {
            background-color: #1e1e1e;
            color: #d4d4d4;
            border: none;
            selection-background-color: #264f78;
        }
        QMenuBar {
            background-color: #333333;
            color: #cccccc;
        }
        QMenuBar::item:selected {
            background-color: #094771;
        }
        QMenu {
            background-color: #252526;
            color: #cccccc;
            border: 1px solid #454545;
        }
        QMenu::item:selected {
            background-color: #094771;
        }
        QStatusBar {
            background-color: #007acc;
            color: white;
            font-size: 12px;
        }
        QLabel {
            color: #cccccc;
        }
        QSplitter::handle {
            background-color: #333333;
            width: 2px;
        }
        QMessageBox {
            background-color: #252526;
        }
        QMessageBox QLabel {
            color: #cccccc;
        }
        QTabWidget::pane {
            border: none;
            background-color: #1e1e1e;
        }
        QTabBar::tab {
            background-color: #2d2d2d;
            color: #969696;
            padding: 6px 16px;
            border: none;
            border-bottom: 2px solid transparent;
        }
        QTabBar::tab:selected {
            color: #ffffff;
            background-color: #1e1e1e;
            border-bottom: 2px solid #007acc;
        }
        QTabBar::tab:hover {
            color: #cccccc;
        }
        QTreeWidget {
            background-color: #1e1e1e;
            color: #cccccc;
            border: none;
            font-size: 12px;
            alternate-background-color: #252526;
        }
        QTreeWidget::item:selected {
            background-color: #094771;
        }
        QTreeWidget::item:hover {
            background-color: #2a2d2e;
        }
        QLineEdit {
            background-color: #3c3c3c;
            color: #cccccc;
            border: 1px solid #454545;
            padding: 4px 8px;
            border-radius: 2px;
        }
        QLineEdit:focus {
            border-color: #007acc;
        }
        QComboBox {
            background-color: #3c3c3c;
            color: #cccccc;
            border: 1px solid #454545;
            padding: 4px 8px;
        }
        QComboBox::drop-down {
            border: none;
        }
        QComboBox QAbstractItemView {
            background-color: #252526;
            color: #cccccc;
            selection-background-color: #094771;
        }
    """)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
