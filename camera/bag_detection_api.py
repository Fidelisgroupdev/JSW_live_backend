"""
API endpoints for cement bag detection and line crossing functionality.
"""
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
import json
import base64
import cv2
import numpy as np
from datetime import datetime
import os
from django.conf import settings
from django.utils import timezone

from .models import Camera, DetectionEvent
from inventory.models import Cluster, CementBag, Movement

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def process_bag_detection(request):
    """
    Process cement bag detection results from the detection module.
    
    Request body:
    {
        "camera_id": 1,
        "timestamp": "2025-04-08T14:00:00",
        "objects": [
            {
                "track_id": 1,
                "class_id": 0,
                "class_name": "cement_bag",
                "confidence": 0.85,
                "box": [x1, y1, x2, y2],
                "center": [cx, cy]
            }
        ],
        "line_crossings": [
            {
                "track_id": 1,
                "line_id": "line1",
                "timestamp": "2025-04-08T14:00:05",
                "direction": "left_to_right",
                "cluster_from": 1,
                "cluster_to": 2,
                "confidence": 0.85
            }
        ],
        "frame": "base64_encoded_image"
    }
    """
    try:
        data = request.data
        camera_id = data.get('camera_id')
        timestamp = data.get('timestamp')
        objects = data.get('objects', [])
        line_crossings = data.get('line_crossings', [])
        frame_base64 = data.get('frame')
        
        # Validate camera
        try:
            camera = Camera.objects.get(id=camera_id)
        except Camera.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': f'Camera with ID {camera_id} not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Process line crossings
        processed_crossings = []
        for crossing in line_crossings:
            # Get clusters
            source_cluster_id = crossing.get('cluster_from')
            dest_cluster_id = crossing.get('cluster_to')
            
            source_cluster = None
            dest_cluster = None
            
            if source_cluster_id:
                try:
                    source_cluster = Cluster.objects.get(id=source_cluster_id)
                except Cluster.DoesNotExist:
                    pass
            
            if dest_cluster_id:
                try:
                    dest_cluster = Cluster.objects.get(id=dest_cluster_id)
                except Cluster.DoesNotExist:
                    pass
            
            # Determine event type
            if source_cluster is None and dest_cluster is not None:
                event_type = 'entry'
            elif source_cluster is not None and dest_cluster is None:
                event_type = 'exit'
            elif source_cluster is not None and dest_cluster is not None:
                event_type = 'movement'
            else:
                event_type = 'unknown'
            
            # Save detection event
            track_id = crossing.get('track_id')
            confidence = crossing.get('confidence', 0.0)
            
            # Find the object data for this track_id
            obj_data = next((obj for obj in objects if obj.get('track_id') == track_id), None)
            
            if obj_data:
                box = obj_data.get('box', [0, 0, 0, 0])
                x_min, y_min, x_max, y_max = box
                
                # Save image snapshot if frame is provided
                image_path = None
                if frame_base64:
                    try:
                        # Decode base64 image
                        img_data = base64.b64decode(frame_base64)
                        nparr = np.frombuffer(img_data, np.uint8)
                        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                        
                        # Crop to the bounding box with some padding
                        padding = 50
                        y_min_pad = max(0, y_min - padding)
                        y_max_pad = min(frame.shape[0], y_max + padding)
                        x_min_pad = max(0, x_min - padding)
                        x_max_pad = min(frame.shape[1], x_max + padding)
                        
                        cropped = frame[y_min_pad:y_max_pad, x_min_pad:x_max_pad]
                        
                        # Save the cropped image
                        timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
                        filename = f'bag_detection_{camera_id}_{track_id}_{timestamp_str}.jpg'
                        image_path = os.path.join('detection_events', filename)
                        full_path = os.path.join(settings.MEDIA_ROOT, image_path)
                        
                        # Ensure directory exists
                        os.makedirs(os.path.dirname(full_path), exist_ok=True)
                        
                        # Save image
                        cv2.imwrite(full_path, cropped)
                    except Exception as e:
                        print(f"Error saving image: {e}")
                
                # Create detection event
                detection_event = DetectionEvent.objects.create(
                    camera=camera,
                    event_type=event_type,
                    confidence_score=confidence,
                    x_min=x_min,
                    y_min=y_min,
                    x_max=x_max,
                    y_max=y_max,
                    source_cluster=source_cluster,
                    destination_cluster=dest_cluster,
                    processed=False
                )
                
                if image_path:
                    detection_event.image_snapshot = image_path
                    detection_event.save()
                
                # Handle inventory updates based on event type
                if event_type == 'entry':
                    # New bag entering a cluster
                    if dest_cluster:
                        # Create a new cement bag (with auto-generated barcode)
                        barcode = f"BAG{timezone.now().strftime('%Y%m%d%H%M%S')}{track_id}"
                        bag = CementBag.objects.create(
                            barcode=barcode,
                            manufacture_date=timezone.now().date(),
                            entry_date=timezone.now(),
                            cluster=dest_cluster,
                            status='available'
                        )
                        
                        # Create movement record
                        movement = Movement.objects.create(
                            destination_cluster=dest_cluster,
                            bag=bag,
                            camera=camera,
                            confidence_score=confidence,
                            notes=f"Auto-detected entry via camera {camera.name}"
                        )
                        
                        # Update detection event
                        detection_event.resulting_movement = movement
                        detection_event.processed = True
                        detection_event.save()
                
                elif event_type == 'movement':
                    # Bag moving between clusters
                    if source_cluster and dest_cluster:
                        # Find the most recent bag in the source cluster
                        # In a real system, you'd need a more robust way to identify which specific bag is moving
                        bags = CementBag.objects.filter(cluster=source_cluster, status='available')
                        if bags.exists():
                            # Take the oldest bag (FIFO)
                            bag = bags.order_by('entry_date').first()
                            
                            # Create movement record
                            movement = Movement.objects.create(
                                source_cluster=source_cluster,
                                destination_cluster=dest_cluster,
                                bag=bag,
                                camera=camera,
                                confidence_score=confidence,
                                notes=f"Auto-detected movement via camera {camera.name}"
                            )
                            
                            # Update detection event
                            detection_event.resulting_movement = movement
                            detection_event.processed = True
                            detection_event.save()
                
                elif event_type == 'exit':
                    # Bag exiting a cluster (leaving the warehouse)
                    if source_cluster:
                        # Find the most recent bag in the source cluster
                        bags = CementBag.objects.filter(cluster=source_cluster, status='available')
                        if bags.exists():
                            # Take the oldest bag (FIFO)
                            bag = bags.order_by('entry_date').first()
                            
                            # Create movement record for exit
                            movement = Movement.objects.create(
                                source_cluster=source_cluster,
                                destination_cluster=None,  # No destination for exit
                                bag=bag,
                                camera=camera,
                                confidence_score=confidence,
                                notes=f"Auto-detected exit via camera {camera.name}"
                            )
                            
                            # Update bag status
                            bag.status = 'sold'
                            bag.save()
                            
                            # Update detection event
                            detection_event.resulting_movement = movement
                            detection_event.processed = True
                            detection_event.save()
                
                processed_crossings.append({
                    'track_id': track_id,
                    'event_type': event_type,
                    'detection_event_id': detection_event.id,
                    'processed': detection_event.processed
                })
        
        return JsonResponse({
            'success': True,
            'message': f'Processed {len(processed_crossings)} line crossings',
            'processed_crossings': processed_crossings
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_cluster_lines(request, camera_id):
    """
    Get the line definitions for a specific camera.
    These lines define the boundaries between clusters for detection.
    """
    try:
        camera = Camera.objects.get(id=camera_id)
        
        # Get clusters monitored by this camera
        clusters = camera.coverage_clusters.all()
        
        # In a real implementation, you would store line definitions in the database
        # For now, we'll generate some example lines based on the clusters
        
        lines = []
        
        # Create horizontal lines between clusters
        sorted_clusters = sorted(clusters, key=lambda c: (c.location_x, c.location_y))
        
        # Get camera resolution
        width = camera.resolution_width
        height = camera.resolution_height
        
        # Create lines between adjacent clusters
        for i in range(len(sorted_clusters) - 1):
            cluster1 = sorted_clusters[i]
            cluster2 = sorted_clusters[i + 1]
            
            # Create a line between these clusters
            # In a real implementation, you would calculate the actual position based on
            # camera calibration and cluster positions in the warehouse
            
            # For now, we'll create evenly spaced horizontal lines
            y_position = int(height * (i + 1) / (len(sorted_clusters)))
            
            line = {
                'id': f'line_{cluster1.id}_{cluster2.id}',
                'start': (0, y_position),
                'end': (width, y_position),
                'cluster_from': cluster1.id,
                'cluster_to': cluster2.id
            }
            
            lines.append(line)
        
        return JsonResponse({
            'success': True,
            'camera_id': camera_id,
            'lines': lines
        })
    
    except Camera.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': f'Camera with ID {camera_id} not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def set_cluster_lines(request, camera_id):
    """
    Set custom line definitions for a specific camera.
    
    Request body:
    {
        "lines": [
            {
                "id": "line1",
                "start": [x1, y1],
                "end": [x2, y2],
                "cluster_from": 1,
                "cluster_to": 2
            }
        ]
    }
    """
    try:
        camera = Camera.objects.get(id=camera_id)
        data = request.data
        lines = data.get('lines', [])
        
        # In a real implementation, you would store these lines in the database
        # For now, we'll just return success
        
        return JsonResponse({
            'success': True,
            'message': f'Set {len(lines)} lines for camera {camera_id}',
            'lines': lines
        })
    
    except Camera.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': f'Camera with ID {camera_id} not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_bag_detection(request, camera_id):
    """
    Start the cement bag detection process for a camera.
    
    Request body:
    {
        "detection_threshold": 0.5,  # Optional
        "device": "cpu"  # Optional, "cpu" or "cuda"
    }
    """
    try:
        camera = Camera.objects.get(id=camera_id)
        data = request.data
        
        detection_threshold = data.get('detection_threshold', camera.detection_threshold)
        device = data.get('device', 'cpu')
        
        # In a real implementation, you would start a background process or task
        # to run the cement_bag_detection.py script for this camera
        
        # For now, we'll just update the camera status
        camera.status = 'active'
        camera.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Started bag detection for camera {camera.name}',
            'camera_id': camera_id,
            'detection_threshold': detection_threshold,
            'device': device
        })
    
    except Camera.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': f'Camera with ID {camera_id} not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def stop_bag_detection(request, camera_id):
    """
    Stop the cement bag detection process for a camera.
    """
    try:
        camera = Camera.objects.get(id=camera_id)
        
        # In a real implementation, you would stop the background process
        
        # For now, we'll just update the camera status
        camera.status = 'inactive'
        camera.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Stopped bag detection for camera {camera.name}',
            'camera_id': camera_id
        })
    
    except Camera.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': f'Camera with ID {camera_id} not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
