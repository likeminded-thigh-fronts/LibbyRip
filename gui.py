#!/usr/bin/env python3
"""easym4b GUI - Convert Libby audiobooks to M4B format"""

import sys
import shutil
from pathlib import Path

from PyQt5 import QtWidgets, QtCore

from easym4b import (
    run_conversion,
    validate_input_directory,
    extract_zip_to_temp,
    resolve_ffmpeg,
    save_ffmpeg_path,
    _is_valid_ffmpeg,
)


class ConversionWorker(QtCore.QObject):
    progress = QtCore.pyqtSignal(str)
    finished = QtCore.pyqtSignal(object)  # emits output Path or None
    error = QtCore.pyqtSignal(str)

    def __init__(self, input_path, output_dir, author_dir=False, temp_dir=None, ffmpeg_path="ffmpeg"):
        super().__init__()
        self.input_path = input_path
        self.output_dir = output_dir
        self.author_dir = author_dir
        self.temp_dir = temp_dir
        self.ffmpeg_path = ffmpeg_path

    def run(self):
        try:
            result = run_conversion(
                input_path=self.input_path,
                output_dir=self.output_dir,
                author_dir=self.author_dir,
                overwrite=True,
                progress_callback=self.progress.emit,
                ffmpeg_path=self.ffmpeg_path,
            )
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))
            self.finished.emit(None)
        finally:
            if self.temp_dir is not None:
                self.progress.emit("Cleaning up extracted zip contents...")
                shutil.rmtree(self.temp_dir, ignore_errors=True)


