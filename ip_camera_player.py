"""
IP Camera Player Application

This module implements a GUI-based IP camera player using PyQt5 and OpenCV. It provides
functionality to view RTSP streams from IP cameras with features like zoom, pan, and snapshot
capabilities.

Key Features:
    - Real-time video streaming from IP cameras
    - Camera settings management with persistence
    - Video controls (start, stop, pause)
    - Advanced viewing features (zoom, pan, fullscreen)
    - Snapshot capture with timestamp

Author: Yamil Garcia
Version: 1.0.0
"""

from PyQt5.QtWidgets import (QApplication, QMainWindow, QLabel, QPushButton,
                             QHBoxLayout, QVBoxLayout, QWidget, QFileDialog,
                             QLineEdit, QDialog, QComboBox, QStatusBar, QMessageBox)
from PyQt5.QtCore import (Qt, QThread, pyqtSignal, QPoint, QMutex, QMutexLocker,
                          QSettings)
from PyQt5.QtGui import (QImage, QPixmap, QCloseEvent, QIcon, QMovie,
                         QWheelEvent, QMouseEvent)

import sys
import cv2
import time
import numpy as np
from typing import Tuple, Dict
import os
from os import path
from datetime import datetime
import threading

SW_VERSION = '1.0.0'
CAMERA_OPENING_TIMEOUT_SECONDS = 20


# LoadingAnimation class to manage the GIF
class LoadingAnimation:
    """
    A class to manage loading animation GIF display.

    This class handles the creation and control of a loading animation overlay
    that is displayed during stream initialization.

    Attributes:
        parent: Parent widget where the animation will be displayed
        label (QLabel): Label widget that contains the animation
        movie (QMovie): QMovie instance that plays the GIF animation
    """
    def __init__(self, parent, gif_path: str, size: Tuple[int, int]):
        """
        Initialize the LoadingAnimation instance.

        Args:
            parent: Parent widget where the animation will be displayed
            gif_path: Path to the GIF file
            size: Tuple of (width, height) for the animation size
        """
        self.parent = parent

        # QLabel to display the GIF
        self.label = QLabel(parent)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setContentsMargins(0, 0, 0, 0)

        # Load the GIF using QMovie
        file_name = os.path.dirname(os.path.realpath(__file__)) + gif_path
        if path.exists(file_name):
            self.movie = QMovie(file_name)

        # Set the movie to the QLabel
        self.label.setMovie(self.movie)

        # Set the size of the gif.
        width, height = size  # unpack the Tuple
        self.label.setFixedSize(width, height)

    def start(self):
        """Start the GIF animation"""
        # Position the GIF in the center of the Parent.
        x = int(self.parent.width() / 2) - int(self.label.width() / 2)
        y = int(self.parent.height() / 2) - int(self.label.height() / 2)
        self.label.setGeometry(x, y, self.label.width(), self.label.height())
        # Start the GIF animation
        self.movie.start()
        # Show the QLabel showing the GIF
        self.label.show()

    def stop(self):
        """Stop the GIF animation"""
        self.movie.stop()  # Stop the GIF animation
        self.label.hide()  # Hide the QLabel showing the GIF


