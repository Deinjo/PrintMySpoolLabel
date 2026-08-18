from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QSettings, QSize, Qt, QThreadPool, Signal, Slot
from PySide6.QtGui import QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)


TARGET_WIDTH = 320
TARGET_HEIGHT = 96
DEFAULT_PORT = "COM4"


class PrintSignals(QObject):
    completed = Signal(int, str)
    failed = Signal(str)


class PrintTask(QRunnable):
    def __init__(self, image_path: Path, port: str) -> None:
        super().__init__()
        self.image_path = image_path
        self.port = port
        self.signals = PrintSignals()

    @Slot()
    def run(self) -> None:
        executable = shutil.which("niimblue-cli.cmd") or shutil.which("niimblue-cli")
        if executable is None:
            self.signals.failed.emit(
                "niimblue-cli wurde nicht gefunden. Installiere "
                "@mmote/niimblue-node global und starte die Anwendung neu."
            )
            return

        command = [
            executable,
            "print",
            "--debug",
            "--transport",
            "serial",
            "--address",
            self.port,
            "--print-task",
            "D110M_V4",
            "--print-direction",
            "left",
            "--label-width",
            str(TARGET_WIDTH),
            "--label-height",
            str(TARGET_HEIGHT),
            "--image-fit",
            "fill",
            "--label-type",
            "1",
            "--density",
            "3",
            "--threshold",
            "128",
            "--quantity",
            "1",
            str(self.image_path),
        ]

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
        except OSError as exc:
            self.signals.failed.emit(f"Druckprogramm konnte nicht gestartet werden: {exc}")
            return

        output = "\n".join(part for part in (result.stdout, result.stderr) if part).strip()
        if result.returncode == 0:
            self.signals.completed.emit(result.returncode, output)
        else:
            self.signals.failed.emit(output or f"Druck fehlgeschlagen (Exit-Code {result.returncode}).")


class DropArea(QLabel):
    file_dropped = Signal(Path)

    def __init__(self) -> None:
        super().__init__("PNG-Datei hier ablegen")
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(QSize(520, 180))
        self.setAcceptDrops(True)
        self.setObjectName("dropArea")

    def dragEnterEvent(self, event) -> None:
        paths = [Path(url.toLocalFile()) for url in event.mimeData().urls()]
        if len(paths) == 1 and paths[0].suffix.lower() == ".png":
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        paths = [Path(url.toLocalFile()) for url in event.mimeData().urls()]
        if len(paths) == 1 and paths[0].suffix.lower() == ".png":
            self.file_dropped.emit(paths[0])
            event.acceptProposedAction()


