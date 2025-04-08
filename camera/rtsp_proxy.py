import cv2
import threading
import time
import base64
import logging
from django.conf import settings
import os
import numpy as np
from pathlib import Path

logger = logging.getLogger(__name__)

class RTSPStreamManager:
    """
    Manager for RTSP streams that handles connection, frame capture,
    and conversion to web-friendly formats.
    """
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(RTSPStreamManager, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self.streams = {}  # Dictionary to store active streams
        self.snapshot_dir = Path(settings.MEDIA_ROOT) / 'camera_snapshots'
        self.snapshot_dir.mkdir(exist_ok=True, parents=True)
        self._initialized = True
        logger.info("RTSPStreamManager initialized")
    
    def get_stream(self, camera_id, rtsp_url, reconnect=False):
        """
        Get or create a stream for the given camera ID and RTSP URL.
        
        Args:
            camera_id: Unique identifier for the camera
            rtsp_url: RTSP URL to connect to
            reconnect: Force reconnection if True
            
        Returns:
            RTSPStream object
        """
        stream_key = str(camera_id)
        logger.info(f"Getting stream for camera {camera_id} with URL: {rtsp_url}")
        
        if stream_key in self.streams and not reconnect:
            # Return existing stream if it's active
            stream = self.streams[stream_key]
            if stream.is_active:
                logger.info(f"Returning existing active stream for camera {camera_id}")
                return stream
            else:
                logger.info(f"Existing stream for camera {camera_id} is not active, reconnecting")
        
        # Create new stream or reconnect
        stream = RTSPStream(camera_id, rtsp_url)
        self.streams[stream_key] = stream
        return stream
    
    def get_snapshot(self, camera_id, rtsp_url):
        """
        Get a snapshot from the camera as a base64 encoded JPEG.
        
        Args:
            camera_id: Camera ID
            rtsp_url: RTSP URL
            
        Returns:
            Base64 encoded JPEG image or None if failed
        """
        logger.info(f"Getting snapshot for camera {camera_id} with URL: {rtsp_url}")
        stream = self.get_stream(camera_id, rtsp_url)
        result = stream.get_base64_frame()
        if result:
            logger.info(f"Successfully got snapshot for camera {camera_id}")
        else:
            logger.error(f"Failed to get snapshot for camera {camera_id}")
        return result
    
    def save_snapshot(self, camera_id, rtsp_url):
        """
        Save a snapshot from the camera to disk.
        
        Args:
            camera_id: Camera ID
            rtsp_url: RTSP URL
            
        Returns:
            Path to saved snapshot or None if failed
        """
        stream = self.get_stream(camera_id, rtsp_url)
        frame = stream.get_frame()
        
        if frame is None:
            return None
            
        # Generate filename with timestamp
        timestamp = int(time.time())
        filename = f"camera_{camera_id}_{timestamp}.jpg"
        filepath = self.snapshot_dir / filename
        
        # Save the frame as JPEG
        success = cv2.imwrite(str(filepath), frame)
        
        if success:
            return f"media/camera_snapshots/{filename}"
        return None
    
    def cleanup(self):
        """Clean up all streams."""
        for stream_key, stream in list(self.streams.items()):
            stream.stop()
            del self.streams[stream_key]


class RTSPStream:
    """
    Handles a single RTSP stream connection and frame processing.
    """
    def __init__(self, camera_id, rtsp_url):
        self.camera_id = camera_id
        self.rtsp_url = rtsp_url
        self.cap = None
        self.is_active = False
        self.last_frame = None
        self.last_frame_time = 0
        self.frame_lock = threading.Lock()
        self.connection_thread = None
        self.frame_thread = None
        self.stopping = False
        
        # Configure OpenCV capture parameters for better performance
        self.cap_props = {
            cv2.CAP_PROP_BUFFERSIZE: 1,  # Minimize buffer size
            cv2.CAP_PROP_FPS: 10,        # Target 10 FPS
        }
        
        # Start connection in a separate thread
        self.connect()
    
    def connect(self):
        """Connect to the RTSP stream in a separate thread."""
        if self.connection_thread and self.connection_thread.is_alive():
            return
            
        self.stopping = False
        self.connection_thread = threading.Thread(target=self._connect_thread)
        self.connection_thread.daemon = True
        self.connection_thread.start()
    
    def _connect_thread(self):
        """Thread function to establish connection to RTSP stream."""
        try:
            logger.info(f"Connecting to RTSP stream: {self.rtsp_url}")
            
            # Try different connection options
            # 1. First try with FFMPEG backend
            logger.info(f"Trying FFMPEG backend for {self.rtsp_url}")
            self.cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)
            
            # Set capture properties
            for prop, value in self.cap_props.items():
                self.cap.set(prop, value)
            
            # Check if connection is successful
            if not self.cap.isOpened():
                logger.warning(f"Failed to open RTSP stream with FFMPEG backend: {self.rtsp_url}")
                
                # 2. Try with GStreamer backend if available
                try:
                    logger.info(f"Trying GStreamer backend for {self.rtsp_url}")
                    self.cap.release()  # Release the previous capture
                    
                    # Construct GStreamer pipeline
                    gst_pipeline = (
                        f"rtspsrc location={self.rtsp_url} latency=0 ! rtph264depay ! h264parse ! "
                        f"avdec_h264 ! videoconvert ! appsink"
                    )
                    self.cap = cv2.VideoCapture(gst_pipeline, cv2.CAP_GSTREAMER)
                    
                    if not self.cap.isOpened():
                        logger.warning(f"Failed to open RTSP stream with GStreamer backend: {self.rtsp_url}")
                        
                        # 3. Try with default backend as last resort
                        logger.info(f"Trying default backend for {self.rtsp_url}")
                        self.cap.release()
                        self.cap = cv2.VideoCapture(self.rtsp_url)
                        
                        if not self.cap.isOpened():
                            logger.error(f"All backends failed for RTSP stream: {self.rtsp_url}")
                            self.is_active = False
                            return
                except Exception as e:
                    logger.warning(f"GStreamer attempt failed: {str(e)}")
                    # Try with default backend
                    logger.info(f"Trying default backend for {self.rtsp_url}")
                    self.cap.release()
                    self.cap = cv2.VideoCapture(self.rtsp_url)
                    
                    if not self.cap.isOpened():
                        logger.error(f"All backends failed for RTSP stream: {self.rtsp_url}")
                        self.is_active = False
                        return
            
            # Try to read a test frame to confirm connection
            ret, test_frame = self.cap.read()
            if not ret or test_frame is None:
                logger.error(f"Connected but failed to read test frame from: {self.rtsp_url}")
                self.is_active = False
                return
                
            logger.info(f"Successfully connected to RTSP stream: {self.rtsp_url}")
            self.is_active = True
            
            # Start frame capture thread
            self.frame_thread = threading.Thread(target=self._frame_capture_thread)
            self.frame_thread.daemon = True
            self.frame_thread.start()
            
        except Exception as e:
            logger.error(f"Error connecting to RTSP stream: {str(e)}")
            self.is_active = False
    
    def _frame_capture_thread(self):
        """Thread function to continuously capture frames."""
        frame_count = 0
        error_count = 0
        
        while self.is_active and not self.stopping:
            try:
                ret, frame = self.cap.read()
                
                if not ret or frame is None:
                    error_count += 1
                    logger.warning(f"Frame read error #{error_count} for {self.rtsp_url}")
                    
                    if error_count > 5:  # Allow a few errors before reconnecting
                        logger.warning(f"Multiple frame read errors for {self.rtsp_url}, reconnecting...")
                        self._reconnect()
                        break
                    time.sleep(0.5)
                    continue
                
                error_count = 0
                frame_count += 1
                
                # Update the last frame with thread safety
                with self.frame_lock:
                    self.last_frame = frame
                    self.last_frame_time = time.time()
                
                # Limit capture rate to reduce CPU usage
                if frame_count % 3 == 0:  # Process every 3rd frame
                    time.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Error capturing frame: {str(e)}")
                time.sleep(1)
                error_count += 1
                
                if error_count > 5:
                    self._reconnect()
                    break
    
    def _reconnect(self):
        """Reconnect to the RTSP stream after failure."""
        logger.info(f"Reconnecting to RTSP stream: {self.rtsp_url}")
        self.stop(reconnect=True)
        time.sleep(2)  # Wait before reconnecting
        self.connect()
    
    def get_frame(self):
        """
        Get the latest frame from the stream.
        
        Returns:
            OpenCV frame or None if no frame is available
        """
        with self.frame_lock:
            if self.last_frame is None:
                logger.warning(f"No frame available for {self.rtsp_url}")
                return None
            
            # Check if frame is too old (more than 10 seconds)
            if time.time() - self.last_frame_time > 10:
                logger.warning(f"Frame for {self.rtsp_url} is too old, reconnecting...")
                self._reconnect()
                return None
                
            return self.last_frame.copy()
    
    def get_base64_frame(self):
        """
        Get the latest frame as base64 encoded JPEG.
        
        Returns:
            Base64 encoded JPEG string or None if no frame is available
        """
        frame = self.get_frame()
        if frame is None:
            return None
            
        try:
            # Resize frame to reduce size if needed
            height, width = frame.shape[:2]
            if width > 800:
                scale = 800 / width
                new_width = 800
                new_height = int(height * scale)
                frame = cv2.resize(frame, (new_width, new_height))
            
            # Encode frame as JPEG
            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            jpg_as_text = base64.b64encode(buffer).decode('utf-8')
            return jpg_as_text
            
        except Exception as e:
            logger.error(f"Error encoding frame: {str(e)}")
            return None
    
    def stop(self, reconnect=False):
        """
        Stop the stream and release resources.
        
        Args:
            reconnect: If True, prepare for reconnection
        """
        self.stopping = True
        self.is_active = False
        
        if self.cap:
            self.cap.release()
            self.cap = None
        
        if not reconnect:
            with self.frame_lock:
                self.last_frame = None
                self.last_frame_time = 0


# Create a singleton instance
rtsp_manager = RTSPStreamManager()