class EasyM4BApp(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("easym4b - Libby to M4B Converter")
        self.resize(650, 450)
        self._thread = None
        self._worker = None
        self._ffmpeg_path = None
        self.init_ui()
        self._check_ffmpeg()

    def init_ui(self):
        layout = QtWidgets.QVBoxLayout()

        # Input selection
        input_label = QtWidgets.QLabel("Input (directory or .zip file):")
        input_layout = QtWidgets.QHBoxLayout()
        self.inputField = QtWidgets.QLineEdit()
        self.inputField.setPlaceholderText("Select audiobook directory or .zip file...")
        self.browseDirBtn = QtWidgets.QPushButton("Directory...")
        self.browseZipBtn = QtWidgets.QPushButton("Zip File...")
        input_layout.addWidget(self.inputField, 1)
        input_layout.addWidget(self.browseDirBtn)
        input_layout.addWidget(self.browseZipBtn)

        # Output directory selection
        output_label = QtWidgets.QLabel("Output directory:")
        output_layout = QtWidgets.QHBoxLayout()
        self.outputField = QtWidgets.QLineEdit()
        self.outputField.setPlaceholderText("Output directory (defaults to input directory)")
        self.browseOutputBtn = QtWidgets.QPushButton("Browse...")
        output_layout.addWidget(self.outputField, 1)
        output_layout.addWidget(self.browseOutputBtn)

        # Author dir checkbox
        self.authorDirCheck = QtWidgets.QCheckBox("Create author subdirectory")

        # FFmpeg path (shown only when not auto-detected)
        self.ffmpegLabel = QtWidgets.QLabel("FFmpeg binary:")
        ffmpeg_layout = QtWidgets.QHBoxLayout()
        self.ffmpegField = QtWidgets.QLineEdit()
        self.ffmpegField.setPlaceholderText("Path to ffmpeg binary...")
        self.browseFfmpegBtn = QtWidgets.QPushButton("Browse...")
        ffmpeg_layout.addWidget(self.ffmpegField, 1)
        ffmpeg_layout.addWidget(self.browseFfmpegBtn)
        self.ffmpegContainer = QtWidgets.QWidget()
        ffmpeg_container_layout = QtWidgets.QVBoxLayout()
        ffmpeg_container_layout.setContentsMargins(0, 0, 0, 0)
        ffmpeg_container_layout.addWidget(self.ffmpegLabel)
        ffmpeg_container_layout.addLayout(ffmpeg_layout)
        self.ffmpegContainer.setLayout(ffmpeg_container_layout)
        self.ffmpegContainer.setVisible(False)

        # Convert button
        self.convertBtn = QtWidgets.QPushButton("Convert to M4B")
        self.convertBtn.setMinimumHeight(40)

        # Log output
        self.logOutput = QtWidgets.QTextEdit()
        self.logOutput.setReadOnly(True)

        layout.addWidget(input_label)
        layout.addLayout(input_layout)
        layout.addSpacing(8)
        layout.addWidget(output_label)
        layout.addLayout(output_layout)
        layout.addWidget(self.authorDirCheck)
        layout.addSpacing(8)
        layout.addWidget(self.ffmpegContainer)
        layout.addSpacing(8)
        layout.addWidget(self.convertBtn)
        layout.addWidget(self.logOutput, 1)
        self.setLayout(layout)

        # Connect signals
        self.browseDirBtn.clicked.connect(self.select_input_dir)
        self.browseZipBtn.clicked.connect(self.select_zip_file)
        self.browseOutputBtn.clicked.connect(self.select_output_dir)
        self.convertBtn.clicked.connect(self.start_conversion)
        self.browseFfmpegBtn.clicked.connect(self.select_ffmpeg)
        self.ffmpegField.editingFinished.connect(self._on_ffmpeg_field_changed)

    def select_input_dir(self):
        dir_path = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Select Audiobook Directory"
        )
        if dir_path:
            self.inputField.setText(dir_path)

    def select_zip_file(self):
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select Audiobook Zip File", "", "Zip Files (*.zip)"
        )
        if file_path:
            self.inputField.setText(file_path)

    def select_output_dir(self):
        dir_path = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Select Output Directory"
        )
        if dir_path:
            self.outputField.setText(dir_path)

    def _check_ffmpeg(self):
        """Check for ffmpeg on startup."""
        path = resolve_ffmpeg()
        if path:
            self._ffmpeg_path = path
            self.ffmpegContainer.setVisible(False)
            self.convertBtn.setEnabled(True)
        else:
            self._ffmpeg_path = None
            self.ffmpegContainer.setVisible(True)
            self.convertBtn.setEnabled(False)
            self.logOutput.append(
                "<span style='color:orange;'>FFmpeg not found in PATH. "
                "Please set the path to ffmpeg below.</span>"
            )

    def select_ffmpeg(self):
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select FFmpeg Binary"
        )
        if file_path:
            self.ffmpegField.setText(file_path)
            self._validate_and_save_ffmpeg(file_path)

    def _on_ffmpeg_field_changed(self):
        path = self.ffmpegField.text().strip()
        if path:
            self._validate_and_save_ffmpeg(path)

    def _validate_and_save_ffmpeg(self, path):
        if _is_valid_ffmpeg(path):
            self._ffmpeg_path = path
            save_ffmpeg_path(path)
            self.convertBtn.setEnabled(True)
            self.logOutput.append(f"FFmpeg found: {path}")
        else:
            self._ffmpeg_path = None
            self.convertBtn.setEnabled(False)
            self.logOutput.append(
                f"<span style='color:red;'>Invalid ffmpeg path: {path}</span>"
            )

    def set_controls_enabled(self, enabled):
        self.convertBtn.setEnabled(enabled)
        self.browseDirBtn.setEnabled(enabled)
        self.browseZipBtn.setEnabled(enabled)
        self.browseOutputBtn.setEnabled(enabled)
        self.inputField.setEnabled(enabled)
        self.outputField.setEnabled(enabled)
        self.authorDirCheck.setEnabled(enabled)

    def start_conversion(self):
        input_text = self.inputField.text().strip()
        if not input_text:
            self.logOutput.append("<span style='color:red;'>Please select an input directory or zip file.</span>")
            return

        input_path = Path(input_text)
        if not input_path.exists():
            self.logOutput.append(f"<span style='color:red;'>Not found: {input_path}</span>")
            return

        self.logOutput.clear()
        self.set_controls_enabled(False)

        temp_dir = None
        try:
            # Handle zip input
            if input_path.suffix.lower() == '.zip':
                self.logOutput.append(f"Extracting zip file: {input_path.name}")
                extracted_path, temp_dir = extract_zip_to_temp(input_path)
                working_path = validate_input_directory(extracted_path)
            else:
                working_path = validate_input_directory(input_path)

            # Determine output dir
            output_text = self.outputField.text().strip()
            if output_text:
                output_dir = Path(output_text)
            elif temp_dir is not None:
                # Zip input with no output dir: default to cwd
                output_dir = Path.cwd()
            else:
                output_dir = None  # run_conversion defaults to input_path

        except (FileNotFoundError, RuntimeError) as e:
            self.logOutput.append(f"<span style='color:red;'>{e}</span>")
            self.set_controls_enabled(True)
            if temp_dir is not None:
                shutil.rmtree(temp_dir, ignore_errors=True)
            return

        # Launch worker thread
        self._thread = QtCore.QThread()
        self._worker = ConversionWorker(
            input_path=working_path,
            output_dir=output_dir,
            author_dir=self.authorDirCheck.isChecked(),
            temp_dir=temp_dir,
            ffmpeg_path=self._ffmpeg_path,
        )
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self.on_progress)
        self._worker.error.connect(self.on_error)
        self._worker.finished.connect(self.on_finished)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def on_progress(self, message):
        self.logOutput.append(message)

    def on_error(self, error_message):
        self.logOutput.append(f"<span style='color:red;'>Error: {error_message}</span>")

    def on_finished(self, result):
        if result:
            self.logOutput.append(f"\nDone!")
        self.set_controls_enabled(True)


def main():
    app = QtWidgets.QApplication(sys.argv)
    window = EasyM4BApp()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
