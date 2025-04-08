"""
RTSP Demo - Advanced RTSP Processing with Multi-threaded Pipeline

This script demonstrates how to use the advanced RTSP processor and multi-threaded
pipeline for real-time video processing with hardware acceleration.

Usage:
    python rtsp_demo.py --url rtsp://username:password@ip:port/path --output output.mp4
"""

import argparse
import cv2
import time
import logging
import numpy as np
import threading
import os
from typing import Optional

# Import our modules
from advanced_rtsp_processor import AdvancedRTSPProcessor, FrameData
from stream_pipeline import StreamPipeline, annotate_frame_stage

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('rtsp_demo')

def object_detection_stage(frame_data: FrameData) -> FrameData:
    """
    Simple object detection stage (placeholder)
    
    In a real implementation, this would use a proper object detection model.
    This is just a simple color-based detection for demonstration.
    
    Args:
        frame_data: Frame data to process
        
    Returns:
        Processed frame data with detection results
    """
    if frame_data.frame is None:
        return frame_data
    
    # Convert to HSV for better color detection
    hsv = cv2.cvtColor(frame_data.frame, cv2.COLOR_BGR2HSV)
    
    # Define range for red color detection
    lower_red = np.array([0, 120, 70])
    upper_red = np.array([10, 255, 255])
    mask1 = cv2.inRange(hsv, lower_red, upper_red)
    
    lower_red = np.array([170, 120, 70])
    upper_red = np.array([180, 255, 255])
    mask2 = cv2.inRange(hsv, lower_red, upper_red)
    
    # Combine masks
    mask = mask1 + mask2
    
    # Find contours
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Store detections in frame data
    detections = []
    
    for contour in contours:
        area = cv2.contourArea(contour)
        if area > 500:  # Filter small contours
            x, y, w, h = cv2.boundingRect(contour)
            detections.append({
                'class': 'red_object',
                'confidence': 0.9,
                'bbox': (x, y, x + w, y + h)
            })
    
    # Store detections in frame data
    frame_data.processing_data['detections'] = detections
    
    return frame_data

def visualization_stage(frame_data: FrameData) -> FrameData:
    """
    Visualization stage to draw detection results
    
    Args:
        frame_data: Frame data to process
        
    Returns:
        Processed frame data with visualizations
    """
    if frame_data.frame is None:
        return frame_data
    
    # Get detections
    detections = frame_data.processing_data.get('detections', [])
    
    # Draw bounding boxes
    for detection in detections:
        x1, y1, x2, y2 = detection['bbox']
        label = f"{detection['class']} {detection['confidence']:.2f}"
        
        # Draw rectangle
        cv2.rectangle(frame_data.frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        
        # Draw label
        cv2.putText(
            frame_data.frame,
            label,
            (x1, y1 - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 255, 0),
            2
        )
    
    # Add frame count and timestamp
    cv2.putText(
        frame_data.frame,
        f"Frame: {frame_data.frame_index}",
        (10, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        (0, 255, 0),
        2
    )
    
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(frame_data.timestamp))
    cv2.putText(
        frame_data.frame,
        timestamp,
        (10, 70),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        (0, 255, 0),
        2
    )
    
    return frame_data

def stats_display_stage(frame_data: FrameData, pipeline: StreamPipeline) -> FrameData:
    """
    Display pipeline statistics on frame
    
    Args:
        frame_data: Frame data to process
        pipeline: Pipeline instance for stats
        
    Returns:
        Processed frame data with stats
    """
    if frame_data.frame is None:
        return frame_data
    
    # Get pipeline stats
    stats = pipeline.get_stats()
    
    # Add stats to frame
    y_pos = 110
    cv2.putText(
        frame_data.frame,
        f"FPS: {stats['fps']:.2f}",
        (10, y_pos),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (0, 255, 0),
        2
    )
    
    y_pos += 30
    cv2.putText(
        frame_data.frame,
        f"Processed: {stats['processed_frames']}",
        (10, y_pos),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (0, 255, 0),
        2
    )
    
    y_pos += 30
    cv2.putText(
        frame_data.frame,
        f"Dropped: {stats['dropped_frames']}",
        (10, y_pos),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (0, 255, 0),
        2
    )
    
    # Add processing times
    y_pos += 40
    cv2.putText(
        frame_data.frame,
        "Processing Times (ms):",
        (10, y_pos),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (0, 255, 0),
        2
    )
    
    for stage_name, time_ms in stats['avg_processing_times'].items():
        y_pos += 25
        cv2.putText(
            frame_data.frame,
            f"  {stage_name}: {time_ms * 1000:.2f}",
            (10, y_pos),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 0),
            2
        )
    
    return frame_data

