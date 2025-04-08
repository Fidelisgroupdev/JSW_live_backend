"""
Cement bag counter using RTSP camera feed and YOLOv5 detection.
"""
import cv2
import time
import threading
import numpy as np
from datetime import datetime
from .rtsp_api import RTSPStream, get_or_create_processor
from .cement_detector import CementBagDetector

class CementBagCounter:
    """
    Counter for cement bags using RTSP camera feed and YOLOv5 detection.
    """
    def __init__(self, rtsp_url, model_path=None, line_position=0.5, 
                 count_direction='both', resolution='medium', 
                 codec='auto', transport='tcp'):
        """
        Initialize the cement bag counter.
        
        Args:
            rtsp_url: RTSP camera URL
            model_path: Path to YOLOv5 model weights
            line_position: Position of counting line (0.0-1.0, relative to frame height)
            count_direction: 'up', 'down', or 'both'
            resolution: Camera resolution ('low', 'medium', 'high')
            codec: Video codec ('auto', 'h264', 'h265')
            transport: Transport protocol ('tcp', 'udp')
        """
        self.rtsp_url = rtsp_url
        self.line_position = line_position
        self.count_direction = count_direction
        self.resolution = resolution
        self.codec = codec
        self.transport = transport
        
        # Initialize detector
        self.detector = CementBagDetector(model_path)
        
        # Initialize counters
        self.total_count = 0
        self.last_frame_count = 0
        self.hourly_counts = {}
        self.daily_counts = {}
        self.last_centers = {}  # Track object centers for crossing detection
        self.object_id_counter = 0
        
        # Initialize stream processor
        self.stream_processor = None
        
        # Threading
        self.lock = threading.Lock()
        self.running = False
        self.thread = None
        
        # Performance metrics
        self.fps = 0
        self.processing_time = 0
        self.last_update_time = time.time()
        
        # Store the last processed frame
        self.last_frame = None
        self.last_annotated_frame = None
    
    def start(self):
        """Start the cement bag counter."""
        if self.running:
            return
        
        self.running = True
        
        # Get or create RTSP stream processor
        self.stream_processor = get_or_create_processor(
            self.rtsp_url, 
            resolution=self.resolution,
            codec=self.codec,
            transport=self.transport
        )
        
        # Start background thread for processing
        self.thread = threading.Thread(target=self._process_frames)
        self.thread.daemon = True
        self.thread.start()
        
        print(f"Started cement bag counter for {self.rtsp_url}")
    
    def stop(self):
        """Stop the cement bag counter."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
        print(f"Stopped cement bag counter for {self.rtsp_url}")
    
    def _process_frames(self):
        """Background thread to process frames and count bags."""
        frame_count = 0
        start_time = time.time()
        
        while self.running:
            # Get frame from stream processor
            if not self.stream_processor:
                time.sleep(0.1)
                continue
            
            # Get the raw frame
            frame = self.stream_processor.get_frame()
            if frame is None:
                time.sleep(0.1)
                continue
            
            # Decode the JPEG frame
            try:
                frame = cv2.imdecode(np.frombuffer(frame, np.uint8), cv2.IMREAD_COLOR)
            except Exception as e:
                print(f"Error decoding frame: {str(e)}")
                time.sleep(0.1)
                continue
            
            # Store the raw frame
            with self.lock:
                self.last_frame = frame.copy()
            
            # Calculate line position
            line_y = int(frame.shape[0] * self.line_position)
            
            # Process the frame with the detector
            process_start = time.time()
            count, annotated_frame = self._count_bags_with_tracking(frame, line_y)
            process_end = time.time()
            
            # Update processing time
            self.processing_time = process_end - process_start
            
            # Store the annotated frame
            with self.lock:
                self.last_annotated_frame = annotated_frame
            
            # Update FPS calculation
            frame_count += 1
            elapsed = time.time() - start_time
            if elapsed >= 1.0:
                self.fps = frame_count / elapsed
                frame_count = 0
                start_time = time.time()
            
            # Limit processing rate to avoid excessive CPU usage
            time.sleep(0.01)
    
    def _count_bags_with_tracking(self, frame, line_y):
        """
        Count bags with object tracking to detect line crossings.
        
        Args:
            frame: OpenCV image
            line_y: Y-coordinate of counting line
            
        Returns:
            count: Number of new bags counted
            annotated_frame: Frame with annotations
        """
        # Get detections
        detections, annotated_frame = self.detector.detect(frame)
        
        # Draw counting line
        cv2.line(annotated_frame, (0, line_y), (frame.shape[1], line_y), (0, 0, 255), 2)
        
        # Current centers of detected objects
        current_centers = {}
        
        # Process each detection
        for det in detections:
            if det[5] != 0:  # Skip if not a cement bag
                continue
                
            x1, y1, x2, y2, conf, class_id = det
            x1, y1, x2, y2 = map(int, [x1, y1, x2, y2])
            
            # Calculate center
            center_x = (x1 + x2) // 2
            center_y = (y1 + y2) // 2
            
            # Find the closest existing tracked object
            min_dist = float('inf')
            closest_id = None
            
            for obj_id, (prev_x, prev_y) in self.last_centers.items():
                dist = np.sqrt((center_x - prev_x)**2 + (center_y - prev_y)**2)
                if dist < min_dist:
                    min_dist = dist
                    closest_id = obj_id
            
            # If close enough to an existing object, use that ID
            if closest_id is not None and min_dist < 50:  # Threshold for same object
                obj_id = closest_id
            else:
                # New object
                obj_id = self.object_id_counter
                self.object_id_counter += 1
            
            # Store current center
            current_centers[obj_id] = (center_x, center_y)
            
            # Check if object crossed the line
            if obj_id in self.last_centers:
                prev_x, prev_y = self.last_centers[obj_id]
                
                # Line crossing detection
                if (prev_y < line_y and center_y >= line_y) or (prev_y >= line_y and center_y < line_y):
                    # Determine direction
                    direction = 'down' if center_y > prev_y else 'up'
                    
                    # Count based on direction setting
                    if self.count_direction == 'both' or direction == self.count_direction:
                        self.total_count += 1
                        
                        # Update hourly and daily counts
                        now = datetime.now()
                        hour_key = now.strftime('%Y-%m-%d %H:00')
                        day_key = now.strftime('%Y-%m-%d')
                        
                        with self.lock:
                            self.hourly_counts[hour_key] = self.hourly_counts.get(hour_key, 0) + 1
                            self.daily_counts[day_key] = self.daily_counts.get(day_key, 0) + 1
                        
                        # Draw crossing indicator
                        color = (0, 255, 255)  # Yellow for crossing
                        cv2.circle(annotated_frame, (center_x, center_y), 10, color, -1)
            
            # Draw ID on the bounding box
            cv2.putText(annotated_frame, f"ID: {obj_id}", (x1, y1 - 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 2)
        
        # Update last centers
        self.last_centers = current_centers
        
        # Draw count on frame
        cv2.putText(annotated_frame, f"Total Count: {self.total_count}", (10, 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        
        # Draw FPS and processing time
        cv2.putText(annotated_frame, f"FPS: {self.fps:.1f}", (10, 70), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        cv2.putText(annotated_frame, f"Process: {self.processing_time*1000:.1f}ms", (10, 100), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        
        return self.total_count, annotated_frame
    
    def get_frame(self):
        """Get the latest processed frame as JPEG bytes."""
        with self.lock:
            if self.last_annotated_frame is None:
                return None
            
            # Encode frame to JPEG
            _, jpeg = cv2.imencode('.jpg', self.last_annotated_frame)
            return jpeg.tobytes()
    
    def get_frame_base64(self):
        """Get the latest processed frame as base64 encoded JPEG."""
        import base64
        frame_bytes = self.get_frame()
        if frame_bytes:
            return base64.b64encode(frame_bytes).decode('utf-8')
        return None
    
    def get_status(self):
        """Get counter status information."""
        with self.lock:
            # Get hourly counts for today
            today = datetime.now().strftime('%Y-%m-%d')
            today_hourly = {k: v for k, v in self.hourly_counts.items() if k.startswith(today)}
            
            return {
                'total_count': self.total_count,
                'fps': self.fps,
                'processing_time_ms': self.processing_time * 1000,
                'line_position': self.line_position,
                'count_direction': self.count_direction,
                'today_count': self.daily_counts.get(today, 0),
                'today_hourly': today_hourly,
                'is_running': self.running,
                'rtsp_url': self.rtsp_url,
                'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }

# Dictionary to store active counters
active_counters = {}

def get_or_create_counter(rtsp_url, model_path=None, line_position=0.5, 
                         count_direction='both', resolution='medium', 
                         codec='auto', transport='tcp'):
    """
    Get or create a cement bag counter for the given RTSP URL.
    
    Args:
        rtsp_url: RTSP camera URL
        model_path: Path to YOLOv5 model weights
        line_position: Position of counting line (0.0-1.0, relative to frame height)
        count_direction: 'up', 'down', or 'both'
        resolution: Camera resolution ('low', 'medium', 'high')
        codec: Video codec ('auto', 'h264', 'h265')
        transport: Transport protocol ('tcp', 'udp')
        
    Returns:
        counter: CementBagCounter instance
    """
    # Create key for counter lookup
    key = f"{rtsp_url}_{resolution}_{codec}_{transport}_{line_position}_{count_direction}"
    
    # Check if counter already exists
    if key in active_counters:
        return active_counters[key]
    
    # Create new counter
    counter = CementBagCounter(
        rtsp_url=rtsp_url,
        model_path=model_path,
        line_position=line_position,
        count_direction=count_direction,
        resolution=resolution,
        codec=codec,
        transport=transport
    )
    
    # Start the counter
    counter.start()
    
    # Store in active counters
    active_counters[key] = counter
    
    return counter

def cleanup_counters():
    """Clean up inactive counters."""
    for key in list(active_counters.keys()):
        if not active_counters[key].running:
            del active_counters[key]
