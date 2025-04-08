"""
Stream Pipeline for Advanced RTSP Processing

This module provides a multi-threaded pipeline for processing RTSP streams with:
- Parallel processing stages
- AI model integration
- Frame synchronization
- Adaptive buffering
- Performance monitoring

Usage:
    # Create pipeline with stages
    pipeline = StreamPipeline()
    pipeline.add_stage("decode", decode_frame_func)
    pipeline.add_stage("detect", detect_objects_func)
    pipeline.add_stage("annotate", annotate_frame_func)
    
    # Start pipeline
    pipeline.start()
    
    # Process frames
    pipeline.process_frame(frame_data)
    
    # Get processed frames
    result = pipeline.get_result()
    
    # Stop pipeline
    pipeline.stop()
"""

import threading
import queue
import time
import logging
import numpy as np
from typing import Dict, List, Callable, Optional, Any, Tuple, Union
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from enum import Enum

# Import FrameData from advanced_rtsp_processor
from .advanced_rtsp_processor import FrameData

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('stream_pipeline')

class PipelineStage(Enum):
    """Enum for pipeline stages"""
    DECODE = "decode"
    PREPROCESS = "preprocess"
    DETECT = "detect"
    TRACK = "track"
    ANALYZE = "analyze"
    ANNOTATE = "annotate"
    ENCODE = "encode"
    CUSTOM = "custom"

@dataclass
class PipelineStageConfig:
    """Configuration for a pipeline stage"""
    name: str
    func: Callable
    workers: int = 1
    max_queue_size: int = 10
    timeout: float = 1.0
    enabled: bool = True