def main():
    """Main function"""
    # Parse arguments
    parser = argparse.ArgumentParser(description="RTSP Demo")
    parser.add_argument("--url", type=str, required=True, help="RTSP URL")
    parser.add_argument("--output", type=str, default="", help="Output video file")
    parser.add_argument("--transport", type=str, default="tcp", choices=["tcp", "udp", "auto"], help="Transport protocol")
    parser.add_argument("--hw-accel", action="store_true", help="Use hardware acceleration")
    parser.add_argument("--low-latency", action="store_true", help="Optimize for low latency")
    parser.add_argument("--codec", type=str, default="auto", choices=["auto", "h264", "h265"], help="Preferred codec")
    parser.add_argument("--width", type=int, default=None, help="Target frame width")
    parser.add_argument("--height", type=int, default=None, help="Target frame height")
    parser.add_argument("--fps", type=int, default=None, help="Target FPS")
    parser.add_argument("--buffer-size", type=int, default=5, help="Buffer size")
    parser.add_argument("--display", action="store_true", help="Display video")
    
    args = parser.parse_args()
    
    # Create RTSP processor
    processor = AdvancedRTSPProcessor(
        rtsp_url=args.url,
        transport=args.transport,
        hardware_acceleration=args.hw_accel,
        low_latency=args.low_latency,
        buffer_size=args.buffer_size,
        frame_width=args.width,
        frame_height=args.height,
        fps_target=args.fps,
        codec=args.codec
    )
    
    # Create pipeline
    pipeline = StreamPipeline(max_queue_size=args.buffer_size)
    
    # Add pipeline stages
    pipeline.add_stage("detect", object_detection_stage, workers=1)
    pipeline.add_stage("visualize", visualization_stage, workers=1)
    
    # Create a wrapper for the stats display stage that includes the pipeline
    def stats_stage_wrapper(frame_data: FrameData) -> FrameData:
        return stats_display_stage(frame_data, pipeline)
    
    pipeline.add_stage("stats", stats_stage_wrapper, workers=1)
    
    # Create video writer if output is specified
    video_writer = None
    if args.output:
        # Wait for first frame to get dimensions
        processor.start()
        frame = None
        for _ in range(10):  # Try a few times
            frame = processor.get_frame(timeout=1.0)
            if frame is not None:
                break
            time.sleep(0.1)
        
        if frame is not None:
            height, width = frame.shape[:2]
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            video_writer = cv2.VideoWriter(args.output, fourcc, 30.0, (width, height))
        else:
            logger.error("Could not get frame for video writer initialization")
            processor.stop()
            return
    else:
        # Start processor
        processor.start()
    
    # Start pipeline
    pipeline.start()
    
    try:
        # Process frames
        while True:
            # Get frame from processor
            frame_data = processor.get_frame_data(timeout=1.0)
            
            if frame_data is None:
                logger.warning("No frame received")
                continue
            
            # Process frame through pipeline
            pipeline.process_frame(frame_data)
            
            # Get processed frame
            processed_frame_data = pipeline.get_result(timeout=1.0)
            
            if processed_frame_data is None:
                continue
            
            # Write frame to output if specified
            if video_writer is not None and processed_frame_data.frame is not None:
                video_writer.write(processed_frame_data.frame)
            
            # Display frame if requested
            if args.display and processed_frame_data.frame is not None:
                cv2.imshow("RTSP Demo", processed_frame_data.frame)
                
                # Check for exit key
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    break
    
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        # Stop processor and pipeline
        processor.stop()
        pipeline.stop()
        
        # Release video writer
        if video_writer is not None:
            video_writer.release()
        
        # Close windows
        cv2.destroyAllWindows()
        
        # Print final stats
        stats = pipeline.get_stats()
        logger.info(f"Final statistics:")
        logger.info(f"  Processed frames: {stats['processed_frames']}")
        logger.info(f"  Dropped frames: {stats['dropped_frames']}")
        logger.info(f"  FPS: {stats['fps']:.2f}")
        logger.info(f"  Duration: {stats['duration']:.2f} seconds")

if __name__ == "__main__":
    main()
