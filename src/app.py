from __future__ import annotations

import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from pathlib import PurePosixPath

from PySide6.QtCore import QObject, QRunnable, QSettings, QSize, Qt, QThreadPool, Signal, Slot
from PySide6.QtGui import QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFormLayout,
    QGroupBox,
    QCheckBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QProgressBar,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

try:
    from .aml_renderer import AmlError, render_aml_to_png
except ImportError:
    from aml_renderer import AmlError, render_aml_to_png


TARGET_WIDTH = 320
TARGET_HEIGHT = 96
DEFAULT_PORT = "COM4"


class PrintSignals(QObject):
    completed = Signal(int, int, str)
    failed = Signal(int, str)


class PrintTask(QRunnable):
    def __init__(self, slot_index: int, image_path: Path, port: str, quantity: int) -> None:
        super().__init__()
        self.slot_index = slot_index
        self.image_path = image_path
        self.port = port
        self.quantity = quantity
        self.signals = PrintSignals()

    @Slot()
    def run(self) -> None:
        executable = shutil.which("niimblue-cli.cmd") or shutil.which("niimblue-cli")
        if executable is None:
            self.signals.failed.emit(self.slot_index,
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
            str(self.quantity),
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
            self.signals.failed.emit(self.slot_index, f"Druckprogramm konnte nicht gestartet werden: {exc}")
            return

        output = "\n".join(part for part in (result.stdout, result.stderr) if part).strip()
        if result.returncode == 0:
            self.signals.completed.emit(self.slot_index, result.returncode, output)
        else:
            self.signals.failed.emit(self.slot_index, output or f"Druck fehlgeschlagen (Exit-Code {result.returncode}).")


class RenderSignals(QObject):
    completed = Signal(int, int, str)
    failed = Signal(int, int, str)


class RenderTask(QRunnable):
    def __init__(self, generation: int, slot_index: int, source_path: Path, destination: Path) -> None:
        super().__init__()
        self.generation = generation
        self.slot_index = slot_index
        self.source_path = source_path
        self.destination = destination
        self.signals = RenderSignals()

    @Slot()
    def run(self) -> None:
        try:
            render_aml_to_png(self.source_path, self.destination)
        except AmlError as exc:
            self.signals.failed.emit(self.generation, self.slot_index, str(exc))
        except Exception as exc:  # Keep unexpected parser errors visible in the GUI.
            self.signals.failed.emit(self.generation, self.slot_index, f"AML-Verarbeitung fehlgeschlagen: {exc}")
        else:
            self.signals.completed.emit(self.generation, self.slot_index, str(self.destination))


class DropArea(QLabel):
    files_dropped = Signal(list)

    def __init__(self) -> None:
        super().__init__("Bis zu 24 PNG-, AML- oder ZIP-Dateien hier ablegen")
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(QSize(520, 70))
        self.setAcceptDrops(True)
        self.setObjectName("dropArea")

    def dragEnterEvent(self, event) -> None:
        paths = [Path(url.toLocalFile()) for url in event.mimeData().urls()]
        if 0 < len(paths) <= 24 and all(path.suffix.lower() in {".png", ".aml", ".zip"} for path in paths):
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        paths = [Path(url.toLocalFile()) for url in event.mimeData().urls()]
        if 0 < len(paths) <= 24 and all(path.suffix.lower() in {".png", ".aml", ".zip"} for path in paths):
            self.files_dropped.emit(paths)
            event.acceptProposedAction()


class PreviewLabel(QLabel):
    def __init__(self) -> None:
        super().__init__("Noch kein Label ausgewählt")
        self._source_pixmap = QPixmap()
        self._padding = 18
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumHeight(150)
        self.setStyleSheet("background: white; border: 1px solid #d2d9df; border-radius: 4px;")

    def set_source_pixmap(self, pixmap: QPixmap) -> None:
        self._source_pixmap = pixmap
        self._source_pixmap.setDevicePixelRatio(1.0)
        self._refresh_pixmap()

    def set_padding(self, padding: int) -> None:
        self._padding = padding
        self._refresh_pixmap()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._refresh_pixmap()

    def _refresh_pixmap(self) -> None:
        if self._source_pixmap.isNull():
            return
        canvas_size = self.contentsRect().size()
        available = self.contentsRect().adjusted(self._padding, self._padding, -self._padding, -self._padding).size()
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


class PrintToggle(QCheckBox):
    def __init__(self) -> None:
        super().__init__()
        self.setFixedSize(28, 28)
        self.setCursor(Qt.PointingHandCursor)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        enabled = self.isEnabled()
        checked = self.isChecked()
        box = self.rect().adjusted(3, 3, -3, -3)
        if not enabled:
            fill = "#edf1f3"
            outline = "#b9c3ca"
        elif checked:
            fill = "#087f8c"
            outline = "#066a75"
        else:
            fill = "#ffffff"
            outline = "#52616b"

        painter.setBrush(fill)
        pen = painter.pen()
        pen.setColor(outline)
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawRoundedRect(box, 3, 3)

        if enabled and checked:
            pen.setColor("#ffffff")
            pen.setWidth(3)
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            painter.setPen(pen)
            painter.drawLine(9, 15, 13, 19)
            painter.drawLine(13, 19, 21, 10)
        painter.end()


class BatchSlot(QWidget):
    def __init__(self, index: int) -> None:
        super().__init__()
        self.index = index
        self.image_path: Path | None = None
        self.source_path: Path | None = None
        self.preview = PreviewLabel()
        self.preview.setMinimumSize(QSize(150, 58))
        self.preview.set_padding(4)
        self.preview.setText(f"Feld {index + 1}")
        self.enabled = PrintToggle()
        self.enabled.setToolTip("Label drucken")
        self.enabled.setChecked(False)
        self.enabled.setEnabled(False)

        layout = QGridLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(0)
        layout.addWidget(self.preview, 0, 0)
        layout.addWidget(self.enabled, 0, 0, alignment=Qt.AlignTop | Qt.AlignLeft)
        self.setObjectName("batchSlot")

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        preview_width = max(150, self.preview.width())
        preview_height = min(100, max(45, round(preview_width * 96 / 320)))
        self.preview.setFixedHeight(preview_height)

    def set_image(self, source_path: Path, image_path: Path, pixmap: QPixmap) -> None:
        self.source_path = source_path
        self.image_path = image_path
        self.preview.set_source_pixmap(pixmap)
        self.preview.setText("")
        self.enabled.setEnabled(True)
        self.enabled.setChecked(True)

    def clear(self) -> None:
        self.source_path = None
        self.image_path = None
        self.preview._source_pixmap = QPixmap()
        self.preview.clear()
        self.preview.setText(f"Feld {self.index + 1}")
        self.enabled.setChecked(False)
        self.enabled.setEnabled(False)
        self.preview.setFixedHeight(45)

    def is_ready(self) -> bool:
        return self.image_path is not None


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.settings = QSettings("Deinjo", "PrintMySpoolLabel")
        self.thread_pool = QThreadPool.globalInstance()
        self.render_pool = QThreadPool(self)
        self.render_pool.setMaxThreadCount(2)
        self.slots = [BatchSlot(index) for index in range(24)]
        self.render_generation = 0
        self.pending_renders = 0
        self.total_renders = 0
        self.print_queue: list[int] = []
        self.active_print_index: int | None = None
        self.print_port = ""
        self.print_quantity = 1
        self._import_tempdirs: list[tempfile.TemporaryDirectory] = []
        self._build_ui()
        for slot in self.slots:
            slot.enabled.toggled.connect(self._update_print_button)
        self._restore_settings()

    def _build_ui(self) -> None:
        self.setWindowTitle("PrintMySpoolLabel")
        self.resize(1120, 820)
        self.setAcceptDrops(True)
        self.setStyleSheet(
            """
            QMainWindow { background: #f4f6f8; }
            QGroupBox { font-weight: 600; border: 1px solid #d2d9df; border-radius: 6px; margin-top: 10px; padding: 12px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; color: #263746; }
             QLineEdit, QPlainTextEdit { background: white; border: 1px solid #c7d0d9; border-radius: 4px; padding: 6px; }
             QCheckBox { background: white; border: 1px solid #aeb8c2; border-radius: 2px; }
             #batchSlot { background: #ffffff; border: 1px solid #d2d9df; border-radius: 5px; }
            QPushButton { background: #087f8c; color: white; border: 0; border-radius: 4px; padding: 9px 18px; font-weight: 600; }
            QPushButton:hover { background: #066a75; }
            QPushButton:disabled { background: #aeb8c2; }
            #dropArea { background: white; border: 2px dashed #087f8c; border-radius: 8px; color: #52616b; font-size: 16px; }
            """
        )

        self.drop_area = DropArea()
        self.drop_area.files_dropped.connect(self._add_files)

        grid_box = QGroupBox("Label-Stapel (4 Spalten x 6 Zeilen)")
        grid_layout = QGridLayout(grid_box)
        grid_layout.setContentsMargins(4, 6, 4, 4)
        grid_layout.setSpacing(2)
        for index, slot in enumerate(self.slots):
            grid_layout.addWidget(slot, index // 4, index % 4)

        self.clear_button = QPushButton("Alles löschen")
        self.clear_button.clicked.connect(self._clear_all)
        self.port_edit = QLineEdit(DEFAULT_PORT)
        self.quantity_edit = QSpinBox()
        self.quantity_edit.setRange(1, 99)
        self.quantity_edit.setSuffix(" Kopie(n)")
        self.print_button = QPushButton("Drucken")
        self.print_button.setEnabled(False)
        self.print_button.clicked.connect(self._print)

        settings_box = QGroupBox("Druckeinstellungen")
        settings_box.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)
        settings_form = QFormLayout(settings_box)
        settings_form.addRow("Serieller Port:", self.port_edit)
        settings_form.addRow("Anzahl Kopien:", self.quantity_edit)
        settings_form.addRow("Druckformat:", QLabel("40 × 12 mm / 320 × 96 Pixel / 203 dpi"))
        settings_form.addRow("Druckmodus:", QLabel("D110M_V4 / links / nicht gespiegelt"))

        log_box = QGroupBox("Status")
        log_box.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)
        log_layout = QVBoxLayout(log_box)
        self.status_label = QLabel("Bereit")
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(300)
        self.log.setMinimumHeight(105)
        self.log.setPlaceholderText("Druckdiagnose erscheint hier ...")
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.hide()
        log_layout.addWidget(self.status_label)
        log_layout.addWidget(self.progress)
        log_layout.addWidget(self.log)
        log_box.setMinimumHeight(170)

        buttons = QHBoxLayout()
        buttons.addWidget(self.clear_button)
        buttons.addStretch()
        buttons.addWidget(self.print_button)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addWidget(self.drop_area)
        layout.addWidget(grid_box, 1)

        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(8)
        bottom_layout.addWidget(log_box, 2)
        bottom_layout.addWidget(settings_box, 1)
        bottom_layout.setStretch(0, 2)
        bottom_layout.setStretch(1, 1)
        layout.addLayout(bottom_layout)
        layout.addLayout(buttons)
        self.setCentralWidget(central)

    def _restore_settings(self) -> None:
        self.port_edit.setText(str(self.settings.value("printer/port", DEFAULT_PORT)))
        self.quantity_edit.setValue(int(self.settings.value("printer/quantity", 1)))

    def _extract_zip(self, archive_path: Path) -> list[Path]:
        tempdir = tempfile.TemporaryDirectory(prefix="PrintMySpoolLabel-")
        extracted: list[Path] = []
        root = Path(tempdir.name).resolve()
        try:
            with zipfile.ZipFile(archive_path) as archive:
                for member in archive.infolist():
                    if member.is_dir() or Path(member.filename).suffix.lower() not in {".png", ".aml"}:
                        continue
                    if stat.S_ISLNK(member.external_attr >> 16):
                        continue

                    relative = PurePosixPath(member.filename.replace("\\", "/"))
                    if relative.is_absolute() or ".." in relative.parts:
                        continue
                    target = (root / Path(*relative.parts)).resolve()
                    try:
                        target.relative_to(root)
                    except ValueError:
                        continue
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(member) as source, target.open("wb") as destination:
                        shutil.copyfileobj(source, destination)
                    extracted.append(target)
        except (OSError, zipfile.BadZipFile) as exc:
            tempdir.cleanup()
            self.log.appendPlainText(f"ZIP konnte nicht verarbeitet werden ({archive_path.name}): {exc}")
            return []

        if not extracted:
            tempdir.cleanup()
            self.log.appendPlainText(f"Keine PNG- oder AML-Dateien in {archive_path.name} gefunden.")
            return []
        self._import_tempdirs.append(tempdir)
        return extracted

    def _expand_import_paths(self, paths: list[Path]) -> list[Path]:
        expanded: list[Path] = []
        for path in paths:
            if path.suffix.lower() == ".zip":
                expanded.extend(self._extract_zip(path))
            elif path.suffix.lower() in {".png", ".aml"}:
                expanded.append(path)
        return expanded

    @Slot(list)
    def _add_files(self, paths: list[Path]) -> None:
        self.log.clear()
        free_indices = [index for index, slot in enumerate(self.slots) if not slot.is_ready() and slot.source_path is None]
        valid_paths = [path for path in self._expand_import_paths(paths) if path.is_file()]
        if len(valid_paths) > len(free_indices):
            self.status_label.setText(f"Nur {len(free_indices)} freie Rasterfelder verfuegbar")
            valid_paths = valid_paths[: len(free_indices)]
        if not valid_paths:
            return

        self.total_renders = sum(path.suffix.lower() == ".aml" for path in valid_paths)
        self.pending_renders = self.total_renders
        if self.total_renders:
            self.progress.show()
            self.status_label.setText(f"Verarbeite {self.total_renders} AML-Datei(en) ...")

        for index, path in zip(free_indices, valid_paths):
            slot = self.slots[index]
            slot.source_path = path
            if path.suffix.lower() == ".aml":
                rendered_path = Path(tempfile.gettempdir()) / "PrintMySpoolLabel" / f"{path.stem}-{index}-40x12.png"
                rendered_path.parent.mkdir(parents=True, exist_ok=True)
                task = RenderTask(self.render_generation, index, path, rendered_path)
                task.signals.completed.connect(self._aml_render_completed)
                task.signals.failed.connect(self._aml_render_failed)
                self.render_pool.start(task)
            else:
                self._set_slot_image(index, path, path)
        if self.total_renders == 0:
            self.status_label.setText("Label-Stapel bereit")
        self._update_print_button()

    def _set_slot_image(self, index: int, source_path: Path, rendered_path: Path) -> None:
        pixmap = QPixmap(str(rendered_path))
        if pixmap.isNull():
            QMessageBox.warning(self, "Ungültige Datei", "Die PNG-Datei konnte nicht geladen werden.")
            return
        self.slots[index].set_image(source_path, rendered_path, pixmap)

    @Slot(int, int, str)
    def _aml_render_completed(self, generation: int, index: int, rendered_path: str) -> None:
        if generation != self.render_generation:
            return
        source_path = self.slots[index].source_path
        if source_path is not None:
            self._set_slot_image(index, source_path, Path(rendered_path))
        self.pending_renders -= 1
        self._finish_rendering_if_done()

    @Slot(int, int, str)
    def _aml_render_failed(self, generation: int, index: int, message: str) -> None:
        if generation != self.render_generation:
            return
        self.slots[index].clear()
        self.pending_renders -= 1
        self.log.appendPlainText(message)
        self._finish_rendering_if_done()

    def _finish_rendering_if_done(self) -> None:
        if self.pending_renders > 0:
            return
        self.progress.hide()
        self.status_label.setText("Label-Stapel bereit")
        self._update_print_button()

    @Slot()
    def _clear_all(self) -> None:
        self.render_generation += 1
        self.pending_renders = 0
        self.total_renders = 0
        self.progress.hide()
        for slot in self.slots:
            slot.clear()
        self.log.clear()
        self.status_label.setText("Bereit")
        self._update_print_button()

    def _update_print_button(self) -> None:
        self.print_button.setEnabled(
            self.pending_renders == 0
            and any(slot.is_ready() and slot.enabled.isChecked() for slot in self.slots)
        )

    @Slot()
    def _print(self) -> None:
        selected = [index for index, slot in enumerate(self.slots) if slot.is_ready() and slot.enabled.isChecked()]
        if not selected:
            return
        port = self.port_edit.text().strip()
        if not port:
            QMessageBox.warning(self, "Port fehlt", "Bitte einen seriellen Port angeben.")
            return

        self.settings.setValue("printer/port", port)
        quantity = self.quantity_edit.value()
        self.settings.setValue("printer/quantity", quantity)
        self.print_queue = selected
        self.active_print_index = None
        self.print_port = port
        self.print_quantity = quantity
        self.print_button.setEnabled(False)
        self.clear_button.setEnabled(False)
        self.status_label.setText(f"Druck läuft über {port} ...")
        self.log.clear()
        self._start_next_print(port, quantity)

    def _start_next_print(self, port: str, quantity: int) -> None:
        if not self.print_queue:
            self.active_print_index = None
            self.status_label.setText("Batch-Druck erfolgreich abgeschlossen")
            self.clear_button.setEnabled(True)
            self._update_print_button()
            return
        index = self.print_queue.pop(0)
        self.active_print_index = index
        image_path = self.slots[index].image_path
        if image_path is None:
            self._start_next_print(port, quantity)
            return
        task = PrintTask(index, image_path, port, quantity)
        task.signals.completed.connect(self._print_completed)
        task.signals.failed.connect(self._print_failed)
        self.thread_pool.start(task)

    @Slot(int, int, str)
    def _print_completed(self, index: int, _returncode: int, output: str) -> None:
        self.slots[index].enabled.setChecked(False)
        if output:
            self.log.appendPlainText(f"{self.slots[index].source_path.name}:\n{output}")
        self.status_label.setText(f"Label {index + 1} gedruckt, verbleibend: {len(self.print_queue)}")
        self._start_next_print(self.print_port, self.print_quantity)

    @Slot(int, str)
    def _print_failed(self, _index: int, message: str) -> None:
        self.print_button.setEnabled(True)
        self.clear_button.setEnabled(True)
        self.status_label.setText("Druck fehlgeschlagen")
        self.log.setPlainText(message)
        QMessageBox.warning(self, "Druckfehler", message)

    def closeEvent(self, event) -> None:
        self.settings.setValue("printer/port", self.port_edit.text().strip())
        self.settings.setValue("printer/quantity", self.quantity_edit.value())
        self.render_generation += 1
        self.render_pool.waitForDone(3000)
        self.thread_pool.waitForDone(3000)
        for tempdir in self._import_tempdirs:
            tempdir.cleanup()
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
