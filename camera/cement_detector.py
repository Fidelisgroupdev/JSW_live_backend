"""
Cement bag detector using YOLOv5 model.
"""
import os
import cv2
import torch
import numpy as np
import time
from pathlib import Path

class CementBagDetector:
    """
    Detector for cement bags using YOLOv5.
    """
    def __init__(self, model_path=None, conf_threshold=0.25, iou_threshold=0.45):
        """
        Initialize the cement bag detector.
        
        Args:
            model_path: Path to the YOLOv5 model weights (.pt file)
            conf_threshold: Confidence threshold for detections
            iou_threshold: IoU threshold for NMS
        """
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        
        # Use default model path if not specified
        if model_path is None:
            base_dir = Path(__file__).resolve().parent.parent
            model_path = os.path.join(base_dir, 'models', 'cement_bag_model.pt')
        
        # Load YOLOv5 model
        try:
            self.model = torch.hub.load('ultralytics/yolov5', 'custom', path=model_path)
            self.model.conf = self.conf_threshold
            self.model.iou = self.iou_threshold
            self.model.classes = [0]  # Only detect cement bags (class 0)
            self.model.eval()
            self.loaded = True
            print(f"Loaded cement bag detection model from {model_path}")
        except Exception as e:
            print(f"Failed to load YOLOv5 model: {str(e)}")
            # Fallback to loading a default YOLOv5 model
            try:
                self.model = torch.hub.load('ultralytics/yolov5', 'yolov5s')
                self.model.conf = self.conf_threshold
                self.model.iou = self.iou_threshold
                self.loaded = True
                print("Loaded default YOLOv5s model")
            except Exception as e:
                print(f"Failed to load default model: {str(e)}")
                self.loaded = False
    
    def detect(self, frame):
        """
        Detect cement bags in a frame.
        
        Args:
            frame: OpenCV image (numpy array)
            
        Returns:
            detections: List of detections [x1, y1, x2, y2, confidence, class_id]
            annotated_frame: Frame with bounding boxes drawn
        """
        if not self.loaded or frame is None:
            return [], frame
        
        # Run inference
        results = self.model(frame)
        
        # Process results
        detections = results.xyxy[0].cpu().numpy()  # xyxy format: [x1, y1, x2, y2, confidence, class_id]
        
        # Draw bounding boxes on a copy of the frame
        annotated_frame = frame.copy()
        for det in detections:
            x1, y1, x2, y2, conf, class_id = det
            # Only process cement bag class (usually class 0)
            if class_id == 0:  
                # Draw bounding box
                cv2.rectangle(annotated_frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
                # Add label
                label = f"Cement Bag: {conf:.2f}"
                cv2.putText(annotated_frame, label, (int(x1), int(y1) - 10), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        
        return detections, annotated_frame
    
    def count_bags(self, frame, line_y=None, direction='both'):
        """
        Count cement bags in a frame, optionally counting only bags crossing a line.
        
        Args:
            frame: OpenCV image (numpy array)
            line_y: Y-coordinate of counting line (if None, counts all bags in frame)
            direction: 'up', 'down', or 'both' for counting direction
            
        Returns:
            count: Number of bags detected
            annotated_frame: Frame with bounding boxes and count drawn
        """
        detections, annotated_frame = self.detect(frame)
        
        # Count bags
        if line_y is None:
            # Count all bags in frame
            count = len([d for d in detections if d[5] == 0])  # Class 0 = cement bag
        else:
            # Count bags crossing the line
            count = 0
            for det in detections:
                if det[5] != 0:  # Skip if not a cement bag
                    continue
                    
                x1, y1, x2, y2 = map(int, det[:4])
                center_y = (y1 + y2) / 2
                
                # Check if center crosses the line based on direction
                if direction == 'up' and center_y < line_y:
                    count += 1
                elif direction == 'down' and center_y > line_y:
                    count += 1
                elif direction == 'both':
                    count += 1
        
        # Draw counting line if specified
        if line_y is not None:
            cv2.line(annotated_frame, (0, line_y), (frame.shape[1], line_y), (0, 0, 255), 2)
            
        # Draw count on frame
        cv2.putText(annotated_frame, f"Bag Count: {count}", (10, 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        
        return count, annotated_frame