class PipelineStats:
    """Statistics for pipeline performance monitoring"""
    def __init__(self):
        self.processed_frames = 0
        self.dropped_frames = 0
        self.processing_times: Dict[str, List[float]] = {}
        self.queue_sizes: Dict[str, List[int]] = {}
        self.start_time = 0
        self.last_update_time = 0
        self.lock = threading.Lock()
    
    def start(self):
        """Start statistics collection"""
        self.start_time = time.time()
        self.last_update_time = self.start_time
    
    def update_processing_time(self, stage_name: str, processing_time: float):
        """Update processing time for a stage"""
        with self.lock:
            if stage_name not in self.processing_times:
                self.processing_times[stage_name] = []
            
            self.processing_times[stage_name].append(processing_time)
            
            # Keep only the last 100 values
            if len(self.processing_times[stage_name]) > 100:
                self.processing_times[stage_name] = self.processing_times[stage_name][-100:]
    
    def update_queue_size(self, stage_name: str, queue_size: int):
        """Update queue size for a stage"""
        with self.lock:
            if stage_name not in self.queue_sizes:
                self.queue_sizes[stage_name] = []
            
            self.queue_sizes[stage_name].append(queue_size)
            
            # Keep only the last 100 values
            if len(self.queue_sizes[stage_name]) > 100:
                self.queue_sizes[stage_name] = self.queue_sizes[stage_name][-100:]
    
    def increment_processed_frames(self):
        """Increment processed frames counter"""
        with self.lock:
            self.processed_frames += 1
    
    def increment_dropped_frames(self):
        """Increment dropped frames counter"""
        with self.lock:
            self.dropped_frames += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics"""
        with self.lock:
            current_time = time.time()
            duration = current_time - self.start_time
            time_since_last_update = current_time - self.last_update_time
            self.last_update_time = current_time
            
            # Calculate FPS
            fps = self.processed_frames / duration if duration > 0 else 0
            
            # Calculate average processing times
            avg_processing_times = {}
            for stage_name, times in self.processing_times.items():
                if times:
                    avg_processing_times[stage_name] = sum(times) / len(times)
                else:
                    avg_processing_times[stage_name] = 0
            
            # Calculate average queue sizes
            avg_queue_sizes = {}
            for stage_name, sizes in self.queue_sizes.items():
                if sizes:
                    avg_queue_sizes[stage_name] = sum(sizes) / len(sizes)
                else:
                    avg_queue_sizes[stage_name] = 0
            
            return {
                "processed_frames": self.processed_frames,
                "dropped_frames": self.dropped_frames,
                "fps": fps,
                "duration": duration,
                "avg_processing_times": avg_processing_times,
                "avg_queue_sizes": avg_queue_sizes,
                "time_since_last_update": time_since_last_update
            }

class StreamPipeline:
    """
    Multi-threaded pipeline for processing video streams
    """
    def __init__(self, max_queue_size: int = 10, adaptive_buffering: bool = True):
        """
        Initialize the stream pipeline
        
        Args:
            max_queue_size: Maximum size of the queues between stages
            adaptive_buffering: Whether to use adaptive buffering
        """
        self.stages: Dict[str, PipelineStageConfig] = {}
        self.stage_queues: Dict[str, queue.Queue] = {}
        self.stage_threads: Dict[str, List[threading.Thread]] = {}
        self.stage_executors: Dict[str, ThreadPoolExecutor] = {}
        
        self.max_queue_size = max_queue_size
        self.adaptive_buffering = adaptive_buffering
        
        self.input_queue = queue.Queue(maxsize=max_queue_size)
        self.output_queue = queue.Queue(maxsize=max_queue_size)
        
        self.is_running = False
        self.stats = PipelineStats()
        
        # Locks for thread safety
        self.lock = threading.Lock()
    
    def add_stage(self, 
                 name: str, 
                 func: Callable, 
                 workers: int = 1, 
                 max_queue_size: Optional[int] = None,
                 timeout: float = 1.0) -> None:
        """
        Add a processing stage to the pipeline
        
        Args:
            name: Stage name
            func: Processing function (takes FrameData, returns FrameData)
            workers: Number of worker threads
            max_queue_size: Maximum size of the stage queue (None for default)
            timeout: Timeout for queue operations
        """
        if max_queue_size is None:
            max_queue_size = self.max_queue_size
        
        self.stages[name] = PipelineStageConfig(
            name=name,
            func=func,
            workers=workers,
            max_queue_size=max_queue_size,
            timeout=timeout
        )
        
        # Create queue for this stage
        self.stage_queues[name] = queue.Queue(maxsize=max_queue_size)
        
        logger.info(f"Added pipeline stage: {name} with {workers} workers")
    
    def _stage_worker(self, stage_name: str, worker_id: int):
        """
        Worker thread for a pipeline stage
        
        Args:
            stage_name: Stage name
            worker_id: Worker ID
        """
        logger.info(f"Starting worker {worker_id} for stage {stage_name}")
        
        stage_config = self.stages[stage_name]
        input_queue = self.stage_queues[stage_name]
        
        # Determine output queue
        stage_names = list(self.stages.keys())
        stage_index = stage_names.index(stage_name)
        
        if stage_index < len(stage_names) - 1:
            # Not the last stage, output to next stage
            next_stage = stage_names[stage_index + 1]
            output_queue = self.stage_queues[next_stage]
        else:
            # Last stage, output to output queue
            output_queue = self.output_queue
        
        while self.is_running:
            try:
                # Get frame from input queue with timeout
                frame_data = input_queue.get(timeout=stage_config.timeout)
                
                try:
                    # Measure processing time
                    start_time = time.time()
                    
                    # Process frame
                    processed_frame = stage_config.func(frame_data)
                    
                    # Update statistics
                    processing_time = time.time() - start_time
                    self.stats.update_processing_time(stage_name, processing_time)
                    
                    # Check if frame was dropped (None result)
                    if processed_frame is None:
                        self.stats.increment_dropped_frames()
                    else:
                        # Try to add to output queue, drop if full
                        try:
                            output_queue.put(processed_frame, block=False)
                        except queue.Full:
                            # Queue is full, drop frame
                            self.stats.increment_dropped_frames()
                            
                            if self.adaptive_buffering:
                                # In adaptive mode, drop oldest frames from output queue
                                try:
                                    # Remove oldest frame
                                    _ = output_queue.get_nowait()
                                    output_queue.task_done()
                                    
                                    # Add new frame
                                    output_queue.put(processed_frame, block=False)
                                except (queue.Empty, queue.Full):
                                    # Could not adapt, frame is dropped
                                    pass
                except Exception as e:
                    logger.error(f"Error in stage {stage_name}: {str(e)}")
                    self.stats.increment_dropped_frames()
                
                # Mark task as done
                input_queue.task_done()
                
                # Update queue size statistics
                self.stats.update_queue_size(stage_name, input_queue.qsize())
                
            except queue.Empty:
                # No frames available, continue
                continue
            except Exception as e:
                logger.error(f"Error in worker {worker_id} for stage {stage_name}: {str(e)}")
        
        logger.info(f"Worker {worker_id} for stage {stage_name} stopped")
    
    def _input_worker(self):
        """Worker thread for the input stage"""
        logger.info("Starting input worker")
        
        # Get first stage
        first_stage = list(self.stages.keys())[0]
        output_queue = self.stage_queues[first_stage]
        
        while self.is_running:
            try:
                # Get frame from input queue with timeout
                frame_data = self.input_queue.get(timeout=1.0)
                
                # Try to add to first stage queue, drop if full
                try:
                    output_queue.put(frame_data, block=False)
                except queue.Full:
                    # Queue is full, drop frame
                    self.stats.increment_dropped_frames()
                
                # Mark task as done
                self.input_queue.task_done()
                
            except queue.Empty:
                # No frames available, continue
                continue
            except Exception as e:
                logger.error(f"Error in input worker: {str(e)}")
        
        logger.info("Input worker stopped")
    
    def start(self):
        """Start the pipeline"""
        if self.is_running:
            logger.warning("Pipeline is already running")
            return
        
        if not self.stages:
            logger.error("No stages added to pipeline")
            return
        
        logger.info("Starting pipeline")
        
        # Set state
        self.is_running = True
        
        # Start statistics
        self.stats.start()
        
        # Clear queues
        self._clear_queues()
        
        # Start input worker
        input_thread = threading.Thread(target=self._input_worker, daemon=True)
        input_thread.start()
        
        # Start stage workers
        for stage_name, stage_config in self.stages.items():
            self.stage_threads[stage_name] = []
            
            for worker_id in range(stage_config.workers):
                thread = threading.Thread(
                    target=self._stage_worker,
                    args=(stage_name, worker_id),
                    daemon=True
                )
                thread.start()
                self.stage_threads[stage_name].append(thread)
        
        logger.info("Pipeline started")
    
    def _clear_queues(self):
        """Clear all queues"""
        # Clear input queue
        while not self.input_queue.empty():
            try:
                self.input_queue.get_nowait()
                self.input_queue.task_done()
            except queue.Empty:
                break
        
        # Clear stage queues
        for name, q in self.stage_queues.items():
            while not q.empty():
                try:
                    q.get_nowait()
                    q.task_done()
                except queue.Empty:
                    break
        
        # Clear output queue
        while not self.output_queue.empty():
            try:
                self.output_queue.get_nowait()
                self.output_queue.task_done()
            except queue.Empty:
                break
    
    def stop(self):
        """Stop the pipeline"""
        if not self.is_running:
            logger.warning("Pipeline is not running")
            return
        
        logger.info("Stopping pipeline")
        
        # Set state
        self.is_running = False
        
        # Wait for threads to finish
        for stage_name, threads in self.stage_threads.items():
            for thread in threads:
                if thread.is_alive():
                    thread.join(timeout=3.0)
        
        # Log statistics
        stats = self.stats.get_stats()
        logger.info(f"Pipeline stopped")
        logger.info(f"Statistics: {stats['processed_frames']} frames, {stats['dropped_frames']} dropped, {stats['fps']:.2f} FPS")
    
    def process_frame(self, frame_data: FrameData) -> bool:
        """
        Process a frame through the pipeline
        
        Args:
            frame_data: Frame data to process
            
        Returns:
            True if frame was added to pipeline, False if dropped
        """
        if not self.is_running:
            return False
        
        try:
            # Add to input queue, drop if full
            self.input_queue.put(frame_data, block=False)
            return True
        except queue.Full:
            # Queue is full, drop frame
            self.stats.increment_dropped_frames()
            return False
    
    def get_result(self, block: bool = True, timeout: Optional[float] = None) -> Optional[FrameData]:
        """
        Get a processed frame from the pipeline
        
        Args:
            block: Whether to block until a frame is available
            timeout: Timeout in seconds (None for no timeout)
            
        Returns:
            Processed frame data or None if no frame is available
        """
        if not self.is_running:
            return None
        
        try:
            # Get frame from output queue
            frame_data = self.output_queue.get(block=block, timeout=timeout)
            self.output_queue.task_done()
            
            # Update statistics
            self.stats.increment_processed_frames()
            
            # Return frame data
            return frame_data
        except queue.Empty:
            return None
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get pipeline statistics
        
        Returns:
            Dictionary with pipeline statistics
        """
        return self.stats.get_stats()
    
    def is_empty(self) -> bool:
        """
        Check if pipeline is empty
        
        Returns:
            True if pipeline is empty, False otherwise
        """
        # Check input queue
        if not self.input_queue.empty():
            return False
        
        # Check stage queues
        for name, q in self.stage_queues.items():
            if not q.empty():
                return False
        
        # Check output queue
        if not self.output_queue.empty():
            return False
        
        return True

