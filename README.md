# IP Camera Player Using Python
This Python project implements an IP Camera Player using PyQt5 and OpenCV. It allows users to view real-time video streams from IP cameras via RTSP, providing features such as zoom, pan, fullscreen toggle, and snapshot capture with timestamp. The app uses a threaded approach to manage video streaming, ensuring smooth UI performance. User settings, including camera configuration, are persisted across sessions. A loading animation is displayed during stream initialization. The application also includes basic error handling and status updates, ensuring the user is informed of any issues or stream progress during runtime

![image](https://github.com/user-attachments/assets/694a66ed-1295-4843-a4d2-433f7d49f619)

## Features

- **Real-time Video Streaming**: Connect to and stream from RTSP-enabled IP cameras
- **Camera Settings Management**: 
  - Easy configuration of camera connection parameters
  - Persistent storage of camera settings
  - Support for different video resolutions (1080p, 720p, 480p)
- **Video Controls**:
  - Start/Stop streaming
  - Pause/Resume stream
  - Take snapshots with timestamp
- **Advanced Viewing Features**:
  - Zoom in/out using mouse wheel
  - Pan the zoomed image by clicking and dragging
  - Double-click for fullscreen mode
- **User Interface**:
  - Clean and intuitive interface
  - Status bar with connection details
  - Loading animation during stream initialization

 ## Requirements

- Python 3.6+
- PyQt5
- OpenCV (cv2)
- NumPy

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/ip-camera-player.git
cd ip-camera-player
```

2. Install the required packages:
```bash
pip install -r requirements.txt
```

## Usage

1. Run the application:
```bash
python ip_camera_player.py
```
2. Configure your camera:
   - Click the "Settings" button
   - Enter your camera's details:
     - Protocol (e.g., rtsp)
     - Username
     - Password
     - IP Address
     - Port (default: 554 for RTSP)
     - Stream Path
     - Video Resolution

3. Control the stream:
   - Click "Start" to begin streaming
   - Use "Pause" to freeze the stream
   - Click "Stop" to end the stream
   - Use "Snapshot" to capture the current frame

4. Navigate the video:
   - Use the mouse wheel to zoom in/out
   - Click and drag to pan when zoomed in
   - Double-click for fullscreen mode

## Key Components

### Main Window (`Windows` class)
- Manages the main application window and UI components
- Handles video stream display and user interactions
- Manages camera settings and configuration persistence

### Camera Settings (`CameraSettings` class)
- Provides a dialog for configuring camera connection parameters
- Validates and saves camera settings
- Allows direct stream initiation from settings dialog

### Stream Thread (`StreamThread` class)
- Handles video stream capture in a separate thread
- Manages stream state (running, paused, stopped)
- Emits signals for frame updates and error conditions

### Loading Animation (`LoadingAnimation` class)
- Provides visual feedback during stream initialization
- Uses GIF animation for loading indicator

## Configuration

The application automatically saves the following settings:
- Protocol
- Username
- Password
- IP Address
- Port
- Stream Path
- Video Resolution

Settings are persisted between sessions using QSettings.

## Error Handling

The application includes comprehensive error handling for:
- Connection failures
- Stream initialization timeouts
- Invalid camera settings
- Frame capture errors

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- PyQt5 for the GUI framework
- OpenCV for video capture capabilities
- Contributors and testers who helped improve this application

## Version History

- 1.0.0 (Current)
  - Initial release
  - Basic streaming functionality
  - Camera settings management
  - Zoom and pan capabilities
  - Snapshot feature with timestamp

## Known Issues

- Stream initialization may take longer on some networks
- Some IP cameras might require specific stream paths
- Zoom performance may vary based on system capabilities

## Support

For support, please open an issue in the GitHub repository or contact the maintainers.

## Development Notes

For developers looking to modify or extend the application:

### Signal Flow
1. `StreamThread` captures frames and emits signals
2. Main window receives and processes frames
3. UI updates occur in the main thread
4. Error handling through dedicated signal channels

### Adding New Features
- Follow the existing error-handling patterns
- Use separate threads for long-running operations
- Maintain the MVC-like structure
- Add appropriate documentation

### Code Style
- Follow PEP 8 guidelines
- Use type hints for function parameters
- Document complex logic with inline comments
- Maintain consistent error-handling patterns
