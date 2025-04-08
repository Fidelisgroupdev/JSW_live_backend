"""
Advanced RTSP Stream Processor with Hardware Acceleration

This module provides a robust, low-latency RTSP video streaming solution with:
- Hardware-accelerated decoding (NVIDIA, Intel QuickSync, VAAPI)
- Multi-threaded processing pipeline
- Adaptive buffering for network jitter
- Error handling and reconnection logic
- Support for both TCP and UDP transport

Usage:
    processor = AdvancedRTSPProcessor(rtsp_url, 
                                     transport='tcp',
                                     hardware_acceleration=True,
                                     low_latency=True)
    processor.start()
    
    # Get frames for processing
    frame = processor.get_frame()
    
    # Stop when done
    processor.stop()
"""

import cv2
import numpy as np
import time
import threading
import queue
import logging
import os
import platform
import subprocess
import re
from enum import Enum
from typing import Tuple, Dict, Optional, List, Union

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('advanced_rtsp')

class HardwareAcceleration(Enum):
    """Enum for hardware acceleration types"""
    NONE = "none"
    NVIDIA = "nvidia"
    INTEL = "intel"
    VAAPI = "vaapi"
    AMD = "amd"

class TransportProtocol(Enum):
    """Enum for RTSP transport protocols"""
    TCP = "tcp"
    UDP = "udp"
    AUTO = "auto"

class FrameData:
    """Class to store frame data with metadata"""
    def __init__(self, frame: np.ndarray, timestamp: float, frame_index: int):
        self.frame = frame
        self.timestamp = timestamp
        self.frame_index = frame_index
        self.processing_data = {}  # Store additional processing results