class StreamThread(QThread):
    """
    Thread class for handling video stream capture.

    This class manages the camera connection and frame capture in a separate thread
    to prevent UI blocking. It emits signals for frame updates and error conditions.

    Signals:
        frame_received: Emitted when a new frame is captured
        first_frame_received: Emitted when the first frame is captured
        error_signal: Emitted when an error occurs
        status_signal: Emitted to update status messages
    """

    # Signal use to send the frame to the main thread (ui)
    frame_received = pyqtSignal(np.ndarray)
    # Signal used to notify that the first frame was received.
    first_frame_received = pyqtSignal()
    # Signal to send error messages to the UI thread.
    error_signal = pyqtSignal(str)
    # Signal to send status messages to the UI thread.
    status_signal = pyqtSignal(str)

    def __init__(self, url: str, video_res: Tuple[int, int] = (1920, 1080)) -> None:
        """
        Initialize the StreamThread instance.

        Args:
            url: RTSP URL for the camera stream
            video_res: Desired video resolution as (width, height)
        """
        super().__init__()

        # Class fields
        self.__url = url
        self.__cap = None
        self.__stream_is_running = False
        self.__stream_is_paused = False
        self.__video_resolution = video_res
        self.__first_frame_was_received = False
        self.__resize_frame = False
        self.__timeout = CAMERA_OPENING_TIMEOUT_SECONDS

    def run(self) -> None:
        """
       Main thread execution method for capturing video frames.

       This method handles the camera initialization and continuous frame capture.
       It emits signals for frames and various status updates.
       """

        # Start camera initialization in a separate thread
        init_thread = threading.Thread(target=self.initialize_camera)
        init_thread.start()

        # Wait for the thread to complete or timeout
        init_thread.join(self.__timeout)

        # If the thread is still alive after the timeout, handle it as a failure
        if init_thread.is_alive():
            self.error_signal.emit("Failed to open camera stream: Operation timed out.")
            self.stop_streaming()
            return

        # If camera initialization failed, stop the thread
        if not self.__cap or not self.__cap.isOpened():
            # self.error_signal.emit(f"Failed to open camera stream: {self.__url}")
            self.error_signal.emit(f"Failed to open camera stream")
            self.stop_streaming()
            return

        # Reduce buffer size for low latency
        self.__cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        # Get the stream width and height
        frame_width = self.__cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        frame_height = self.__cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        print(f'camera resolution: {frame_width, frame_height}')

        # Get the desired frame width and height
        desired_frame_width, desired_frame_height = self.__video_resolution
        print(f'requested camera resolution: {self.__video_resolution}')

        # Decide if we have to resize the frame
        if desired_frame_width != frame_width or desired_frame_height != frame_height:
            self.__resize_frame = True
            print('Resizing frames')

        while self.__stream_is_running:
            if self.__cap and self.__cap.isOpened():
                if not self.__stream_is_paused:  # to pause the streaming
                    # Read the camera frame and check for errors.
                    ret, frame = self.__cap.read()
                    if not ret:
                        self.error_signal.emit("Error reading frame. Stopping the video stream.")
                        break

                    # Resize frame for faster processing
                    if self.__resize_frame:
                        frame = cv2.resize(frame, self.__video_resolution)

                    # Emit a signal carrying the frame.
                    self.frame_received.emit(frame)

                    # Notify when the first frame was received.
                    if not self.__first_frame_was_received:
                        self.status_signal.emit('Streaming started')
                        # print('Streaming started')
                        self.first_frame_received.emit()
                        self.__first_frame_was_received = True
            else:
                time.sleep(0.01)  # Sleep briefly to avoid busy-waiting
        # self.stop_streaming()

    def initialize_camera(self):
        """Camera initialization logic that runs in a separate thread"""
        self.__cap = cv2.VideoCapture(self.__url)

    def start_streaming(self, url: str, res: Tuple[int, int]) -> None:
        if not self.__stream_is_running:
            self.__url = url
            self.__video_resolution = res
            self.__stream_is_running = True
            self.__stream_is_paused = False
            self.start()  # Begins execution of the thread by calling run()
            self.status_signal.emit('Starting streaming')
        self.__first_frame_was_received = False

    def stop_streaming(self) -> None:
        self.status_signal.emit('Stopping streaming')
        self.__stream_is_running = False
        # Terminate the thread.
        self.quit()
        self.wait()
        # Release resources
        if self.__cap is not None:
            self.__cap.release()
            self.__cap = None

    def pause_streaming(self, pause: bool) -> None:
        if pause:
            self.__stream_is_paused = True
            self.status_signal.emit('Streaming paused')
        else:
            self.__stream_is_paused = False
            self.status_signal.emit('Streaming playing')

    def set_url(self, url: str) -> None:
        self.__url = url

    def get_url(self) -> str:
        return self.__url

    def set_resolution(self, res: Tuple[int, int]) -> None:
        self.__video_resolution = res

    def get_resolution(self) -> Tuple[int, int]:
        return self.__video_resolution


