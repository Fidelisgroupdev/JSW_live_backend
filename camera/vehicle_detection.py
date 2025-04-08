"""
Vehicle detection and counting module for warehouse cameras.
Uses YOLOv5 for vehicle detection and tracking.
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

# Vehicle classes in COCO dataset (used by YOLOv5)
VEHICLE_CLASSES = {
    2: 'car',
    3: 'motorcycle',
    5: 'bus',
    7: 'truck',
    8: 'forklift',  # Note: standard YOLO doesn't have forklift, we'll need to customize
}

# Warehouse-specific vehicle classes (can be customized)
WAREHOUSE_VEHICLES = {
    'forklift': 8,
    'truck': 7,
    'car': 2,
}

class VehicleDetector:
    """Vehicle detection and counting using YOLOv5."""
    
    def __init__(self, model_path=None, confidence=0.5, device='cpu'):
        """
        Initialize the vehicle detector.
        
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
        
        # Counting line (horizontal line at middle of frame by default)
        self.line_position = 0.5  # Position as fraction of frame height
        self.counted_ids = set()  # Track IDs that have been counted
        
        print(f"Vehicle detector initialized with confidence {confidence} on {device}")
    
    def detect_vehicles(self, frame):
        """
        Detect vehicles in a frame.
        
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
            # Only keep vehicle classes
            if cls_id in VEHICLE_CLASSES:
                x1, y1, x2, y2 = map(int, box)
                vehicle_type = VEHICLE_CLASSES[cls_id]
                detections.append([x1, y1, x2, y2, float(conf), cls_id, vehicle_type])
        
        return detections
    
    def track_vehicles(self, frame, detections):
        """
        Track vehicles across frames.
        
        Args:
            frame: OpenCV image
            detections: List of detections [x1, y1, x2, y2, conf, cls_id, cls_name]
            
        Returns:
            List of tracked objects with tracking IDs
        """
        height, width = frame.shape[:2]
        
        # Define counting line
        line_y = int(height * self.line_position)
        
        # Current objects being tracked
        current_objects = {}
        
        # Update existing trackers
        for obj_id, tracker in list(self.tracking_objects.items()):
            success, box = tracker.update(frame)
            if success:
                x, y, w, h = map(int, box)
                current_objects[obj_id] = {
                    'bbox': [x, y, x+w, y+h],
                    'center': (x + w//2, y + h//2),
                    'vehicle_type': self.tracking_objects[obj_id]['vehicle_type'],
                    'crossed_line': self.tracking_objects[obj_id]['crossed_line'],
                    'direction': self.tracking_objects[obj_id]['direction']
                }
                
                # Check if object has crossed the line
                center_y = current_objects[obj_id]['center'][1]
                prev_center_y = self.tracking_objects[obj_id]['center'][1]
                
                # Determine if object crossed the line in this frame
                if not current_objects[obj_id]['crossed_line']:
                    if (prev_center_y < line_y and center_y >= line_y) or \
                       (prev_center_y > line_y and center_y <= line_y):
                        current_objects[obj_id]['crossed_line'] = True
                        direction = 'in' if prev_center_y < line_y else 'out'
                        current_objects[obj_id]['direction'] = direction
                        self.counted_ids.add(obj_id)
        
        # Match new detections with existing objects or create new trackers
        for detection in detections:
            x1, y1, x2, y2, conf, cls_id, vehicle_type = detection
            center_x, center_y = (x1 + x2) // 2, (y1 + y2) // 2
            
            # Check if this detection matches any existing object
            matched = False
            for obj_id, obj in current_objects.items():
                bbox = obj['bbox']
                obj_center_x, obj_center_y = obj['center']
                
                # Calculate IoU (Intersection over Union)
                x_left = max(bbox[0], x1)
                y_top = max(bbox[1], y1)
                x_right = min(bbox[2], x2)
                y_bottom = min(bbox[3], y2)
                
                if x_right < x_left or y_bottom < y_top:
                    continue  # No overlap
                
                intersection = (x_right - x_left) * (y_bottom - y_top)
                area1 = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
                area2 = (x2 - x1) * (y2 - y1)
                iou = intersection / float(area1 + area2 - intersection)
                
                if iou > 0.5:  # If IoU is high enough, consider it the same object
                    matched = True
                    break
            
            if not matched:
                # Create a new tracker for this object
                tracker = cv2.TrackerCSRT_create()
                tracker.init(frame, (x1, y1, x2-x1, y2-y1))
                
                # Assign a new ID
                self.track_id += 1
                obj_id = self.track_id
                
                # Check if already crossing the line
                crossed_line = False
                direction = None
                
                self.tracking_objects[obj_id] = {
                    'tracker': tracker,
                    'bbox': [x1, y1, x2, y2],
                    'center': (center_x, center_y),
                    'vehicle_type': vehicle_type,
                    'crossed_line': crossed_line,
                    'direction': direction
                }
                
                current_objects[obj_id] = {
                    'bbox': [x1, y1, x2, y2],
                    'center': (center_x, center_y),
                    'vehicle_type': vehicle_type,
                    'crossed_line': crossed_line,
                    'direction': direction
                }
        
        # Update tracking objects for next frame
        self.tracking_objects = {
            obj_id: {
                'tracker': self.tracking_objects.get(obj_id, {}).get('tracker', None),
                'bbox': obj['bbox'],
                'center': obj['center'],
                'vehicle_type': obj['vehicle_type'],
                'crossed_line': obj['crossed_line'],
                'direction': obj['direction']
            }
            for obj_id, obj in current_objects.items()
        }
        
        return current_objects
    
    def draw_results(self, frame, tracked_objects):
        """
        Draw detection boxes, tracking IDs, and counting line on frame.
        
        Args:
            frame: OpenCV image
            tracked_objects: Dictionary of tracked objects
            
        Returns:
            Annotated frame
        """
        height, width = frame.shape[:2]
        line_y = int(height * self.line_position)
        
        # Draw counting line
        cv2.line(frame, (0, line_y), (width, line_y), (255, 0, 0), 2)
        
        # Count vehicles by type
        vehicle_counts = {}
        crossed_counts = {}
        
        for obj_id, obj in tracked_objects.items():
            bbox = obj['bbox']
            vehicle_type = obj['vehicle_type']
            crossed = obj['crossed_line']
            direction = obj['direction'] or 'unknown'
            
            # Update counts
            vehicle_counts[vehicle_type] = vehicle_counts.get(vehicle_type, 0) + 1
            if crossed:
                key = f"{vehicle_type}_{direction}"
                crossed_counts[key] = crossed_counts.get(key, 0) + 1
            
            # Draw bounding box
            color = (0, 255, 0) if crossed else (0, 165, 255)
            cv2.rectangle(frame, (bbox[0], bbox[1]), (bbox[2], bbox[3]), color, 2)
            
            # Draw ID and type
            label = f"ID:{obj_id} {vehicle_type}"
            if crossed:
                label += f" ({direction})"
            
            cv2.putText(frame, label, (bbox[0], bbox[1] - 10), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        
        # Draw vehicle count
        total_count = len(self.counted_ids)
        cv2.putText(frame, f"Vehicle count: {total_count}", (10, 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        
        # Draw counts by type
        y_pos = 70
        for vehicle_type, count in vehicle_counts.items():
            cv2.putText(frame, f"{vehicle_type}: {count}", (10, y_pos), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
            y_pos += 30
        
        return frame
    
    def process_frame(self, frame):
        """
        Process a single frame for vehicle detection and tracking.
        
        Args:
            frame: OpenCV image
            
        Returns:
            Tuple of (annotated_frame, tracked_objects)
        """
        # Detect vehicles
        detections = self.detect_vehicles(frame)
        
        # Track vehicles
        tracked_objects = self.track_vehicles(frame, detections)
        
        # Draw results
        annotated_frame = self.draw_results(frame.copy(), tracked_objects)
        
        return annotated_frame, tracked_objects
    
    def get_api_payload(self, camera_id, tracked_objects, frame=None):
        """
        Prepare payload for API submission.
        
        Args:
            camera_id: Camera ID
            tracked_objects: Dictionary of tracked objects
            frame: Optional frame to include as base64 image
            
        Returns:
            API payload dictionary
        """
        detections = []
        
        for obj_id, obj in tracked_objects.items():
            bbox = obj['bbox']
            detection = {
                'vehicle_type': obj['vehicle_type'],
                'confidence': 0.9,  # Placeholder for tracking confidence
                'bbox': bbox,
                'tracking_id': f"vehicle_{obj_id}",
                'crossed_line': obj['crossed_line'],
                'direction': obj['direction']
            }
            detections.append(detection)
        
        payload = {
            'camera_id': camera_id,
            'detections': detections
        }
        
        # Add frame data if provided
        if frame is not None:
            _, buffer = cv2.imencode('.jpg', frame)
            frame_data = base64.b64encode(buffer).decode('utf-8')
            payload['frame_data'] = frame_data
        
        return payload
    
    def submit_to_api(self, camera_id, tracked_objects, frame=None, api_url=None):
        """
        Submit detection results to API.
        
        Args:
            camera_id: Camera ID
            tracked_objects: Dictionary of tracked objects
            frame: Optional frame to include
            api_url: API endpoint URL
            
        Returns:
            API response
        """
        if api_url is None:
            api_url = 'http://127.0.0.1:8000/api/camera/process-vehicle-detection/'
        
        payload = self.get_api_payload(camera_id, tracked_objects, frame)
        
        try:
            response = requests.post(
                api_url,
                json=payload,
                headers={'Content-Type': 'application/json'}
            )
            return response.json()
        except Exception as e:
            print(f"API submission error: {e}")
            return None


def process_rtsp_stream(rtsp_url, camera_id, output_path=None, api_url=None, 
                       confidence=0.5, device='cpu', display=True):
    """
    Process RTSP stream for vehicle detection and counting.
    
    Args:
        rtsp_url: RTSP URL of the camera
        camera_id: Camera ID in the database
        output_path: Path to save output video (optional)
        api_url: API endpoint URL
        confidence: Detection confidence threshold
        device: Device to run inference on ('cpu' or 'cuda')
        display: Whether to display the output
    """
    # Initialize detector
    detector = VehicleDetector(confidence=confidence, device=device)
    
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
            annotated_frame, tracked_objects = detector.process_frame(frame)
            
            # Write frame if output path is provided
            if writer:
                writer.write(annotated_frame)
            
            # Display frame if requested
            if display:
                cv2.imshow('Vehicle Detection', annotated_frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
            
            # Submit to API at regular intervals
            if api_url and frame_count % api_submit_interval == 0:
                detector.submit_to_api(camera_id, tracked_objects, frame, api_url)
            
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
        print(f"Detected {len(detector.counted_ids)} vehicles crossing the line")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Vehicle detection and counting from RTSP stream")
    parser.add_argument("--rtsp_url", required=True, help="RTSP URL of the camera")
    parser.add_argument("--camera_id", type=int, required=True, help="Camera ID in the database")
    parser.add_argument("--output", help="Path to save output video")
    parser.add_argument("--api_url", default="http://127.0.0.1:8000/api/camera/process-vehicle-detection/",
                       help="API endpoint URL")
    parser.add_argument("--confidence", type=float, default=0.5, help="Detection confidence threshold")
    parser.add_argument("--device", default="cpu", choices=["cpu", "cuda"], help="Device to run inference on")
    parser.add_argument("--no_display", action="store_true", help="Don't display output")
    
    args = parser.parse_args()
    
    process_rtsp_stream(
        rtsp_url=args.rtsp_url,
        camera_id=args.camera_id,
        output_path=args.output,
        api_url=args.api_url,
        confidence=args.confidence,
        device=args.device,
        display=not args.no_display
    )
