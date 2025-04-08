"""
Cement bag detection and counting module for warehouse cameras.
Uses YOLOv5 for bag detection and tracking with line crossing detection.
"""
import cv2
import numpy as np
import torch
import time
import requests
import base64
import json
import os
import argparse
from datetime import datetime
from pathlib import Path

# Set up paths
BASE_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = BASE_DIR / 'models'
os.makedirs(MODELS_DIR, exist_ok=True)

# YOLOv5 model download URL
YOLOV5_URL = "https://github.com/ultralytics/yolov5/releases/download/v6.1/yolov5s.pt"
MODEL_PATH = MODELS_DIR / 'yolov5s.pt'

# Cement bag class ID (we'll use custom class ID 0 for cement bags)
# Standard YOLO doesn't have cement bags, so we'll need a custom model or adapt detection
BAG_CLASS_ID = 0
BAG_CLASS_NAME = 'cement_bag'

class CementBagDetector:
    """Cement bag detection and counting using YOLOv5 with line crossing detection."""
    
    def __init__(self, model_path=None, confidence=0.5, device='cpu'):
        """
        Initialize the cement bag detector.
        
        Args:
            model_path: Path to YOLOv5 model file
            confidence: Detection confidence threshold
            device: Device to run inference on ('cpu' or 'cuda')
        """
        self.confidence = confidence
        self.device = device
        
        # Download model if not exists
        if model_path is None:
            model_path = MODEL_PATH
            if not os.path.exists(model_path):
                print(f"Downloading YOLOv5 model to {model_path}...")
                import urllib.request
                urllib.request.urlretrieve(YOLOV5_URL, model_path)
        
        # Load YOLOv5 model
        self.model = torch.hub.load('ultralytics/yolov5', 'custom', path=model_path)
        self.model.conf = confidence  # Set confidence threshold
        self.model.to(device)  # Move model to specified device
        
        # Initialize tracker
        self.tracker = cv2.TrackerCSRT_create()
        self.tracking_objects = {}
        self.track_id = 0
        
        # Counting lines (we'll have multiple lines for different clusters)
        self.counting_lines = []  # Will be set based on camera view and clusters
        self.counted_ids = {}  # Track IDs that have been counted for each line
        
        # Clusters information
        self.clusters = {}  # Will be populated with cluster info
        
        print(f"Cement bag detector initialized with confidence {confidence} on {device}")
    
    def set_counting_lines(self, lines):
        """
        Set the counting lines for detection.
        
        Args:
            lines: List of dictionaries with line info:
                  [{'id': 'line1', 'start': (x1, y1), 'end': (x2, y2), 
                    'cluster_from': cluster_id, 'cluster_to': cluster_id}]
        """
        self.counting_lines = lines
        # Initialize counted IDs for each line
        for line in lines:
            self.counted_ids[line['id']] = set()
    
    def set_clusters(self, clusters):
        """
        Set the clusters information.
        
        Args:
            clusters: Dictionary of cluster info {cluster_id: cluster_object}
        """
        self.clusters = clusters
    
    def detect_bags(self, frame):
        """
        Detect cement bags in a frame.
        
        Args:
            frame: OpenCV image (numpy array)
            
        Returns:
            List of detections [x1, y1, x2, y2, confidence, class_id, class_name]
        """
        # Run inference
        results = self.model(frame)
        
        # Process results
        detections = []
        for *box, conf, cls_id in results.xyxy[0].cpu().numpy():
            cls_id = int(cls_id)
            # For now, we'll use the standard model and adapt it
            # In a real scenario, you'd use a custom-trained model for cement bags
            
            # Look for boxes (class 73 in COCO) or custom class if using a fine-tuned model
            if cls_id == 73 or cls_id == BAG_CLASS_ID:  # box or cement_bag
                x1, y1, x2, y2 = map(int, box)
                detections.append([x1, y1, x2, y2, float(conf), BAG_CLASS_ID, BAG_CLASS_NAME])
        
        return detections
    
    def track_bags(self, frame, detections):
        """
        Track cement bags across frames and detect line crossings.
        
        Args:
            frame: OpenCV image
            detections: List of detections [x1, y1, x2, y2, conf, cls_id, cls_name]
            
        Returns:
            Dictionary of tracked objects with line crossing events
        """
        height, width = frame.shape[:2]
        
        # Current objects being tracked
        current_objects = {}
        line_crossings = []
        
        # Update existing trackers
        for obj_id, tracker_info in list(self.tracking_objects.items()):
            tracker = tracker_info['tracker']
            success, box = tracker.update(frame)
            if success:
                x, y, w, h = map(int, box)
                current_objects[obj_id] = {
                    'box': (x, y, w, h),
                    'center': (x + w//2, y + h//2),
                    'last_seen': time.time(),
                    'class_id': tracker_info['class_id'],
                    'class_name': tracker_info['class_name'],
                    'confidence': tracker_info['confidence'],
                    'tracker': tracker,
                    'trajectory': tracker_info['trajectory'] + [(x + w//2, y + h//2)]
                }
                
                # Check for line crossings
                center_point = current_objects[obj_id]['center']
                prev_point = tracker_info['trajectory'][-1] if tracker_info['trajectory'] else center_point
                
                for line in self.counting_lines:
                    line_id = line['id']
                    line_start, line_end = line['start'], line['end']
                    
                    # Check if this object has already been counted for this line
                    if obj_id in self.counted_ids[line_id]:
                        continue
                    
                    # Check if the object crossed the line
                    if self._check_line_crossing(prev_point, center_point, line_start, line_end):
                        # Determine direction of crossing
                        direction = self._determine_crossing_direction(prev_point, center_point, line_start, line_end)
                        
                        # Record the crossing
                        crossing_event = {
                            'track_id': obj_id,
                            'line_id': line_id,
                            'timestamp': time.time(),
                            'direction': direction,
                            'cluster_from': line['cluster_from'] if direction == 'left_to_right' else line['cluster_to'],
                            'cluster_to': line['cluster_to'] if direction == 'left_to_right' else line['cluster_from'],
                            'confidence': current_objects[obj_id]['confidence'],
                            'center_point': center_point
                        }
                        
                        line_crossings.append(crossing_event)
                        self.counted_ids[line_id].add(obj_id)
                        
                        print(f"Bag {obj_id} crossed line {line_id} from {crossing_event['cluster_from']} to {crossing_event['cluster_to']}")
            else:
                # Remove tracker if it's lost
                pass
        
        # Clean up old trackers
        current_time = time.time()
        for obj_id in list(self.tracking_objects.keys()):
            if obj_id not in current_objects:
                # Object lost, remove it
                del self.tracking_objects[obj_id]
        
        # Create new trackers for untracked detections
        for x1, y1, x2, y2, conf, cls_id, cls_name in detections:
            # Check if this detection overlaps with any existing tracked object
            is_tracked = False
            for obj_id, obj_info in current_objects.items():
                x, y, w, h = obj_info['box']
                # Calculate IoU between this detection and existing tracked object
                iou = self._calculate_iou((x1, y1, x2, y2), (x, y, x+w, y+h))
                if iou > 0.5:  # If significant overlap
                    is_tracked = True
                    break
            
            if not is_tracked:
                # Create a new tracker
                tracker = cv2.TrackerCSRT_create()
                tracker.init(frame, (x1, y1, x2-x1, y2-y1))
                
                # Assign a new ID
                self.track_id += 1
                obj_id = self.track_id
                
                # Store tracker info
                center_x, center_y = (x1 + x2) // 2, (y1 + y2) // 2
                self.tracking_objects[obj_id] = {
                    'tracker': tracker,
                    'box': (x1, y1, x2-x1, y2-y1),
                    'center': (center_x, center_y),
                    'last_seen': current_time,
                    'class_id': cls_id,
                    'class_name': cls_name,
                    'confidence': conf,
                    'trajectory': [(center_x, center_y)]
                }
                
                # Add to current objects
                current_objects[obj_id] = self.tracking_objects[obj_id]
        
        return current_objects, line_crossings
    
    def _check_line_crossing(self, p1, p2, line_start, line_end):
        """
        Check if a moving point (from p1 to p2) crosses a line (line_start to line_end).
        
        Returns:
            True if the point crossed the line, False otherwise
        """
        def ccw(a, b, c):
            return (c[1] - a[1]) * (b[0] - a[0]) > (b[1] - a[1]) * (c[0] - a[0])
        
        # Check if the line segments intersect
        return ccw(p1, line_start, line_end) != ccw(p2, line_start, line_end) and \
               ccw(p1, p2, line_start) != ccw(p1, p2, line_end)
    
    def _determine_crossing_direction(self, p1, p2, line_start, line_end):
        """
        Determine the direction of crossing (left to right or right to left).
        
        Returns:
            'left_to_right' or 'right_to_left'
        """
        # Calculate the side of the line for both points
        def side_of_line(point, line_start, line_end):
            return (point[0] - line_start[0]) * (line_end[1] - line_start[1]) - \
                   (point[1] - line_start[1]) * (line_end[0] - line_start[0])
        
        side1 = side_of_line(p1, line_start, line_end)
        side2 = side_of_line(p2, line_start, line_end)
        
        if side1 < 0 and side2 >= 0:
            return 'left_to_right'
        else:
            return 'right_to_left'
    
    def _calculate_iou(self, box1, box2):
        """
        Calculate Intersection over Union (IoU) between two bounding boxes.
        
        Args:
            box1: (x1, y1, x2, y2)
            box2: (x1, y1, x2, y2)
            
        Returns:
            IoU value (0.0 to 1.0)
        """
        # Calculate intersection area
        x_left = max(box1[0], box2[0])
        y_top = max(box1[1], box2[1])
        x_right = min(box1[2], box2[2])
        y_bottom = min(box1[3], box2[3])
        
        if x_right < x_left or y_bottom < y_top:
            return 0.0
        
        intersection_area = (x_right - x_left) * (y_bottom - y_top)
        
        # Calculate union area
        box1_area = (box1[2] - box1[0]) * (box1[3] - box1[1])
        box2_area = (box2[2] - box2[0]) * (box2[3] - box2[1])
        union_area = box1_area + box2_area - intersection_area
        
        return intersection_area / union_area if union_area > 0 else 0.0
    
    def draw_results(self, frame, tracked_objects, line_crossings=None):
        """
        Draw detection boxes, tracking IDs, counting lines, and crossing events on frame.
        
        Args:
            frame: OpenCV image
            tracked_objects: Dictionary of tracked objects
            line_crossings: List of line crossing events
            
        Returns:
            Annotated frame
        """
        # Draw counting lines
        for line in self.counting_lines:
            start_point = line['start']
            end_point = line['end']
            cv2.line(frame, start_point, end_point, (0, 255, 0), 2)
            
            # Draw line label
            mid_x = (start_point[0] + end_point[0]) // 2
            mid_y = (start_point[1] + end_point[1]) // 2
            cv2.putText(frame, line['id'], (mid_x, mid_y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        # Draw tracked objects
        for obj_id, obj_info in tracked_objects.items():
            x, y, w, h = obj_info['box']
            center = obj_info['center']
            
            # Draw bounding box
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
            
            # Draw ID and class
            label = f"ID:{obj_id} {obj_info['class_name']}"
            cv2.putText(frame, label, (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            
            # Draw trajectory
            trajectory = obj_info['trajectory']
            if len(trajectory) > 1:
                for i in range(1, len(trajectory)):
                    cv2.line(frame, trajectory[i-1], trajectory[i], (0, 0, 255), 2)
        
        # Draw crossing events
        if line_crossings:
            for event in line_crossings:
                center_point = event['center_point']
                cv2.circle(frame, center_point, 10, (255, 0, 0), -1)
                
                # Draw crossing info
                label = f"Crossing: {event['cluster_from']} -> {event['cluster_to']}"
                cv2.putText(frame, label, (center_point[0], center_point[1]-20), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
        
        # Draw counts
        y_pos = 30
        for line_id, counted_ids in self.counted_ids.items():
            count_text = f"{line_id}: {len(counted_ids)} bags"
            cv2.putText(frame, count_text, (10, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            y_pos += 30
        
        return frame
    
    def process_frame(self, frame):
        """
        Process a single frame for cement bag detection, tracking, and line crossing.
        
        Args:
            frame: OpenCV image
            
        Returns:
            Tuple of (annotated_frame, tracked_objects, line_crossings)
        """
        # Detect bags
        detections = self.detect_bags(frame)
        
        # Track bags and detect line crossings
        tracked_objects, line_crossings = self.track_bags(frame, detections)
        
        # Draw results
        annotated_frame = self.draw_results(frame.copy(), tracked_objects, line_crossings)
        
        return annotated_frame, tracked_objects, line_crossings
    
    def get_api_payload(self, camera_id, tracked_objects, line_crossings, frame=None):
        """
        Prepare payload for API submission.
        
        Args:
            camera_id: Camera ID
            tracked_objects: Dictionary of tracked objects
            line_crossings: List of line crossing events
            frame: Optional frame to include as base64 image
            
        Returns:
            API payload dictionary
        """
        # Convert frame to base64 if provided
        frame_base64 = None
        if frame is not None:
            _, buffer = cv2.imencode('.jpg', frame)
            frame_base64 = base64.b64encode(buffer).decode('utf-8')
        
        # Prepare payload
        payload = {
            'camera_id': camera_id,
            'timestamp': datetime.now().isoformat(),
            'objects': [],
            'line_crossings': [],
            'frame': frame_base64
        }
        
        # Add tracked objects
        for obj_id, obj_info in tracked_objects.items():
            x, y, w, h = obj_info['box']
            payload['objects'].append({
                'track_id': obj_id,
                'class_id': obj_info['class_id'],
                'class_name': obj_info['class_name'],
                'confidence': obj_info['confidence'],
                'box': [x, y, x+w, y+h],
                'center': obj_info['center']
            })
        
        # Add line crossings
        for event in line_crossings:
            payload['line_crossings'].append({
                'track_id': event['track_id'],
                'line_id': event['line_id'],
                'timestamp': datetime.fromtimestamp(event['timestamp']).isoformat(),
                'direction': event['direction'],
                'cluster_from': event['cluster_from'],
                'cluster_to': event['cluster_to'],
                'confidence': event['confidence']
            })
        
        return payload
    
    def submit_to_api(self, camera_id, tracked_objects, line_crossings, frame=None, api_url=None):
        """
        Submit detection and line crossing results to API.
        
        Args:
            camera_id: Camera ID
            tracked_objects: Dictionary of tracked objects
            line_crossings: List of line crossing events
            frame: Optional frame to include
            api_url: API endpoint URL
            
        Returns:
            API response
        """
        if not api_url:
            api_url = "http://127.0.0.1:8000/api/camera/process-bag-detection/"
        
        payload = self.get_api_payload(camera_id, tracked_objects, line_crossings, frame)
        
        try:
            response = requests.post(api_url, json=payload)
            return response.json()
        except Exception as e:
            print(f"Error submitting to API: {e}")
            return {'error': str(e)}


def process_rtsp_stream(rtsp_url, camera_id, cluster_lines=None, output_path=None, 
                       api_url=None, confidence=0.5, device='cpu', display=True):
    """
    Process RTSP stream for cement bag detection, tracking, and line crossing.
    
    Args:
        rtsp_url: RTSP URL of the camera
        camera_id: Camera ID in the database
        cluster_lines: List of line definitions for crossing detection
        output_path: Path to save output video (optional)
        api_url: API endpoint URL
        confidence: Detection confidence threshold
        device: Device to run inference on ('cpu' or 'cuda')
        display: Whether to display the output
    """
    # Initialize detector
    detector = CementBagDetector(confidence=confidence, device=device)
    
    # Set counting lines if provided
    if cluster_lines:
        detector.set_counting_lines(cluster_lines)
    else:
        # Default horizontal line in the middle
        def_lines = [{
            'id': 'default_line',
            'start': (0, 360),
            'end': (1280, 360),
            'cluster_from': None,
            'cluster_to': None
        }]
        detector.set_counting_lines(def_lines)
    
    # Open RTSP stream
    print(f"Connecting to RTSP stream: {rtsp_url}")
    cap = cv2.VideoCapture(rtsp_url)
    
    if not cap.isOpened():
        print(f"Error: Could not open RTSP stream: {rtsp_url}")
        return
    
    # Get video properties
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    
    # Initialize video writer if output path is provided
    writer = None
    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
    
    # Process frames
    frame_count = 0
    start_time = time.time()
    api_submit_interval = 10  # Submit to API every 10 frames
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("End of stream or error reading frame")
                break
            
            # Process frame
            annotated_frame, tracked_objects, line_crossings = detector.process_frame(frame)
            
            # Write frame if output path is provided
            if writer:
                writer.write(annotated_frame)
            
            # Display frame if requested
            if display:
                cv2.imshow('Cement Bag Detection', annotated_frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
            
            # Submit to API if there are line crossings or at regular intervals
            if api_url and (line_crossings or frame_count % api_submit_interval == 0):
                detector.submit_to_api(camera_id, tracked_objects, line_crossings, frame, api_url)
            
            frame_count += 1
            
            # Print stats every 100 frames
            if frame_count % 100 == 0:
                elapsed_time = time.time() - start_time
                fps = frame_count / elapsed_time
                print(f"Processed {frame_count} frames at {fps:.2f} FPS")
    
    finally:
        # Release resources
        cap.release()
        if writer:
            writer.release()
        cv2.destroyAllWindows()
        
        print(f"Processed {frame_count} frames")
        print(f"Detected {sum(len(ids) for ids in detector.counted_ids.values())} bag crossings")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cement bag detection and counting from RTSP stream")
    parser.add_argument("--rtsp_url", required=True, help="RTSP URL of the camera")
    parser.add_argument("--camera_id", type=int, required=True, help="Camera ID in the database")
    parser.add_argument("--output", help="Path to save output video")
    parser.add_argument("--api_url", default="http://127.0.0.1:8000/api/camera/process-bag-detection/",
                       help="API endpoint URL")
    parser.add_argument("--confidence", type=float, default=0.5, help="Detection confidence threshold")
    parser.add_argument("--device", default="cpu", choices=["cpu", "cuda"], help="Device to run inference on")
    parser.add_argument("--no_display", action="store_true", help="Don't display output")
    
    args = parser.parse_args()
    
    # Example cluster lines (would be loaded from database in production)
    example_lines = [
        {
            'id': 'line1',
            'start': (0, 360),
            'end': (640, 360),
            'cluster_from': 1,  # Cluster ID
            'cluster_to': 2     # Cluster ID
        },
        {
            'id': 'line2',
            'start': (640, 360),
            'end': (1280, 360),
            'cluster_from': 2,  # Cluster ID
            'cluster_to': 3     # Cluster ID
        }
    ]
    
    process_rtsp_stream(
        rtsp_url=args.rtsp_url,
        camera_id=args.camera_id,
        cluster_lines=example_lines,
        output_path=args.output,
        api_url=args.api_url,
        confidence=args.confidence,
        device=args.device,
        display=not args.no_display
    )