class AdvancedRTSPProcessor:
    """
    Advanced RTSP Stream Processor with hardware acceleration and multi-threading
    """
    def __init__(
        self,
        rtsp_url: str,
        transport: str = "tcp",
        hardware_acceleration: bool = True,
        low_latency: bool = True,
        buffer_size: int = 5,
        reconnect_attempts: int = 5,
        reconnect_delay: int = 2,
        frame_width: Optional[int] = None,
        frame_height: Optional[int] = None,
        fps_target: Optional[int] = None,
        codec: str = "auto"
    ):
        """
        Initialize the RTSP processor
        
        Args:
            rtsp_url: RTSP URL to connect to
            transport: Transport protocol ('tcp', 'udp', or 'auto')
            hardware_acceleration: Whether to use hardware acceleration if available
            low_latency: Whether to optimize for low latency
            buffer_size: Size of the frame buffer
            reconnect_attempts: Number of reconnection attempts
            reconnect_delay: Delay between reconnection attempts in seconds
            frame_width: Target frame width (None for original)
            frame_height: Target frame height (None for original)
            fps_target: Target FPS (None for original)
            codec: Preferred codec ('auto', 'h264', 'h265')
        """
        self.rtsp_url = rtsp_url
        self.transport = TransportProtocol(transport)
        self.hardware_acceleration = hardware_acceleration
        self.low_latency = low_latency
        self.buffer_size = buffer_size
        self.reconnect_attempts = reconnect_attempts
        self.reconnect_delay = reconnect_delay
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.fps_target = fps_target
        self.codec = codec
        
        # Initialize state variables
        self.is_running = False
        self.error = None
        self.last_frame_time = 0
        self.frame_count = 0
        self.dropped_frames = 0
        self.reconnect_count = 0
        self.start_time = 0
        self.hw_accel_type = HardwareAcceleration.NONE
        
        # Thread-safe queues for the pipeline
        self.frame_queue = queue.Queue(maxsize=buffer_size)
        self.processed_frame_queue = queue.Queue(maxsize=buffer_size)
        
        # Locks for thread safety
        self.lock = threading.Lock()
        
        # Threads
        self.capture_thread = None
        self.processing_thread = None
        
        # Detect available hardware acceleration
        if hardware_acceleration:
            self.hw_accel_type = self._detect_hardware_acceleration()
            logger.info(f"Using hardware acceleration: {self.hw_accel_type.value}")
        
    def _detect_hardware_acceleration(self) -> HardwareAcceleration:
        """
        Detect available hardware acceleration
        
        Returns:
            HardwareAcceleration enum value
        """
        # Check for NVIDIA GPU
        try:
            # Try to detect NVIDIA GPU using OpenCV
            if cv2.cuda.getCudaEnabledDeviceCount() > 0:
                return HardwareAcceleration.NVIDIA
                
            # Alternative detection method using subprocess
            if platform.system() == "Windows":
                result = subprocess.run(["nvidia-smi"], capture_output=True, text=True)
                if result.returncode == 0:
                    return HardwareAcceleration.NVIDIA
            else:
                result = subprocess.run(["lspci"], capture_output=True, text=True)
                if "NVIDIA" in result.stdout:
                    return HardwareAcceleration.NVIDIA
        except Exception as e:
            logger.debug(f"NVIDIA GPU detection failed: {str(e)}")
        
        # Check for Intel QuickSync
        try:
            if platform.system() == "Windows":
                result = subprocess.run(["wmic", "path", "win32_VideoController", "get", "name"], 
                                       capture_output=True, text=True)
                if "Intel" in result.stdout:
                    return HardwareAcceleration.INTEL
            else:
                result = subprocess.run(["lspci"], capture_output=True, text=True)
                if "Intel Corporation" in result.stdout and ("VGA" in result.stdout or "Display" in result.stdout):
                    return HardwareAcceleration.INTEL
        except Exception as e:
            logger.debug(f"Intel GPU detection failed: {str(e)}")
        
        # Check for VAAPI (Linux)
        if platform.system() == "Linux":
            try:
                result = subprocess.run(["vainfo"], capture_output=True, text=True)
                if result.returncode == 0:
                    return HardwareAcceleration.VAAPI
            except Exception as e:
                logger.debug(f"VAAPI detection failed: {str(e)}")
        
        # Check for AMD
        try:
            if platform.system() == "Windows":
                result = subprocess.run(["wmic", "path", "win32_VideoController", "get", "name"], 
                                       capture_output=True, text=True)
                if "AMD" in result.stdout or "Radeon" in result.stdout:
                    return HardwareAcceleration.AMD
            else:
                result = subprocess.run(["lspci"], capture_output=True, text=True)
                if "AMD" in result.stdout or "Radeon" in result.stdout:
                    return HardwareAcceleration.AMD
        except Exception as e:
            logger.debug(f"AMD GPU detection failed: {str(e)}")
        
        # No hardware acceleration available
        return HardwareAcceleration.NONE
    
    def _configure_capture_options(self) -> Dict[str, str]:
        """
        Configure capture options based on settings
        
        Returns:
            Dictionary of FFmpeg/OpenCV options
        """
        options = {}
        
        # Set transport protocol
        if self.transport == TransportProtocol.TCP:
            options["rtsp_transport"] = "tcp"
        elif self.transport == TransportProtocol.UDP:
            options["rtsp_transport"] = "udp"
        
        # Set buffer size
        if self.low_latency:
            # Low latency mode: small buffer
            options["buffer_size"] = "131072"  # 128KB
        else:
            # Normal mode: larger buffer
            options["buffer_size"] = "1048576"  # 1MB
        
        # Set hardware acceleration options
        if self.hw_accel_type == HardwareAcceleration.NVIDIA:
            if platform.system() == "Windows":
                options["hwaccel"] = "cuda"
                options["hwaccel_output_format"] = "cuda"
            else:
                options["hwaccel"] = "cuda"
                options["hwaccel_output_format"] = "cuda"
        elif self.hw_accel_type == HardwareAcceleration.INTEL:
            if platform.system() == "Windows":
                options["hwaccel"] = "qsv"
                options["hwaccel_output_format"] = "qsv"
            else:
                options["hwaccel"] = "qsv"
        elif self.hw_accel_type == HardwareAcceleration.VAAPI:
            options["hwaccel"] = "vaapi"
            options["hwaccel_device"] = "/dev/dri/renderD128"
        elif self.hw_accel_type == HardwareAcceleration.AMD:
            options["hwaccel"] = "d3d11va" if platform.system() == "Windows" else "vdpau"
        
        # Set low latency options
        if self.low_latency:
            options["max_delay"] = "100000"  # 100ms max delay
            options["fflags"] = "nobuffer"
            options["flags"] = "low_delay"
        
        # Set codec options
        if self.codec == "h264":
            options["decoder"] = "h264"
        elif self.codec == "h265":
            options["decoder"] = "hevc"
        
        # Convert options to string format for OpenCV
        return options
    
    def _create_capture(self) -> cv2.VideoCapture:
        """
        Create and configure the video capture object
        
        Returns:
            Configured OpenCV VideoCapture object
        """
        # Get capture options
        options = self._configure_capture_options()
        
        # Set environment variables for FFmpeg
        os_options = "|".join([f"{k}={v}" for k, v in options.items()])
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = os_options
        logger.debug(f"Setting FFMPEG options: {os_options}")
        
        # Create capture object
        cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)
        
        # Configure additional capture properties
        cap.set(cv2.CAP_PROP_BUFFERSIZE, self.buffer_size)
        
        if self.frame_width and self.frame_height:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.frame_width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.frame_height)
        
        if self.fps_target:
            cap.set(cv2.CAP_PROP_FPS, self.fps_target)
        
        # Check if connection is successful
        if not cap.isOpened():
            raise ConnectionError(f"Failed to open RTSP stream: {self.rtsp_url}")
        
        # Log capture properties
        actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps = cap.get(cv2.CAP_PROP_FPS)
        
        logger.info(f"Stream opened: {self.rtsp_url}")
        logger.info(f"Resolution: {actual_width}x{actual_height}, FPS: {actual_fps}")
        
        return cap
    
    def _capture_thread_func(self):
        """Thread function for capturing frames"""
        logger.info(f"Starting capture thread for {self.rtsp_url}")
        
        retry_count = 0
        frame_index = 0
        
        while self.is_running:
            try:
                # Create capture object
                cap = self._create_capture()
                
                # Reset retry count on successful connection
                retry_count = 0
                
                # Process frames
                while self.is_running:
                    # Read frame
                    ret, frame = cap.read()
                    
                    if not ret or frame is None:
                        logger.warning("Failed to read frame, reconnecting...")
                        break
                    
                    # Create frame data object
                    current_time = time.time()
                    frame_data = FrameData(frame, current_time, frame_index)
                    
                    # Try to add to queue, drop if full
                    try:
                        self.frame_queue.put(frame_data, block=False)
                        frame_index += 1
                        
                        with self.lock:
                            self.last_frame_time = current_time
                            self.frame_count += 1
                    except queue.Full:
                        # Queue is full, drop frame
                        with self.lock:
                            self.dropped_frames += 1
                        
                        if self.dropped_frames % 100 == 0:
                            logger.warning(f"Dropped {self.dropped_frames} frames due to full queue")
                    
                    # Small delay to prevent high CPU usage
                    time.sleep(0.001)
                
                # Release capture when exiting the loop
                cap.release()
                
            except Exception as e:
                logger.error(f"Error in capture thread: {str(e)}")
                
                with self.lock:
                    self.error = str(e)
                    self.reconnect_count += 1
                
                # Check if max retries reached
                retry_count += 1
                if retry_count >= self.reconnect_attempts:
                    logger.error(f"Max reconnection attempts reached ({self.reconnect_attempts})")
                    break
                
                # Wait before reconnecting
                logger.info(f"Reconnecting in {self.reconnect_delay} seconds (attempt {retry_count}/{self.reconnect_attempts})")
                time.sleep(self.reconnect_delay)
        
        logger.info(f"Capture thread ended for {self.rtsp_url}")
    
    def _processing_thread_func(self):
        """Thread function for processing frames"""
        logger.info("Starting processing thread")
        
        while self.is_running:
            try:
                # Get frame from queue with timeout
                frame_data = self.frame_queue.get(timeout=1.0)
                
                # Process frame (placeholder for actual processing)
                processed_frame = self._process_frame(frame_data)
                
                # Add to processed queue, drop if full
                try:
                    self.processed_frame_queue.put(processed_frame, block=False)
                except queue.Full:
                    # Queue is full, drop processed frame
                    pass
                
                # Mark task as done
                self.frame_queue.task_done()
                
            except queue.Empty:
                # No frames available, continue
                continue
            except Exception as e:
                logger.error(f"Error in processing thread: {str(e)}")
        
        logger.info("Processing thread ended")
    
    def _process_frame(self, frame_data: FrameData) -> FrameData:
        """
        Process a frame (placeholder for actual processing)
        
        Args:
            frame_data: Frame data object
            
        Returns:
            Processed frame data object
        """
        # This is a placeholder for actual frame processing
        # In a real implementation, this would include:
        # - Frame preprocessing
        # - AI model inference
        # - Annotation/visualization
        
        # For now, just return the original frame data
        return frame_data
    
    def start(self):
        """Start the RTSP processor"""
        if self.is_running:
            logger.warning("Processor is already running")
            return
        
        logger.info(f"Starting RTSP processor for {self.rtsp_url}")
        
        # Set state
        self.is_running = True
        self.start_time = time.time()
        self.error = None
        self.frame_count = 0
        self.dropped_frames = 0
        self.reconnect_count = 0
        
        # Clear queues
        while not self.frame_queue.empty():
            try:
                self.frame_queue.get_nowait()
                self.frame_queue.task_done()
            except queue.Empty:
                break
        
        while not self.processed_frame_queue.empty():
            try:
                self.processed_frame_queue.get_nowait()
                self.processed_frame_queue.task_done()
            except queue.Empty:
                break
        
        # Start threads
        self.capture_thread = threading.Thread(target=self._capture_thread_func, daemon=True)
        self.processing_thread = threading.Thread(target=self._processing_thread_func, daemon=True)
        
        self.capture_thread.start()
        self.processing_thread.start()
        
        logger.info("RTSP processor started")
    
    def stop(self):
        """Stop the RTSP processor"""
        if not self.is_running:
            logger.warning("Processor is not running")
            return
        
        logger.info("Stopping RTSP processor")
        
        # Set state
        self.is_running = False
        
        # Wait for threads to finish
        if self.capture_thread and self.capture_thread.is_alive():
            self.capture_thread.join(timeout=3.0)
        
        if self.processing_thread and self.processing_thread.is_alive():
            self.processing_thread.join(timeout=3.0)
        
        # Log statistics
        duration = time.time() - self.start_time
        fps = self.frame_count / duration if duration > 0 else 0
        
        logger.info(f"RTSP processor stopped")
        logger.info(f"Statistics: {self.frame_count} frames, {self.dropped_frames} dropped, {fps:.2f} FPS")
    
    def get_frame(self, block: bool = True, timeout: Optional[float] = None) -> Optional[np.ndarray]:
        """
        Get a processed frame
        
        Args:
            block: Whether to block until a frame is available
            timeout: Timeout in seconds (None for no timeout)
            
        Returns:
            Processed frame or None if no frame is available
        """
        if not self.is_running:
            return None
        
        try:
            # Get frame from processed queue
            frame_data = self.processed_frame_queue.get(block=block, timeout=timeout)
            self.processed_frame_queue.task_done()
            
            # Return frame
            return frame_data.frame
        except queue.Empty:
            return None
    
    def get_frame_data(self, block: bool = True, timeout: Optional[float] = None) -> Optional[FrameData]:
        """
        Get a processed frame with metadata
        
        Args:
            block: Whether to block until a frame is available
            timeout: Timeout in seconds (None for no timeout)
            
        Returns:
            Processed frame data or None if no frame is available
        """
        if not self.is_running:
            return None
        
        try:
            # Get frame from processed queue
            frame_data = self.processed_frame_queue.get(block=block, timeout=timeout)
            self.processed_frame_queue.task_done()
            
            # Return frame data
            return frame_data
        except queue.Empty:
            return None
    
    def get_status(self) -> Dict:
        """
        Get processor status
        
        Returns:
            Dictionary with processor status
        """
        with self.lock:
            duration = time.time() - self.start_time if self.start_time > 0 else 0
            fps = self.frame_count / duration if duration > 0 else 0
            
            return {
                "is_running": self.is_running,
                "error": self.error,
                "frame_count": self.frame_count,
                "dropped_frames": self.dropped_frames,
                "reconnect_count": self.reconnect_count,
                "fps": fps,
                "duration": duration,
                "last_frame_time": self.last_frame_time,
                "hardware_acceleration": self.hw_accel_type.value,
                "transport": self.transport.value,
                "buffer_size": self.buffer_size,
                "queue_size": self.frame_queue.qsize(),
                "processed_queue_size": self.processed_frame_queue.qsize(),
            }
