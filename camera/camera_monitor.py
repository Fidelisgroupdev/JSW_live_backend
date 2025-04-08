"""
Camera Monitoring Module

This module provides a centralized system for monitoring multiple RTSP camera streams
using the advanced RTSP processor with hardware acceleration and multi-threading.
"""

import logging
import threading
import time
import cv2
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
import os
import json
from datetime import datetime

from django.conf import settings
from django.utils import timezone

from .models import Camera, DetectionEvent
from .advanced_rtsp_processor import AdvancedRTSPProcessor, FrameData
from .stream_pipeline import StreamPipeline

# Configure logging
logger = logging.getLogger(__name__)

class CameraMonitor:
    """
    Manages multiple camera streams using the advanced RTSP processor.
    
    This class provides a centralized system for:
    1. Starting and stopping camera streams
    2. Processing frames from multiple cameras
    3. Detecting events across cameras
    4. Managing hardware resources efficiently
    """
    
    def __init__(self):
        self.active_processors: Dict[int, AdvancedRTSPProcessor] = {}
        self.active_pipelines: Dict[int, StreamPipeline] = {}
        self.camera_threads: Dict[int, threading.Thread] = {}
        self.camera_status: Dict[int, Dict[str, Any]] = {}
        self.stop_events: Dict[int, threading.Event] = {}
        self.lock = threading.RLock()
        
        # Default configuration
        self.default_config = {
            'hardware_acceleration': True,
            'low_latency': True,
            'transport': 'tcp',
            'buffer_size': 5,
            'reconnect_attempts': 3,
            'reconnect_delay': 2,
            'frame_processing_interval': 0.1,  # Process every 100ms
            'status_update_interval': 5.0,     # Update status every 5 seconds
            'codec': 'auto'  # Added codec option with default 'auto'
        }
        
        # Load any custom configuration
        self.load_config()
        
        # Directory for saving snapshots
        self.snapshot_dir = getattr(settings, 'CAMERA_SNAPSHOT_DIR', 'media/camera_snapshots')
        os.makedirs(self.snapshot_dir, exist_ok=True)
    
    def load_config(self):
        """Load custom configuration if available"""
        try:
            config_path = os.path.join(settings.BASE_DIR, 'camera', 'config', 'monitor_config.json')
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    custom_config = json.load(f)
                    self.default_config.update(custom_config)
                    logger.info(f"Loaded custom camera monitor configuration: {custom_config}")
        except Exception as e:
            logger.error(f"Error loading camera monitor configuration: {str(e)}")
    
    def start_camera(self, camera_id: int, custom_config: Optional[Dict[str, Any]] = None) -> bool:
        """
        Start monitoring a camera with the given ID
        
        Args:
            camera_id: ID of the camera to monitor
            custom_config: Optional custom configuration for this camera
            
        Returns:
            bool: True if camera was started successfully, False otherwise
        """
        with self.lock:
            # Check if camera is already being monitored
            if camera_id in self.active_processors:
                logger.info(f"Camera {camera_id} is already being monitored")
                return True
            
            try:
                # Get camera from database
                camera = Camera.objects.get(id=camera_id)
                
                # Update camera status to connecting
                camera.status = 'connecting'
                camera.save()
                
                # Merge default config with custom config
                config = self.default_config.copy()
                if custom_config:
                    config.update(custom_config)
                
                # Detect codec from URL if set to auto
                if config['codec'] == 'auto':
                    url = camera.rtsp_url.lower()
                    # Check for Hikvision cameras
                    if 'hikvision' in url or 'isapi' in url:
                        # Channels 401, 402 typically use H.265
                        if 'ch=4' in url or '/channels/4' in url:
                            config['codec'] = 'h265'
                        # Channels 101, 102 typically use H.264
                        elif 'ch=1' in url or '/channels/1' in url:
                            config['codec'] = 'h264'
                    # Check for explicit codec mentions in URL
                    elif 'h265' in url or 'hevc' in url:
                        config['codec'] = 'h265'
                    elif 'h264' in url or 'avc' in url:
                        config['codec'] = 'h264'
                    else:
                        # Default to H.264 if we can't detect
                        config['codec'] = 'h264'
                
                logger.info(f"Starting camera {camera_id} with config: {config}")
                
                # Create stop event
                stop_event = threading.Event()
                self.stop_events[camera_id] = stop_event
                
                # Create processor
                processor = AdvancedRTSPProcessor(
                    rtsp_url=camera.rtsp_url,
                    transport=config['transport'],
                    hardware_acceleration=config['hardware_acceleration'],
                    low_latency=config['low_latency'],
                    buffer_size=config['buffer_size'],
                    reconnect_attempts=config['reconnect_attempts'],
                    reconnect_delay=config['reconnect_delay'],
                    frame_width=camera.resolution_width,
                    frame_height=camera.resolution_height,
                    fps_target=camera.fps,
                    codec=config['codec']  # Pass codec to processor
                )
                
                # Create pipeline
                pipeline = StreamPipeline(max_queue_size=config['buffer_size'])
                
                # Add basic processing stages - can be customized per camera
                pipeline.add_stage("preprocess", self._preprocess_stage, workers=1)
                
                # Start processor and pipeline
                processor.start()
                pipeline.start()
                
                # Store processor and pipeline
                self.active_processors[camera_id] = processor
                self.active_pipelines[camera_id] = pipeline
                
                # Initialize camera status
                self.camera_status[camera_id] = {
                    'last_frame_time': None,
                    'frames_processed': 0,
                    'frames_dropped': 0,
                    'detection_events': 0,
                    'last_status_update': time.time(),
                    'status': 'connecting',
                    'error': None,
                    'fps': 0,
                    'codec': config['codec']  # Include codec in status
                }
                
                # Start camera thread
                thread = threading.Thread(
                    target=self._camera_monitoring_thread,
                    args=(camera_id, stop_event, config),
                    daemon=True
                )
                thread.start()
                self.camera_threads[camera_id] = thread
                
                logger.info(f"Started monitoring camera {camera_id} ({camera.name})")
                return True
                
            except Camera.DoesNotExist:
                logger.error(f"Camera with ID {camera_id} does not exist")
                return False
            except Exception as e:
                logger.error(f"Error starting camera {camera_id}: {str(e)}")
                # Update camera status to error
                try:
                    camera = Camera.objects.get(id=camera_id)
                    camera.status = 'error'
                    camera.save()
                except:
                    pass
                return False
    
    def stop_camera(self, camera_id: int) -> bool:
        """
        Stop monitoring a camera
        
        Args:
            camera_id: ID of the camera to stop monitoring
            
        Returns:
            bool: True if camera was stopped successfully, False otherwise
        """
        with self.lock:
            if camera_id not in self.active_processors:
                logger.warning(f"Camera {camera_id} is not being monitored")
                return False
            
            try:
                # Signal thread to stop
                if camera_id in self.stop_events:
                    self.stop_events[camera_id].set()
                
                # Stop processor and pipeline
                if camera_id in self.active_processors:
                    self.active_processors[camera_id].stop()
                
                if camera_id in self.active_pipelines:
                    self.active_pipelines[camera_id].stop()
                
                # Wait for thread to finish
                if camera_id in self.camera_threads:
                    self.camera_threads[camera_id].join(timeout=5.0)
                
                # Clean up
                if camera_id in self.active_processors:
                    del self.active_processors[camera_id]
                
                if camera_id in self.active_pipelines:
                    del self.active_pipelines[camera_id]
                
                if camera_id in self.camera_threads:
                    del self.camera_threads[camera_id]
                
                if camera_id in self.stop_events:
                    del self.stop_events[camera_id]
                
                if camera_id in self.camera_status:
                    del self.camera_status[camera_id]
                
                # Update camera status to inactive
                try:
                    camera = Camera.objects.get(id=camera_id)
                    camera.status = 'inactive'
                    camera.save()
                except:
                    pass
                
                logger.info(f"Stopped monitoring camera {camera_id}")
                return True
                
            except Exception as e:
                logger.error(f"Error stopping camera {camera_id}: {str(e)}")
                return False
    
    def stop_all_cameras(self):
        """Stop all active camera monitors"""
        with self.lock:
            camera_ids = list(self.active_processors.keys())
            for camera_id in camera_ids:
                self.stop_camera(camera_id)
    
    def get_camera_status(self, camera_id: int) -> Dict[str, Any]:
        """
        Get the current status of a camera
        
        Args:
            camera_id: ID of the camera
            
        Returns:
            Dict containing status information
        """
        with self.lock:
            if camera_id not in self.camera_status:
                return {
                    'status': 'inactive',
                    'error': 'Camera is not being monitored'
                }
            
            status = self.camera_status[camera_id].copy()
            
            # Add processor stats if available
            if camera_id in self.active_processors:
                processor = self.active_processors[camera_id]
                processor_status = processor.get_status()
                status.update(processor_status)
            
            # Add pipeline stats if available
            if camera_id in self.active_pipelines:
                pipeline = self.active_pipelines[camera_id]
                pipeline_stats = pipeline.get_stats()
                status['pipeline_stats'] = pipeline_stats
            
            return status
    
    def get_frame(self, camera_id: int) -> Tuple[Optional[np.ndarray], Optional[str]]:
        """
        Get the latest frame from a camera
        
        Args:
            camera_id: ID of the camera
            
        Returns:
            Tuple of (frame, error_message)
        """
        with self.lock:
            if camera_id not in self.active_processors:
                return None, "Camera is not being monitored"
            
            try:
                processor = self.active_processors[camera_id]
                frame = processor.get_frame(timeout=1.0)
                
                if frame is None:
                    return None, "No frame available"
                
                return frame, None
                
            except Exception as e:
                logger.error(f"Error getting frame from camera {camera_id}: {str(e)}")
                return None, str(e)
    
    def get_snapshot(self, camera_id: int, save_to_disk: bool = False) -> Tuple[Optional[np.ndarray], Optional[str], Optional[str]]:
        """
        Get a snapshot from a camera
        
        Args:
            camera_id: ID of the camera
            save_to_disk: Whether to save the snapshot to disk
            
        Returns:
            Tuple of (frame, file_path, error_message)
        """
        frame, error = self.get_frame(camera_id)
        
        if frame is None:
            return None, None, error
        
        if save_to_disk:
            try:
                # Create filename with timestamp
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"camera_{camera_id}_{timestamp}.jpg"
                filepath = os.path.join(self.snapshot_dir, filename)
                
                # Save image
                cv2.imwrite(filepath, frame)
                
                return frame, filepath, None
            except Exception as e:
                logger.error(f"Error saving snapshot from camera {camera_id}: {str(e)}")
                return frame, None, str(e)
        
        return frame, None, None
    
    def _camera_monitoring_thread(self, camera_id: int, stop_event: threading.Event, config: Dict[str, Any]):
        """
        Thread function for monitoring a camera
        
        Args:
            camera_id: ID of the camera to monitor
            stop_event: Event to signal thread to stop
            config: Configuration for this camera
        """
        logger.info(f"Camera monitoring thread started for camera {camera_id}")
        
        try:
            camera = Camera.objects.get(id=camera_id)
            processor = self.active_processors[camera_id]
            pipeline = self.active_pipelines[camera_id]
            
            # Update camera status to active
            camera.status = 'active'
            camera.save()
            
            # Update status
            with self.lock:
                self.camera_status[camera_id]['status'] = 'active'
            
            last_frame_time = time.time()
            last_status_update = time.time()
            frames_processed = 0
            
            while not stop_event.is_set():
                current_time = time.time()
                
                # Process frames at the specified interval
                if current_time - last_frame_time >= config['frame_processing_interval']:
                    # Get frame from processor
                    frame_data = processor.get_frame_data(timeout=0.5)
                    
                    if frame_data is not None:
                        # Process frame through pipeline
                        pipeline.process_frame(frame_data)
                        
                        # Get processed frame
                        processed_frame_data = pipeline.get_result(timeout=0.5)
                        
                        if processed_frame_data is not None:
                            # Update status
                            with self.lock:
                                self.camera_status[camera_id]['last_frame_time'] = current_time
                                self.camera_status[camera_id]['frames_processed'] += 1
                                frames_processed += 1
                        else:
                            # Frame was dropped
                            with self.lock:
                                self.camera_status[camera_id]['frames_dropped'] += 1
                    
                    last_frame_time = current_time
                
                # Update status periodically
                if current_time - last_status_update >= config['status_update_interval']:
                    # Calculate FPS
                    elapsed = current_time - last_status_update
                    fps = frames_processed / elapsed if elapsed > 0 else 0
                    
                    # Update status
                    with self.lock:
                        self.camera_status[camera_id]['fps'] = fps
                        self.camera_status[camera_id]['last_status_update'] = current_time
                    
                    # Reset counters
                    frames_processed = 0
                    last_status_update = current_time
                    
                    # Check processor status
                    processor_status = processor.get_status()
                    if processor_status.get('error'):
                        with self.lock:
                            self.camera_status[camera_id]['error'] = processor_status['error']
                            self.camera_status[camera_id]['status'] = 'error'
                        
                        # Update camera status in database
                        camera.status = 'error'
                        camera.save()
                
                # Sleep a bit to avoid busy waiting
                time.sleep(0.01)
        
        except Exception as e:
            logger.error(f"Error in camera monitoring thread for camera {camera_id}: {str(e)}")
            
            # Update status
            with self.lock:
                self.camera_status[camera_id]['status'] = 'error'
                self.camera_status[camera_id]['error'] = str(e)
            
            # Update camera status in database
            try:
                camera = Camera.objects.get(id=camera_id)
                camera.status = 'error'
                camera.save()
            except:
                pass
        
        logger.info(f"Camera monitoring thread stopped for camera {camera_id}")
    
    def _preprocess_stage(self, frame_data: FrameData) -> FrameData:
        """
        Basic preprocessing stage for all cameras
        
        Args:
            frame_data: Frame data to process
            
        Returns:
            Processed frame data
        """
        if frame_data.frame is None:
            return frame_data
        
        # Example preprocessing - resize if needed
        if frame_data.processing_data.get('resize'):
            width, height = frame_data.processing_data['resize']
            frame_data.frame = cv2.resize(frame_data.frame, (width, height))
        
        return frame_data


# Create a singleton instance
camera_monitor = CameraMonitor()