class PreviewLabel(QLabel):
    def __init__(self) -> None:
        super().__init__("Noch kein Label ausgewählt")
        self._source_pixmap = QPixmap()
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumHeight(150)
        self.setStyleSheet("background: white; border: 1px solid #d2d9df; border-radius: 4px;")

    def set_source_pixmap(self, pixmap: QPixmap) -> None:
        self._source_pixmap = pixmap
        self._source_pixmap.setDevicePixelRatio(1.0)
        self._refresh_pixmap()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._refresh_pixmap()

    def _refresh_pixmap(self) -> None:
        if self._source_pixmap.isNull():
            return
        canvas_size = self.contentsRect().size()
        available = self.contentsRect().adjusted(18, 18, -18, -18).size()
        if available.width() <= 0 or available.height() <= 0:
            return
        preview = self._source_pixmap.scaled(available, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        canvas = QPixmap(canvas_size)
        canvas.fill("#e9eef1")
        x = (canvas.width() - preview.width()) // 2
        y = (canvas.height() - preview.height()) // 2
        painter = QPainter(canvas)
        painter.drawPixmap(x, y, preview)
        pen = QPen("#52616b")
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawRect(x, y, preview.width() - 1, preview.height() - 1)
        painter.end()
        super().setPixmap(canvas)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.settings = QSettings("Deinjo", "PrintMySpoolLabel")
        self.thread_pool = QThreadPool.globalInstance()
        self.image_path: Path | None = None
        self._build_ui()
        self._restore_settings()

    def _build_ui(self) -> None:
        self.setWindowTitle("PrintMySpoolLabel")
        self.resize(760, 620)
        self.setAcceptDrops(True)
        self.setStyleSheet(
            """
            QMainWindow { background: #f4f6f8; }
            QGroupBox { font-weight: 600; border: 1px solid #d2d9df; border-radius: 6px; margin-top: 10px; padding: 12px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; color: #263746; }
            QLineEdit, QPlainTextEdit { background: white; border: 1px solid #c7d0d9; border-radius: 4px; padding: 6px; }
            QPushButton { background: #087f8c; color: white; border: 0; border-radius: 4px; padding: 9px 18px; font-weight: 600; }
            QPushButton:hover { background: #066a75; }
            QPushButton:disabled { background: #aeb8c2; }
            #dropArea { background: white; border: 2px dashed #087f8c; border-radius: 8px; color: #52616b; font-size: 16px; }
            """
        )

        self.drop_area = DropArea()
        self.drop_area.file_dropped.connect(self._set_image)
        self.preview = PreviewLabel()

        self.file_label = QLabel("Keine Datei ausgewählt")
        self.port_edit = QLineEdit(DEFAULT_PORT)
        self.print_button = QPushButton("Drucken")
        self.print_button.setEnabled(False)
        self.print_button.clicked.connect(self._print)

        settings_box = QGroupBox("Druckeinstellungen")
        settings_form = QFormLayout(settings_box)
        settings_form.addRow("Datei:", self.file_label)
        settings_form.addRow("Serieller Port:", self.port_edit)
        settings_form.addRow("Druckformat:", QLabel("40 × 12 mm / 320 × 96 Pixel / 203 dpi"))
        settings_form.addRow("Druckmodus:", QLabel("D110M_V4 / links / nicht gespiegelt"))

        log_box = QGroupBox("Status")
        log_layout = QVBoxLayout(log_box)
        self.status_label = QLabel("Bereit")
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(300)
        self.log.setPlaceholderText("Druckdiagnose erscheint hier ...")
        log_layout.addWidget(self.status_label)
        log_layout.addWidget(self.log)

        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(self.print_button)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addWidget(self.drop_area)
        layout.addWidget(self.preview)
        layout.addWidget(settings_box)
        layout.addWidget(log_box, 1)
        layout.addLayout(buttons)
        self.setCentralWidget(central)

    def _restore_settings(self) -> None:
        self.port_edit.setText(str(self.settings.value("printer/port", DEFAULT_PORT)))

    @Slot(Path)
    def _set_image(self, path: Path) -> None:
        if not path.is_file():
            return
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            QMessageBox.warning(self, "Ungültige Datei", "Die PNG-Datei konnte nicht geladen werden.")
            return
        self.image_path = path
        self.file_label.setText(path.name)
        self.preview.set_source_pixmap(pixmap)
        self.drop_area.setText("Weitere PNG-Datei hier ablegen")
        self.print_button.setEnabled(True)
        self.status_label.setText("Label bereit zum Drucken")

    @Slot()
    def _print(self) -> None:
        if self.image_path is None:
            return
        port = self.port_edit.text().strip()
        if not port:
            QMessageBox.warning(self, "Port fehlt", "Bitte einen seriellen Port angeben.")
            return

        self.settings.setValue("printer/port", port)
        self.print_button.setEnabled(False)
        self.status_label.setText(f"Druck läuft über {port} ...")
        self.log.clear()
        task = PrintTask(self.image_path, port)
        task.signals.completed.connect(self._print_completed)
        task.signals.failed.connect(self._print_failed)
        self.thread_pool.start(task)

    @Slot(int, str)
    def _print_completed(self, _returncode: int, output: str) -> None:
        self.print_button.setEnabled(True)
        self.status_label.setText("Druck erfolgreich abgeschlossen")
        self.log.setPlainText(output)

    @Slot(str)
    def _print_failed(self, message: str) -> None:
        self.print_button.setEnabled(True)
        self.status_label.setText("Druck fehlgeschlagen")
        self.log.setPlainText(message)
        QMessageBox.warning(self, "Druckfehler", message)

    def closeEvent(self, event) -> None:
        self.settings.setValue("printer/port", self.port_edit.text().strip())
        self.thread_pool.waitForDone(3000)
        event.accept()


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("PrintMySpoolLabel")
    app.setOrganizationName("Deinjo")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