# Common pipeline stage functions

def decode_frame_stage(frame_data: FrameData) -> FrameData:
    """
    Decode frame stage
    
    Args:
        frame_data: Frame data to process
        
    Returns:
        Processed frame data
    """
    # This is a placeholder for actual frame decoding
    # In a real implementation, this would handle hardware decoding
    
    # Just return the original frame data
    return frame_data

def preprocess_frame_stage(frame_data: FrameData) -> FrameData:
    """
    Preprocess frame stage
    
    Args:
        frame_data: Frame data to process
        
    Returns:
        Processed frame data
    """
    # Example: Convert BGR to RGB
    if frame_data.frame is not None:
        frame_data.processing_data['original_frame'] = frame_data.frame.copy()
        frame_data.frame = cv2.cvtColor(frame_data.frame, cv2.COLOR_BGR2RGB)
    
    return frame_data

def resize_frame_stage(frame_data: FrameData, target_width: int, target_height: int) -> FrameData:
    """
    Resize frame stage
    
    Args:
        frame_data: Frame data to process
        target_width: Target width
        target_height: Target height
        
    Returns:
        Processed frame data
    """
    if frame_data.frame is not None:
        frame_data.processing_data['original_size'] = frame_data.frame.shape[:2]
        frame_data.frame = cv2.resize(frame_data.frame, (target_width, target_height))
    
    return frame_data

def annotate_frame_stage(frame_data: FrameData) -> FrameData:
    """
    Annotate frame stage
    
    Args:
        frame_data: Frame data to process
        
    Returns:
        Processed frame data
    """
    # Example: Add timestamp
    if frame_data.frame is not None:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(frame_data.timestamp))
        cv2.putText(
            frame_data.frame,
            timestamp,
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 255, 0),
            2
        )
    
    return frame_data