class CameraSettings(QDialog):
    """
    Dialog for configuring camera connection settings.

    This class provides a dialog interface for users to input and modify
    camera connection parameters.

    Signals:
        camera_settings_closed: Emitted when settings are saved
        camera_settings_start: Emitted when start streaming is requested
    """

    # Signal emitted when this dialog is closed.
    camera_settings_closed = pyqtSignal(dict)
    # Signal emitted when this dialog is closed.
    camera_settings_start = pyqtSignal(dict)

    def __init__(self, parent=None):
        """
        Initialize the CameraSettings dialog.

        Args:
            parent: Parent widget for this dialog
        """

        super().__init__(parent)

        self.camera_settings_start_signal_emitted: bool = False

        self.protocol_line_edit = QLineEdit(self)
        self.protocol_line_edit.setPlaceholderText('Enter protocol')
        self.protocol_line_edit.setText(parent.protocol)

        self.user_line_edit = QLineEdit(self)
        self.user_line_edit.setPlaceholderText('Enter user name')
        self.user_line_edit.setText(parent.user)

        self.password_line_edit = QLineEdit(self)
        self.password_line_edit.setPlaceholderText('Enter password')
        self.password_line_edit.setEchoMode(QLineEdit.Password)  # Set the QLineEdit to mask input like a password
        self.password_line_edit.setText(parent.password)

        self.ip_line_edit = QLineEdit(self)
        self.ip_line_edit.setPlaceholderText('Enter camera ip address')
        self.ip_line_edit.setText(parent.ip)

        self.port_line_edit = QLineEdit(self)
        self.port_line_edit.setPlaceholderText('Enter camera port number')
        self.port_line_edit.setText(str(parent.port))

        self.stream_path_line_edit = QLineEdit(self)
        self.stream_path_line_edit.setPlaceholderText('Enter stream path')
        self.stream_path_line_edit.setText(parent.stream_path)

        self.video_res_combo_box = QComboBox(self)
        video_res = ['1080p', '720p', '480p']
        self.video_res_combo_box.addItems(video_res)
        if parent.video_resolution == (1920, 1080):
            self.video_res_combo_box.setCurrentIndex(0)
        elif parent.video_resolution == (1280, 720):
            self.video_res_combo_box.setCurrentIndex(1)
        elif parent.video_resolution == (640, 480):
            self.video_res_combo_box.setCurrentIndex(2)
        else:
            self.video_res_combo_box.setCurrentIndex(0)

        self.close_button = QPushButton("Close", self)
        self.close_button.clicked.connect(self.close)

        self.start_button = QPushButton("Start", self)
        self.start_button.setToolTip('Open and start streaming the camera')
        self.start_button.clicked.connect(self.start)

        self.init_gui()

    def init_gui(self):
        #
        layout_vertical_1 = QVBoxLayout()
        layout_vertical_1.addWidget(QLabel("Protocol"))
        layout_vertical_1.addWidget(QLabel("User Name"))
        layout_vertical_1.addWidget(QLabel("Password"))
        layout_vertical_1.addWidget(QLabel("IP Address"))
        layout_vertical_1.addWidget(QLabel("Port Number"))
        layout_vertical_1.addWidget(QLabel("Stream Path"))
        layout_vertical_1.addWidget(QLabel("Video Resolution"))

        #
        layout_vertical_2 = QVBoxLayout()
        layout_vertical_2.addWidget(self.protocol_line_edit)
        layout_vertical_2.addWidget(self.user_line_edit)
        layout_vertical_2.addWidget(self.password_line_edit)
        layout_vertical_2.addWidget(self.ip_line_edit)
        layout_vertical_2.addWidget(self.port_line_edit)
        layout_vertical_2.addWidget(self.stream_path_line_edit)
        layout_vertical_2.addWidget(self.video_res_combo_box)

        #
        layout_horizontal_1 = QHBoxLayout()
        layout_horizontal_1.addLayout(layout_vertical_1)
        layout_horizontal_1.addLayout(layout_vertical_2)

        #
        layout_horizontal_2 = QHBoxLayout()
        layout_horizontal_2.addWidget(self.start_button)
        layout_horizontal_2.addStretch(1)
        layout_horizontal_2.addWidget(self.close_button)

        #
        layout_vertical_3 = QVBoxLayout()
        layout_vertical_3.addLayout(layout_horizontal_1)
        layout_vertical_3.addLayout(layout_horizontal_2)

        # Set up setting window
        self.setLayout(layout_vertical_3)
        self.setWindowTitle('Camera Settings')
        self.setFixedSize(400, 220)

    def start(self) -> None:
        # Create a dictionary with the camera settings
        data: Dict[str, str] = {
            "Protocol": self.protocol_line_edit.text(),
            "User Name": self.user_line_edit.text(),
            "Password": self.password_line_edit.text(),
            "IP Address": self.ip_line_edit.text(),
            "Port Number": self.port_line_edit.text(),
            "Stream Path": self.stream_path_line_edit.text(),
            "Video Resolution": self.video_res_combo_box.currentText()
        }
        # Emit this signal with a dictionary
        self.camera_settings_start.emit(data)
        self.camera_settings_start_signal_emitted = True
        # Close this dialog
        self.close()

    # Overriding the closeEvent to capture when the dialog is closed
    def closeEvent(self, event: QCloseEvent) -> None:
        if not self.camera_settings_start_signal_emitted:
            # Create a dictionary with the camera settings
            data: Dict[str, str] = {
                "Protocol": self.protocol_line_edit.text(),
                "User Name": self.user_line_edit.text(),
                "Password": self.password_line_edit.text(),
                "IP Address": self.ip_line_edit.text(),
                "Port Number": self.port_line_edit.text(),
                "Stream Path": self.stream_path_line_edit.text(),
                "Video Resolution": self.video_res_combo_box.currentText()
            }
            # Emit signal with a dictionary
            self.camera_settings_closed.emit(data)
        event.accept()


