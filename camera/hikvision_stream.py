import cv2
import numpy as np
import threading
import time
import logging
import subprocess
import re
import os
import base64
from typing import Tuple, Optional, Dict, Any, List

logger = logging.getLogger(__name__)

class AdvancedRTSPProcessor:
    """
    Advanced RTSP stream processor that uses OpenCV with optimized settings
    for Hikvision cameras. Supports hardware acceleration, low latency mode,
    and different transport protocols.
    """
    
    def __init__(
        self, 
        rtsp_url: str,
        hardware_acceleration: bool = True,
        low_latency: bool = True,
        transport: str = 'tcp',
        buffer_size: int = 5,
        codec: str = 'auto',
        reconnect_attempts: int = 3,
        reconnect_delay: int = 2,
        frame_width: int = 1280,
        frame_height: int = 720,
        fps_target: int = 15
    ):
        """
        Initialize the RTSP processor with the given parameters.
        
        Args:
            rtsp_url: The RTSP URL to connect to
            hardware_acceleration: Whether to use hardware acceleration
            low_latency: Whether to use low latency mode
            transport: The transport protocol to use (tcp, udp)
            buffer_size: The buffer size to use
            codec: The codec to use (auto, h264, h265)
            reconnect_attempts: Number of reconnect attempts
            reconnect_delay: Delay between reconnect attempts
            frame_width: Target frame width
            frame_height: Target frame height
            fps_target: Target FPS
        """
        self.rtsp_url = rtsp_url
        self.hardware_acceleration = hardware_acceleration
        self.low_latency = low_latency
        self.transport = transport
        self.buffer_size = buffer_size
        self.codec = codec
        self.reconnect_attempts = reconnect_attempts
        self.reconnect_delay = reconnect_delay
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.fps_target = fps_target
        
        # Internal state
        self.cap = None
        self.running = False
        self.error = None
        self.last_frame = None
        self.last_frame_time = None
        self.hw_acceleration_info = "none"
        self.detected_codec = "unknown"
        
        # Thread for background processing
        self.thread = None
        self.stop_event = threading.Event()
        self.frame_lock = threading.Lock()
    
    def _build_capture_params(self) -> Dict[int, Any]:
        """
        Build the OpenCV capture parameters based on the configuration.
        
        Returns:
            Dict[int, Any]: Dictionary of OpenCV capture parameters
        """
        params = {}
        
        # Set transport protocol
        if self.transport == 'tcp':
            params[cv2.CAP_PROP_FOURCC] = cv2.VideoWriter_fourcc(*'H264')
            params[cv2.CAP_FFMPEG_RTSP_TRANSPORT] = cv2.CAP_FFMPEG_RTSP_TRANSPORT_TCP
        elif self.transport == 'udp':
            params[cv2.CAP_PROP_FOURCC] = cv2.VideoWriter_fourcc(*'H264')
            params[cv2.CAP_FFMPEG_RTSP_TRANSPORT] = cv2.CAP_FFMPEG_RTSP_TRANSPORT_UDP
        elif self.transport == 'http':
            params[cv2.CAP_PROP_FOURCC] = cv2.VideoWriter_fourcc(*'H264')
            params[cv2.CAP_FFMPEG_RTSP_TRANSPORT] = cv2.CAP_FFMPEG_RTSP_TRANSPORT_HTTP
        
        # Set buffer size
        params[cv2.CAP_PROP_BUFFERSIZE] = self.buffer_size
        
        # Set codec-specific options
        if self.codec == 'h265' or self.codec == 'hevc':
            # For H.265/HEVC, we need to use different settings
            params[cv2.CAP_PROP_FOURCC] = cv2.VideoWriter_fourcc(*'HEVC')
            self.detected_codec = "H.265/HEVC"
        else:
            # Default to H.264
            params[cv2.CAP_PROP_FOURCC] = cv2.VideoWriter_fourcc(*'H264')
            self.detected_codec = "H.264"
        
        # Hardware acceleration settings
        if self.hardware_acceleration:
            # Try different hardware acceleration backends
            # NVIDIA GPU (CUDA)
            params[cv2.CAP_PROP_HW_ACCELERATION] = cv2.VIDEO_ACCELERATION_ANY
            
            # Additional FFMPEG options for hardware acceleration
            ffmpeg_opts = []
            
            # Add hardware acceleration options based on codec
            if self.codec == 'h265' or self.codec == 'hevc':
                ffmpeg_opts.append("hwaccel=auto")
                ffmpeg_opts.append("hwaccel_device=0")
                ffmpeg_opts.append("c:v=hevc_cuvid")  # NVIDIA HEVC decoder
            else:
                ffmpeg_opts.append("hwaccel=auto")
                ffmpeg_opts.append("hwaccel_device=0")
                ffmpeg_opts.append("c:v=h264_cuvid")  # NVIDIA H.264 decoder
            
            # Low latency settings
            if self.low_latency:
                ffmpeg_opts.append("fflags=nobuffer")
                ffmpeg_opts.append("flags=low_delay")
                ffmpeg_opts.append("probesize=32")
                ffmpeg_opts.append("analyzeduration=0")
            
            # Set FFMPEG options
            if ffmpeg_opts:
                params[cv2.CAP_PROP_FFMPEG_OPTS] = '|'.join(ffmpeg_opts)
        
        return params
    
    def _detect_hardware_acceleration(self) -> str:
        """
        Detect which hardware acceleration is being used.
        
        Returns:
            str: Description of hardware acceleration being used
        """
        if not self.hardware_acceleration or not self.cap:
            return "none"
        
        # Try to get hardware acceleration info from OpenCV
        hw_accel = self.cap.get(cv2.CAP_PROP_HW_ACCELERATION)
        
        if hw_accel == cv2.VIDEO_ACCELERATION_NONE:
            return "none"
        elif hw_accel == cv2.VIDEO_ACCELERATION_ANY:
            # Try to detect specific hardware
            # This is a best effort as OpenCV doesn't provide detailed info
            try:
                # Run nvidia-smi to check for NVIDIA GPU
                nvidia_process = subprocess.run(
                    ["nvidia-smi"], 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE,
                    timeout=1
                )
                if nvidia_process.returncode == 0:
                    return "nvidia"
                
                # Check for Intel QuickSync
                if os.name == 'nt':  # Windows
                    intel_process = subprocess.run(
                        ["wmic", "cpu", "get", "name"], 
                        stdout=subprocess.PIPE,
                        timeout=1
                    )
                    if "Intel" in intel_process.stdout.decode():
                        return "intel_quicksync"
                else:  # Linux
                    with open('/proc/cpuinfo', 'r') as f:
                        if "Intel" in f.read():
                            return "intel_quicksync"
                
                # Check for AMD
                if os.name == 'nt':  # Windows
                    amd_process = subprocess.run(
                        ["wmic", "cpu", "get", "name"], 
                        stdout=subprocess.PIPE,
                        timeout=1
                    )
                    if "AMD" in amd_process.stdout.decode():
                        return "amd"
                else:  # Linux
                    with open('/proc/cpuinfo', 'r') as f:
                        if "AMD" in f.read():
                            return "amd"
            
            except (subprocess.SubprocessError, OSError, IOError) as e:
                logger.warning(f"Error detecting hardware acceleration: {str(e)}")
            
            return "unknown"
        elif hw_accel == cv2.VIDEO_ACCELERATION_D3D11:
            return "d3d11"
        elif hw_accel == cv2.VIDEO_ACCELERATION_VAAPI:
            return "vaapi"
        elif hw_accel == cv2.VIDEO_ACCELERATION_MFX:
            return "intel_mfx"
        else:
            return f"unknown_{int(hw_accel)}"
    
    def _detect_codec_info(self) -> str:
        """
        Detect codec information from the stream.
        
        Returns:
            str: Description of codec being used
        """
        if not self.cap:
            return self.detected_codec
        
        # Try to get codec info from OpenCV
        fourcc = int(self.cap.get(cv2.CAP_PROP_FOURCC))
        fourcc_str = "".join([chr((fourcc >> 8 * i) & 0xFF) for i in range(4)])
        
        if fourcc_str in ["H264", "AVC1", "X264"]:
            self.detected_codec = "H.264"
        elif fourcc_str in ["HEVC", "HVC1", "X265"]:
            self.detected_codec = "H.265/HEVC"
        elif fourcc_str:
            self.detected_codec = fourcc_str
        
        return self.detected_codec
    
    def start(self) -> bool:
        """
        Start the RTSP processor.
        
        Returns:
            bool: True if started successfully, False otherwise
        """
        if self.running:
            logger.warning("RTSP processor is already running")
            return True
        
        try:
            # Reset state
            self.error = None
            self.stop_event.clear()
            
            # Build capture parameters
            params = self._build_capture_params()
            
            # Create VideoCapture
            self.cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)
            
            # Set parameters
            for param, value in params.items():
                self.cap.set(param, value)
            
            # Check if connection is successful
            if not self.cap.isOpened():
                self.error = "Failed to open RTSP stream"
                logger.error(f"Failed to open RTSP stream: {self.rtsp_url}")
                return False
            
            # Set resolution
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.frame_width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.frame_height)
            
            # Detect hardware acceleration
            self.hw_acceleration_info = self._detect_hardware_acceleration()
            logger.info(f"Hardware acceleration: {self.hw_acceleration_info}")
            
            # Detect codec
            codec_info = self._detect_codec_info()
            logger.info(f"Codec: {codec_info}")
            
            # Start background thread
            self.running = True
            self.thread = threading.Thread(target=self._process_frames)
            self.thread.daemon = True
            self.thread.start()
            
            logger.info(f"Started RTSP processor for {self.rtsp_url}")
            return True
            
        except Exception as e:
            self.error = str(e)
            logger.exception(f"Error starting RTSP processor: {str(e)}")
            return False
    
    def stop(self) -> None:
        """
        Stop the RTSP processor.
        """
        if not self.running:
            return
        
        logger.info(f"Stopping RTSP processor for {self.rtsp_url}")
        
        # Signal thread to stop
        self.stop_event.set()
        
        # Wait for thread to finish
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5.0)
        
        # Release resources
        if self.cap:
            self.cap.release()
            self.cap = None
        
        self.running = False
        logger.info(f"Stopped RTSP processor for {self.rtsp_url}")
    
    def _process_frames(self) -> None:
        """
        Background thread to continuously process frames.
        """
        reconnect_count = 0
        last_frame_time = time.time()
        frames_processed = 0
        
        while not self.stop_event.is_set():
            try:
                if not self.cap or not self.cap.isOpened():
                    # Try to reconnect
                    if reconnect_count < self.reconnect_attempts:
                        reconnect_count += 1
                        logger.warning(f"Reconnecting to RTSP stream ({reconnect_count}/{self.reconnect_attempts})")
                        
                        # Release old capture
                        if self.cap:
                            self.cap.release()
                        
                        # Wait before reconnecting
                        time.sleep(self.reconnect_delay)
                        
                        # Create new capture
                        params = self._build_capture_params()
                        self.cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)
                        
                        # Set parameters
                        for param, value in params.items():
                            self.cap.set(param, value)
                        
                        continue
                    else:
                        self.error = "Max reconnect attempts reached"
                        logger.error(f"Max reconnect attempts reached for {self.rtsp_url}")
                        break
                
                # Read frame
                ret, frame = self.cap.read()
                
                if not ret:
                    logger.warning(f"Failed to read frame from {self.rtsp_url}")
                    continue
                
                # Update frame
                with self.frame_lock:
                    self.last_frame = frame
                    self.last_frame_time = time.time()
                
                # Calculate FPS control
                frames_processed += 1
                elapsed = time.time() - last_frame_time
                
                # Limit processing rate to target FPS
                if self.fps_target > 0:
                    target_time_per_frame = 1.0 / self.fps_target
                    if elapsed < target_time_per_frame:
                        time.sleep(target_time_per_frame - elapsed)
                
            except Exception as e:
                self.error = str(e)
                logger.exception(f"Error processing RTSP frame: {str(e)}")
                time.sleep(1.0)  # Avoid tight loop on error
        
        # Clean up
        if self.cap:
            self.cap.release()
            self.cap = None
    
    def get_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        """
        Get the latest frame from the RTSP stream.
        
        Returns:
            Tuple[bool, Optional[np.ndarray]]: Success flag and frame (if successful)
        """
        if not self.running or self.error:
            return False, None
        
        with self.frame_lock:
            if self.last_frame is None:
                return False, None
            
            # Return a copy to avoid threading issues
            return True, self.last_frame.copy()
    
    def get_frame_as_jpeg(self, quality: int = 95) -> Tuple[bool, Optional[bytes]]:
        """
        Get the latest frame as JPEG bytes.
        
        Args:
            quality: JPEG quality (0-100)
            
        Returns:
            Tuple[bool, Optional[bytes]]: Success flag and JPEG bytes (if successful)
        """
        success, frame = self.get_frame()
        
        if not success:
            return False, None
        
        # Encode frame as JPEG
        ret, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
        
        if not ret:
            return False, None
        
        return True, jpeg.tobytes()
    
    def get_frame_as_base64(self, quality: int = 95) -> Tuple[bool, Optional[str]]:
        """
        Get the latest frame as base64 encoded JPEG.
        
        Args:
            quality: JPEG quality (0-100)
            
        Returns:
            Tuple[bool, Optional[str]]: Success flag and base64 string (if successful)
        """
        success, jpeg = self.get_frame_as_jpeg(quality)
        
        if not success:
            return False, None
        
        # Encode as base64
        base64_str = base64.b64encode(jpeg).decode('utf-8')
        return True, base64_str
    
    def is_running(self) -> bool:
        """
        Check if the RTSP processor is running.
        
        Returns:
            bool: True if running, False otherwise
        """
        return self.running and self.thread and self.thread.is_alive()
    
    def has_error(self) -> bool:
        """
        Check if the RTSP processor has an error.
        
        Returns:
            bool: True if there is an error, False otherwise
        """
        return self.error is not None
    
    def get_error(self) -> Optional[str]:
        """
        Get the error message if there is one.
        
        Returns:
            Optional[str]: Error message or None
        """
        return self.error
    
    def get_hardware_acceleration_info(self) -> str:
        """
        Get information about the hardware acceleration being used.
        
        Returns:
            str: Description of hardware acceleration
        """
        return self.hw_acceleration_info
    
    def get_codec_info(self) -> str:
        """
        Get information about the codec being used.
        
        Returns:
            str: Description of codec
        """
        return self.detected_codec
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get the status of the RTSP processor.
        
        Returns:
            Dict[str, Any]: Dictionary of status information
        """
        status = {
            "running": self.running,
            "error": self.error,
            "hardware_acceleration": self.hw_acceleration_info,
            "codec": self.detected_codec
        }
        
        return status