class Windows(QMainWindow):
    """
    Main application window class.

    This class manages the main application window and coordinates all the
    functionality including video display, user interface, and camera control.

    Attributes:
        app_settings (QSettings): Application settings manager
        mutex (QMutex): Mutex for thread synchronization
        video_label (QLabel): Label for displaying video stream
        current_frame (np.ndarray): Current video frame
        zoom_factor (float): Current zoom level
        is_full_screen (bool): Fullscreen state flag
    """

    def __init__(self) -> None:
        """Initialize the main window and set up the user interface."""
        super(Windows, self).__init__()

        # Create an instance of the QSettings class to persist application data.
        self.app_settings = QSettings('IP Camera Player', 'AppSettings')

        # Create a mutex to access the shared resource (frame)
        self.mutex = QMutex()

        # Create a label in the status bar to show status messages.
        self.status_bar_message_label = QLabel()

        # Create a label in the status bar to show the camera url
        self.status_bar_url = QLabel()

        # Create a label in the status bar to show the camera resolution
        self.status_bar_resolution = QLabel()

        # Create a label to display the video stream
        self.video_label = QLabel(self)
        self.video_label.setContentsMargins(0, 0, 0, 0)
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setStyleSheet("background-color: black;")

        # Create a button to start streaming video from the camera.
        self.start_button = QPushButton("Start", self)
        self.start_button.clicked.connect(self.start_streaming)
        self.start_button.setEnabled(False)

        # Create a button to start streaming video from the camera.
        self.stop_button = QPushButton("Stop", self)
        self.stop_button.clicked.connect(self.stop_streaming)
        self.stop_button.setEnabled(False)

        # Create a button to pause the streaming from the camera.
        self.pause_button = QPushButton("Pause", self)
        self.pause_button.clicked.connect(self.pause_streaming)
        self.pause_button.setEnabled(False)

        # Create a button to take a snapshot.
        self.take_snapshot_button = QPushButton("Snapshot", self)
        self.take_snapshot_button.clicked.connect(self.take_snapshot)
        self.take_snapshot_button.setEnabled(False)

        # Create a button to set the camera settings.
        self.open_cam_settings_button = QPushButton("Settings", self)
        self.open_cam_settings_button.setToolTip('Set up camera settings: protocol, ip, port, etc')
        self.open_cam_settings_button.setEnabled(True)
        self.open_cam_settings_button.clicked.connect(self.open_camera_settings)

        # Read camera persisted settings if existed.
        self.protocol: str = self.app_settings.value('protocol', 'rtsp', type=str)
        self.user: str = self.app_settings.value('user', '', type=str)
        self.password: str = self.app_settings.value('password', '', type=str)
        self.ip: str = self.app_settings.value('ip', '', type=str)
        self.port: int = self.app_settings.value('port', 554, type=int)  # Default RTSP port
        self.stream_path: str = self.app_settings.value('stream_path', '', type=str)
        # Retrieve the tuple as a string
        video_resolution_str = self.app_settings.value('video_resolution', '', type=str)
        # Convert the string back to a tuple using eval
        if video_resolution_str:
            self.video_resolution: Tuple[int, int] = eval(video_resolution_str)
        else:
            self.video_resolution: Tuple[int, int] = (1920, 1080)

        # Variable for pausing
        self.is_running = False

        # Store the current frame for snapshot functionality
        self.current_frame = None

        # Store the zoom factor. Start with no zoom
        self.zoom_factor = 1.0

        # Variables for panning
        self.panning = False
        self.last_mouse_position = QPoint(0, 0)
        self.x_offset = 0
        self.y_offset = 0

        # Scaled image size (updated with zoom)
        self.scaled_width = 0
        self.scaled_height = 0

        # Variable to track full screen state
        self.is_full_screen = False

        # Initialize the GUI.
        self.init_gui()

        # variable to store the camera url
        self.url = ""

        if self.ip:
            # Construct the url.
            self.url = f"{self.protocol}://{self.user}:{self.password}@{self.ip}:{self.port}/{self.stream_path}"
            # Update the status bar
            hidden_password = self.replace_letters_with_asterisks(self.password)
            url_hidden_password = f" {self.protocol}://{self.user}:{hidden_password}@{self.ip}:{self.port}/{self.stream_path} "
            self.update_status_bar('Streaming stopped', url_hidden_password, f'{self.video_resolution}')
            # Enable the start button
            self.start_button.setEnabled(True)
        else:
            # Update the status bar
            self.update_status_bar('Streaming stopped', "none", "none")
            # Disable the start button
            self.start_button.setEnabled(False)

            # Create the loading animation
        self.loading_animation = LoadingAnimation(self,
                                                  "\\images\\Spinner-1s-104px.gif",
                                                  (104, 104))

        # Create an instance of the RTSPCameraStream class.
        self.rtspCameraStream = StreamThread(self.url, self.video_resolution)
        self.rtspCameraStream.first_frame_received.connect(self.setup_widgets_when_playing)
        self.rtspCameraStream.frame_received.connect(self.display_frame)
        self.rtspCameraStream.finished.connect(self.setup_widgets_when_stopped)
        self.rtspCameraStream.error_signal.connect(lambda error: self.error_streaming(error))
        self.rtspCameraStream.status_signal.connect(lambda status: self.streaming_status(status))

    def init_gui(self) -> None:
        """Initialize and set up the graphical user interface."""

        # Create a Horizontal layout
        layout_horizontal_1 = QHBoxLayout()
        layout_horizontal_1.addStretch(1)
        layout_horizontal_1.addWidget(self.open_cam_settings_button)
        layout_horizontal_1.addStretch(1)
        layout_horizontal_1.addWidget(self.start_button)
        layout_horizontal_1.addStretch(1)
        layout_horizontal_1.addWidget(self.pause_button)
        layout_horizontal_1.addStretch(1)
        layout_horizontal_1.addWidget(self.take_snapshot_button)
        layout_horizontal_1.addStretch(1)
        layout_horizontal_1.addWidget(self.stop_button)
        layout_horizontal_1.addStretch(1)

        # Create a Vertical layout
        layout_vertical_1 = QVBoxLayout()
        layout_vertical_1.addWidget(self.video_label)
        layout_vertical_1.addLayout(layout_horizontal_1)

        #
        self.start_button.setFocus()

        # Set up the central widget
        container_widget = QWidget()
        container_widget.setLayout(layout_vertical_1)

        # Set up the windows settings.
        self.setCentralWidget(container_widget)
        self.setMinimumSize(720, 720)  # self.setMinimumSize(1280, 720)
        self.setWindowTitle("IP Camera Player")
        file_name = os.path.dirname(os.path.realpath(__file__)) + "\\images\\Security-Camera-icon.png"
        if path.exists(file_name):
            self.setWindowIcon(QIcon(file_name))
        self.setStatusBar(self.create_status_bar())

    def create_status_bar(self) -> QStatusBar:
        # Create an instance of the QHBoxLayout class
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 2, 0, 2)
        layout.addSpacing(5)
        layout.addWidget(self.status_bar_message_label)
        layout.addSpacing(5)
        layout.addWidget(self.status_bar_url)
        layout.addSpacing(5)
        layout.addWidget(self.status_bar_resolution)
        layout.addSpacing(5)

        # Create an instance of the QWidget class
        container = QWidget()
        container.setLayout(layout)

        # Create an instance of the QStatusBar class
        status_bar = QStatusBar()
        status_bar.addWidget(container)
        status_bar.addWidget(QLabel(''), stretch=20)
        status_bar.addWidget(QLabel(f' SW Rev: {SW_VERSION} '))

        return status_bar

    def update_status_bar(self, message: str, url: str, res: str) -> None:
        """
        Update the status bar with new information.

        Args:
            message: Status message to display
            url: Camera URL to display
            res: Resolution information to display
        """
        if message:
            self.status_bar_message_label.setText(f'Status: {message},')
        if url:
            self.status_bar_url.setText(f'Url: {url},')
        if res:
            self.status_bar_resolution.setText(f'Resolution: {res}')

    @staticmethod
    def replace_letters_with_asterisks(input_string: str) -> str:
        # Replace each letter with '*', keeping non-letters intact
        return ''.join('*' for char in input_string)

    def start_streaming(self) -> None:
        if self.rtspCameraStream and not self.rtspCameraStream.isRunning() and self.ip:
            # Initialize variables
            self.zoom_factor = 1.0
            self.panning = False
            self.last_mouse_position = QPoint(0, 0)
            self.x_offset = 0
            self.y_offset = 0
            self.scaled_width = 0
            self.scaled_height = 0
            # Set up the widgets.
            self.setup_widgets_when_starting()
            # start streaming the camera
            self.rtspCameraStream.start_streaming(self.url, self.video_resolution)
            # update this flag
            self.is_running = True

    def display_frame(self, frame: np.ndarray) -> None:
        if self.rtspCameraStream:
            # Store the frame for snapshot and zoom functionality
            self.current_frame = frame
            # Convert the frame to RGB format.
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            # Extract the height, width, and the number of channels.
            h, w, ch = frame.shape
            # Calculate bytes per line
            bytes_per_line = ch * w
            # Create an image in Qt format using the given frame.
            q_image = QImage(frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
            # Create a pixmap from image.
            pixmap = QPixmap.fromImage(q_image)

            # Apply zoom factor to the pixmap, converting dimensions to integers
            self.scaled_width = int(self.zoom_factor * w)
            self.scaled_height = int(self.zoom_factor * h)

            # Scale the pixmap with integer dimensions and keep the aspect ratio
            scaled_pixmap = pixmap.scaled(self.scaled_width, self.scaled_height, Qt.KeepAspectRatio)

            # Enforce boundary limits for panning (do not pan outside the image)
            self.x_offset = max(0, min(self.x_offset, self.scaled_width - self.video_label.width()))
            self.y_offset = max(0, min(self.y_offset, self.scaled_height - self.video_label.height()))

            # Create a sub-area based on panning
            visible_pixmap = scaled_pixmap.copy(self.x_offset, self.y_offset, self.video_label.width(),
                                                self.video_label.height())

            # Display the frame
            self.video_label.setPixmap(visible_pixmap)

    def stop_streaming(self) -> None:
        # if self.rtspCameraStream and self.rtspCameraStream.is_running:
        if self.rtspCameraStream and self.rtspCameraStream.isRunning():
            self.rtspCameraStream.stop_streaming()
            self.is_running = False
            self.start_button.setFocus()

    def pause_streaming(self) -> None:
        if self.rtspCameraStream and self.rtspCameraStream.isRunning():
            if self.is_running:
                self.pause_button.setText("Unpause")
                self.rtspCameraStream.pause_streaming(True)
                self.is_running = False
            else:
                self.pause_button.setText("Pause")
                self.rtspCameraStream.pause_streaming(False)
                self.is_running = True

    def error_streaming(self, error: str) -> None:

        self.show_message_box("Stream Error",
                              error,
                              QMessageBox.Critical)

        self.update_status_bar(error, "", "")
        print(error)

    def streaming_status(self, status: str) -> None:
        self.update_status_bar(status, "", "")
        print(status)

    def reset_video_label(self: 'Windows') -> None:
        """
        Reset the video label to a solid black background after clearing the video frame.
        """
        # Clear any existing pixmap
        self.video_label.clear()

        # Create a black QPixmap with the same size as the video label
        black_pixmap = QPixmap(self.video_label.size())
        black_pixmap.fill(Qt.black)

        # Set the black pixmap as the label's content
        self.video_label.setPixmap(black_pixmap)

        # Ensure the UI is updated immediately
        self.video_label.repaint()

    def set_video_label_to_gray(self: 'Windows') -> None:
        """
        Set the video label to a solid gray background after clearing the video frame.
        """
        # Clear any existing pixmap
        self.video_label.clear()

        # Create a black QPixmap with the same size as the video label
        black_pixmap = QPixmap(self.video_label.size())
        black_pixmap.fill(Qt.lightGray)

        # Set the black pixmap as the label's content
        self.video_label.setPixmap(black_pixmap)

        # Ensure the UI is updated immediately
        self.video_label.repaint()

    def enable_widgets(self, enable: bool) -> None:
        """
        Enable or disable all child widgets of a QMainWindow.

        This function iterates through all child widgets of the specified QMainWindow
        and sets their enabled state according to the 'enabled' parameter.

        Parameters:
        - enabled: bool. The state to set for the child widgets (True to enable, False to disable).

        Returns:
        None
        """
        for widget in self.findChildren(QWidget):
            if isinstance(widget, QWidget):  # Ensure it's a QWidget
                if enable:
                    widget.setEnabled(True)
                else:
                    widget.setEnabled(False)
        # Ensure the UI is updated immediately
        self.video_label.repaint()

    def setup_widgets_when_starting(self) -> None:
        # self.enable_widgets(False)  # disable all the widgets
        self.loading_animation.start()  # show the loading animation
        self.set_video_label_to_gray()
        self.open_cam_settings_button.setEnabled(False)
        self.start_button.setEnabled(False)
        self.pause_button.setEnabled(False)
        self.take_snapshot_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.pause_button.setText("Pause")
        print("Loading camera stream, please wait...")
        self.update_status_bar("Loading stream", "", "")

    def setup_widgets_when_playing(self) -> None:
        # self.enable_widgets(True)
        self.loading_animation.stop()  # hide the loading animation
        self.open_cam_settings_button.setEnabled(False)
        self.start_button.setEnabled(False)
        self.pause_button.setEnabled(True)
        self.take_snapshot_button.setEnabled(True)
        self.stop_button.setEnabled(True)
        self.stop_button.setFocus()
        print("Streaming running")
        self.update_status_bar("Streaming running", "", "")

    def setup_widgets_when_stopped(self) -> None:
        # self.enable_widgets(True)
        self.loading_animation.stop()  # stop the loading animation
        self.reset_video_label()
        self.open_cam_settings_button.setEnabled(True)
        self.start_button.setEnabled(True)
        self.pause_button.setEnabled(False)
        self.take_snapshot_button.setEnabled(False)
        self.stop_button.setEnabled(False)
        self.pause_button.setText("Pause")
        self.start_button.setFocus()
        print("Streaming has stopped")
        self.update_status_bar("Streaming stopped", "", "")

    def take_snapshot_old_ok(self) -> None:
        """
        Take a snapshot of the current frame and save it to a file.
        The user will input a custom file name, and the code will concatenate the current date and time.
        """

        # QMutexLocker automatically locks and unlocks the mutex
        # to access the shared resource (self.current_frame)
        # locker = QMutexLocker(self.mutex)
        QMutexLocker(self.mutex)

        try:
            if self.current_frame is not None:
                # Get the current date and time in the format MM/DD/YYYY and 12-hour time with AM/PM
                current_time = datetime.now().strftime("%m-%d-%Y_%I-%M-%S%p")

                # Prompt the user for a file name without extension
                options = QFileDialog.Options()
                file_path, _ = QFileDialog.getSaveFileName(self, "Save Snapshot", "",
                                                           "Images (*.png *.jpg *.jpeg);;All Files (*)",
                                                           options=options)

                if file_path:
                    # Extract the base name and the directory from the file path
                    base_name = os.path.splitext(os.path.basename(file_path))[0]
                    save_dir = os.path.dirname(file_path)

                    # Concatenate the user-provided name with the current date and time
                    final_file_name = f"{base_name}_{current_time}.png"
                    final_path = os.path.join(save_dir, final_file_name)

                    # Save the current frame to the selected file path
                    cv2.imwrite(final_path, self.current_frame)
                    print(f"Snapshot saved to {final_path}")

                else:
                    print("Save operation was canceled.")
            else:
                print("No frame available for snapshot")

        finally:
            # No need to manually unlock the mutex as QMutexLocker will do this automatically
            pass

    def take_snapshot(self) -> None:
        """
        Take a snapshot of the current visible portion of the frame (with zoom and panning applied)
        and save it to a file. The user will input a custom file name, and the code will concatenate
        the current date and time.
        """

        # pixmap = None

        # QMutexLocker automatically locks and unlocks the mutex
        # to access the shared resource (self.video_label)

        try:
            with QMutexLocker(self.mutex):
                # Ensure there is a pixmap in the QLabel before trying to save
                pixmap = self.video_label.pixmap()
        finally:
            # No need to manually unlock the mutex as QMutexLocker will do this automatically
            pass

        if pixmap is not None and not pixmap.isNull():
            try:
                # Get the currently visible pixmap (with zoom and panning applied)
                visible_pixmap = pixmap.copy()

                # Get the current date and time in the format MM/DD/YYYY and 12-hour time with AM/PM
                current_time = datetime.now().strftime("%m-%d-%Y_%I-%M-%S%p")

                # Prompt the user for a file name without extension
                options = QFileDialog.Options()
                file_path, _ = QFileDialog.getSaveFileName(self, "Save Snapshot", "",
                                                           "Images (*.png *.jpg *.jpeg);;All Files (*)",
                                                           options=options)

                if file_path:
                    # Extract the base name and the directory from the file path
                    base_name = os.path.splitext(os.path.basename(file_path))[0]
                    save_dir = os.path.dirname(file_path)

                    # Concatenate the user-provided name with the current date and time
                    final_file_name = f"{base_name}_{current_time}.png"
                    final_path = os.path.join(save_dir, final_file_name)

                    # Save the visible pixmap to the selected file path
                    if visible_pixmap.save(final_path, 'PNG'):
                        print(f"Snapshot saved to {final_path}")
                    else:
                        print("Failed to save snapshot.")
                else:
                    print("Save operation was canceled.")
            except Exception as e:
                print(f"An error occurred while saving the snapshot: {e}")
        else:
            print("No visible pixmap available for snapshot.")

    def open_camera_settings(self) -> None:
        # Create an instance of the CameraSettings class to enter the camera settings.
        camera_settings = CameraSettings(self)
        camera_settings.camera_settings_closed.connect(lambda settings: self.update_camera_settings(settings))
        camera_settings.camera_settings_start.connect(lambda settings: self.start_from_camera_settings(settings))
        camera_settings.exec_()  # show the camera settings dialog

    def update_camera_settings(self, camera_settings: dict) -> None:
        if camera_settings:  # if the dict is not empty
            # Update the camera settings
            self.protocol = camera_settings['Protocol']
            self.user = camera_settings['User Name']
            self.password = camera_settings['Password']
            self.ip = camera_settings['IP Address']
            self.port = int(camera_settings['Port Number'])
            self.stream_path = camera_settings['Stream Path']
            if camera_settings['Video Resolution'] == '1080p':
                self.video_resolution = (1920, 1080)
            elif camera_settings['Video Resolution'] == '720p':
                self.video_resolution = (1280, 720)
            elif camera_settings['Video Resolution'] == '480p':
                self.video_resolution = (640, 480)
            else:
                self.video_resolution = (1920, 1080)

            if self.ip:
                # Update the url.
                self.url = f"{self.protocol}://{self.user}:{self.password}@{self.ip}:{self.port}/{self.stream_path}"

                # Hide the password
                hidden_password = self.replace_letters_with_asterisks(self.password)

                # Update the url and the camera resolution in the status bar
                url_hidden_password = f' {self.protocol}://{self.user}:{hidden_password}@{self.ip}:{self.port}/{self.stream_path}'
                self.update_status_bar("", url_hidden_password, f'{self.video_resolution}')

                self.start_button.setEnabled(True)
            else:

                self.start_button.setEnabled(False)

                # code here for error
                pass

    def start_from_camera_settings(self, camera_settings: dict) -> None:
        if camera_settings:  # if the dict is not empty
            self.update_camera_settings(camera_settings)
            self.start_streaming()

    def show_message_box(self, title: str, message: str, icon: int) -> None:
        """
        Create a modal dialog to inform the user about something he needs to know.
        It can be an error, or an information, or a warning.
        :param title: Title for this dialog window.
        :param message: Message to shown to user.
        :param icon: Icon shown, must be: QMessageBox::NoIcon QMessageBox.Information, QMessageBox.Warning, QMessageBox.Critical
        :return: None
        """
        # Create an instance of the QMessageBox class to create a message window.
        msg_box = QMessageBox(self)
        msg_box.setIcon(icon)
        msg_box.setText(message)
        msg_box.setWindowTitle(title)
        msg_box.setStandardButtons(QMessageBox.Ok)
        # msg_box.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        # msg_box.buttonClicked.connect(msgButtonClick)
        return_value = msg_box.exec()
        if return_value == QMessageBox.Ok:
            pass

    def save_app_settings(self) -> None:
        # Save and persist the camera settings for next time
        self.app_settings.setValue('protocol', self.protocol)
        self.app_settings.setValue('user', self.user)
        self.app_settings.setValue('password', self.password)
        self.app_settings.setValue('ip', self.ip)
        self.app_settings.setValue('port', self.port)
        self.app_settings.setValue('stream_path', self.stream_path)
        # Convert tuple to string and persist it
        self.app_settings.setValue('video_resolution', str(self.video_resolution))

    def wheelEvent(self, event: QWheelEvent) -> None:
        """
        Handle mouse wheel events to zoom in and out on the video stream.
        """
        # Adjust the zoom factor based on the mouse wheel scrolling
        if event.angleDelta().y() > 0:
            self.zoom_factor *= 1.1  # Zoom in
        else:
            self.zoom_factor /= 1.1  # Zoom out

        # Ensure zoom factor stays within a reasonable range
        self.zoom_factor = max(0.1, min(self.zoom_factor, 10))

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """
        Start panning when the mouse is pressed.
        """
        if event.button() == Qt.LeftButton:
            self.panning = True
            self.last_mouse_position = event.pos()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """
        Handle mouse movement for panning.
        """
        if self.panning:
            delta = event.pos() - self.last_mouse_position
            self.last_mouse_position = event.pos()

            # Update the offset for panning
            self.x_offset = max(0, min(self.x_offset - delta.x(), self.scaled_width - self.video_label.width()))
            self.y_offset = max(0, min(self.y_offset - delta.y(), self.scaled_height - self.video_label.height()))

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """
        Stop panning when the mouse is released.
        """
        if event.button() == Qt.LeftButton:
            self.panning = False

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        """Toggle full screen mode on mouse double click"""
        if self.is_full_screen:
            self.showNormal()  # Exit full screen mode
        else:
            self.showFullScreen()  # Enter full screen mode

        self.is_full_screen = not self.is_full_screen  # Toggle the state

    def closeEvent(self, event: QCloseEvent) -> None:
        self.stop_streaming()
        if self.loading_animation:
            self.loading_animation.stop()
        if self.app_settings:
            self.save_app_settings()
        event.accept()


def main() -> None:
    """Main entry point for the application."""
    app = QApplication(sys.argv)
    window = Windows()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
