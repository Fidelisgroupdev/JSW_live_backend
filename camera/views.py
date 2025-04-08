from django.shortcuts import render
from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
import cv2
import numpy as np
import threading
import time
from django.utils import timezone
from django.http import JsonResponse, HttpResponse

from .models import Camera, CameraCalibration, DetectionEvent, VehicleDetectionEvent
from .serializers import (
    CameraSerializer, CameraDetailSerializer, CameraCalibrationSerializer,
    DetectionEventSerializer, RTSPStreamSerializer, CameraStatusUpdateSerializer,
    HikvisionCameraSerializer, VehicleDetectionEventSerializer
)
from inventory.models import Cluster
from .utils import HikvisionCameraIntegration, extract_camera_details_from_hikvision
from .rtsp_proxy import rtsp_manager

class CameraViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing cameras.
    """
    queryset = Camera.objects.all()
    serializer_class = CameraSerializer
    permission_classes = [AllowAny]  # Allow unauthenticated access for testing
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'location_description']
    ordering_fields = ['name', 'status', 'created_at']
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return CameraDetailSerializer
        elif self.action == 'test_connection':
            return RTSPStreamSerializer
        elif self.action == 'update_status':
            return CameraStatusUpdateSerializer
        elif self.action == 'add_hikvision_camera':
            return HikvisionCameraSerializer
        return CameraSerializer
    
    @action(detail=True, methods=['get'])
    def events(self, request, pk=None):
        """
        Return detection events for a specific camera.
        """
        camera = self.get_object()
        events = camera.detection_events.all().order_by('-timestamp')
        
        # Apply filters if provided
        event_type = request.query_params.get('event_type', None)
        if event_type:
            events = events.filter(event_type=event_type)
            
        # Filter by processed status if provided
        processed = request.query_params.get('processed', None)
        if processed is not None:
            processed = processed.lower() == 'true'
            events = events.filter(processed=processed)
            
        # Filter by confidence score if provided
        min_confidence = request.query_params.get('min_confidence', None)
        if min_confidence:
            events = events.filter(confidence_score__gte=float(min_confidence))
            
        page = self.paginate_queryset(events)
        if page is not None:
            serializer = DetectionEventSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
            
        serializer = DetectionEventSerializer(events, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        """
        Update the status of a camera.
        """
        camera = self.get_object()
        serializer = self.get_serializer(data=request.data)
        
        if serializer.is_valid():
            camera.status = serializer.validated_data['status']
            camera.save()
            return Response(CameraSerializer(camera).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    def test_connection(self, request):
        """
        Test connection to an RTSP stream.
        """
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            rtsp_url = serializer.validated_data['rtsp_url']
            timeout = serializer.validated_data['timeout']
            
            # Try to connect to the RTSP stream
            try:
                cap = cv2.VideoCapture(rtsp_url)
                start_time = time.time()
                connected = False
                
                while time.time() - start_time < timeout:
                    ret, frame = cap.read()
                    if ret:
                        connected = True
                        break
                    time.sleep(0.5)
                
                cap.release()
                
                if connected:
                    return Response({
                        'status': 'success',
                        'message': 'Successfully connected to RTSP stream'
                    })
                else:
                    return Response({
                        'status': 'error',
                        'message': 'Could not read frames from RTSP stream'
                    }, status=status.HTTP_400_BAD_REQUEST)
                    
            except Exception as e:
                return Response({
                    'status': 'error',
                    'message': f'Error connecting to RTSP stream: {str(e)}'
                }, status=status.HTTP_400_BAD_REQUEST)
                
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def calibrate(self, request, pk=None):
        """
        Calibrate a camera using reference points.
        """
        camera = self.get_object()
        reference_points = request.data.get('reference_points', [])
        
        if not reference_points or len(reference_points) < 4:
            return Response({
                'error': 'At least 4 reference points are required for calibration'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        # Create or update calibration data
        calibration, created = CameraCalibration.objects.get_or_create(camera=camera)
        
        # In a real application, we would perform actual camera calibration here
        # For this example, we'll just store the reference points
        calibration.reference_points = reference_points
        calibration.calibration_matrix = {
            'fx': 1000.0,
            'fy': 1000.0,
            'cx': camera.resolution_width / 2,
            'cy': camera.resolution_height / 2
        }
        calibration.distortion_coefficients = {
            'k1': 0.0,
            'k2': 0.0,
            'p1': 0.0,
            'p2': 0.0,
            'k3': 0.0
        }
        calibration.save()
        
        return Response(CameraCalibrationSerializer(calibration).data)

    @action(detail=False, methods=['post'])
    def add_hikvision_camera(self, request):
        """
        Add a Hikvision camera or NVR to the system.
        
        This endpoint connects to a Hikvision device using the provided credentials,
        retrieves camera information, and creates Camera objects in the system.
        """
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            ip_address = serializer.validated_data['ip_address']
            username = serializer.validated_data['username']
            password = serializer.validated_data['password']
            port = serializer.validated_data['port']
            add_all_cameras = serializer.validated_data['add_all_cameras']
            
            # Create Hikvision integration instance
            integration = HikvisionCameraIntegration(ip_address, username, password, port)
            
            # Test connection first
            connection_test = integration.test_connection()
            if connection_test['status'] != 'success':
                return Response(connection_test, status=status.HTTP_400_BAD_REQUEST)
            
            # Get camera details
            camera_details = extract_camera_details_from_hikvision(ip_address, username, password, port)
            
            if not camera_details:
                return Response({
                    'status': 'error',
                    'message': 'No cameras found on the device'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # If not adding all cameras, just take the first one (main device)
            if not add_all_cameras and len(camera_details) > 1:
                camera_details = [camera_details[0]]
            
            # Create Camera objects
            created_cameras = []
            for camera_detail in camera_details:
                # Check if camera with same RTSP URL already exists
                existing_camera = Camera.objects.filter(rtsp_url=camera_detail['rtsp_url']).first()
                if existing_camera:
                    # Update existing camera
                    for key, value in camera_detail.items():
                        setattr(existing_camera, key, value)
                    existing_camera.save()
                    created_cameras.append(CameraSerializer(existing_camera).data)
                else:
                    # Create new camera
                    camera_serializer = CameraSerializer(data=camera_detail)
                    if camera_serializer.is_valid():
                        camera = camera_serializer.save()
                        created_cameras.append(camera_serializer.data)
                    else:
                        # Log error but continue with other cameras
                        print(f"Error creating camera: {camera_serializer.errors}")
            
            return Response({
                'status': 'success',
                'message': f'Successfully added {len(created_cameras)} cameras',
                'cameras': created_cameras
            })
            
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'])
    def stream_snapshot(self, request, pk=None):
        """
        Get a snapshot from the camera's RTSP stream as a base64 encoded JPEG.
        This can be used directly in an <img> tag with data:image/jpeg;base64,{base64_string}
        """
        camera = self.get_object()
        
        if not camera.rtsp_url:
            return Response({
                'error': 'Camera does not have an RTSP URL configured'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        # Get snapshot from RTSP manager
        base64_frame = rtsp_manager.get_snapshot(camera.id, camera.rtsp_url)
        
        if base64_frame:
            return Response({
                'camera_id': camera.id,
                'camera_name': camera.name,
                'snapshot': base64_frame,
                'timestamp': timezone.now().isoformat()
            })
        else:
            return Response({
                'error': 'Failed to get snapshot from camera',
                'camera_id': camera.id,
                'camera_name': camera.name
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def save_snapshot(self, request, pk=None):
        """
        Save a snapshot from the camera's RTSP stream to disk.
        """
        camera = self.get_object()
        
        if not camera.rtsp_url:
            return Response({
                'error': 'Camera does not have an RTSP URL configured'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        # Save snapshot to disk
        snapshot_path = rtsp_manager.save_snapshot(camera.id, camera.rtsp_url)
        
        if snapshot_path:
            return Response({
                'camera_id': camera.id,
                'camera_name': camera.name,
                'snapshot_path': snapshot_path,
                'timestamp': timezone.now().isoformat()
            })
        else:
            return Response({
                'error': 'Failed to save snapshot from camera',
                'camera_id': camera.id,
                'camera_name': camera.name
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def stream_status(self, request, pk=None):
        """
        Check if the camera's RTSP stream is active.
        """
        camera = self.get_object()
        
        if not camera.rtsp_url:
            return Response({
                'camera_id': camera.id,
                'camera_name': camera.name,
                'is_active': False,
                'message': 'Camera does not have an RTSP URL configured'
            })
            
        # Check if stream is active
        stream = rtsp_manager.get_stream(camera.id, camera.rtsp_url)
        
        return Response({
            'camera_id': camera.id,
            'camera_name': camera.name,
            'is_active': stream.is_active,
            'last_frame_time': stream.last_frame_time,
            'rtsp_url': camera.rtsp_url
        })


@api_view(['POST'])
@permission_classes([AllowAny])  # Allow unauthenticated access for testing
def test_rtsp_url(request):
    """
    Test an RTSP URL and get a snapshot without creating a camera.
    This is used by the RTSP Tester component.
    """
    rtsp_url = request.data.get('rtsp_url')
    
    if not rtsp_url:
        return Response({
            'error': 'RTSP URL is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Generate a temporary ID for this test
    test_id = int(time.time())
    
    try:
        # Get snapshot from RTSP manager
        base64_frame = rtsp_manager.get_snapshot(test_id, rtsp_url)
        
        if base64_frame:
            return Response({
                'status': 'success',
                'snapshot': base64_frame,
                'timestamp': timezone.now().isoformat()
            })
        else:
            return Response({
                'status': 'error',
                'error': 'Failed to get snapshot from the RTSP stream',
                'rtsp_url': rtsp_url
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        return Response({
            'status': 'error',
            'error': f'Error processing RTSP stream: {str(e)}',
            'rtsp_url': rtsp_url
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DetectionEventViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing detection events.
    """
    queryset = DetectionEvent.objects.all().order_by('-timestamp')
    serializer_class = DetectionEventSerializer
    permission_classes = [AllowAny]  # Allow unauthenticated access for testing
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['event_type', 'camera__name']
    ordering_fields = ['timestamp', 'confidence_score']
    
    def get_queryset(self):
        queryset = DetectionEvent.objects.all()
        
        # Filter by camera if provided
        camera_id = self.request.query_params.get('camera', None)
        if camera_id:
            queryset = queryset.filter(camera_id=camera_id)
            
        # Filter by event type if provided
        event_type = self.request.query_params.get('event_type', None)
        if event_type:
            queryset = queryset.filter(event_type=event_type)
            
        # Filter by processed status if provided
        processed = self.request.query_params.get('processed', None)
        if processed is not None:
            processed = processed.lower() == 'true'
            queryset = queryset.filter(processed=processed)
            
        # Filter by confidence score if provided
        min_confidence = self.request.query_params.get('min_confidence', None)
        if min_confidence:
            queryset = queryset.filter(confidence_score__gte=float(min_confidence))
            
        # Filter by date range if provided
        start_date = self.request.query_params.get('start_date', None)
        end_date = self.request.query_params.get('end_date', None)
        
        if start_date:
            queryset = queryset.filter(timestamp__gte=start_date)
            
        if end_date:
            queryset = queryset.filter(timestamp__lte=end_date)
            
        return queryset
    
    @action(detail=True, methods=['post'])
    def process(self, request, pk=None):
        """
        Process a detection event and create a movement record if applicable.
        """
        event = self.get_object()
        
        # Check if the event has already been processed
        if event.processed:
            return Response({
                'error': 'Event has already been processed'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        # Validate that we have source and/or destination clusters
        if not event.source_cluster and not event.destination_cluster:
            return Response({
                'error': 'Either source or destination cluster must be specified'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        # Create a movement record
        try:
            from inventory.models import Movement
            
            # Get the bag ID from the request or use None for auto-assignment
            bag_id = request.data.get('bag_id', None)
            
            if bag_id:
                from inventory.models import CementBag
                try:
                    bag = CementBag.objects.get(pk=bag_id)
                except CementBag.DoesNotExist:
                    return Response({
                        'error': f'Bag with ID {bag_id} not found'
                    }, status=status.HTTP_404_NOT_FOUND)
            else:
                # In a real application, we would use computer vision to identify the bag
                # For this example, we'll return an error
                return Response({
                    'error': 'Bag ID must be specified'
                }, status=status.HTTP_400_BAD_REQUEST)
                
            # Create the movement record
            movement = Movement.objects.create(
                source_cluster=event.source_cluster,
                destination_cluster=event.destination_cluster,
                bag=bag,
                camera=event.camera,
                confidence_score=event.confidence_score,
                notes=f"Automated detection: {event.event_type}"
            )
            
            # Update the event
            event.processed = True
            event.resulting_movement = movement
            event.save()
            
            # Return the updated event
            serializer = self.get_serializer(event)
            return Response(serializer.data)
            
        except Exception as e:
            return Response({
                'error': f'Error processing event: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CameraCalibrationViewSet(viewsets.ModelViewSet):
    """
    API endpoint for camera calibration data.
    """
    queryset = CameraCalibration.objects.all()
    serializer_class = CameraCalibrationSerializer
    permission_classes = [AllowAny]  # For testing; change to IsAuthenticated for production
    
    def get_queryset(self):
        """
        Optionally restricts the returned calibrations to a given camera,
        by filtering against a `camera_id` query parameter in the URL.
        """
        queryset = CameraCalibration.objects.all()
        camera_id = self.request.query_params.get('camera_id')
        
        if camera_id is not None:
            queryset = queryset.filter(camera_id=camera_id)
            
        return queryset


class VehicleDetectionEventViewSet(viewsets.ModelViewSet):
    """
    API endpoint for vehicle detection events.
    """
    queryset = VehicleDetectionEvent.objects.all().order_by('-timestamp')
    serializer_class = VehicleDetectionEventSerializer
    permission_classes = [AllowAny]  # For testing; change to IsAuthenticated for production
    
    def get_queryset(self):
        """
        Optionally restricts the returned events to a given camera,
        by filtering against a `camera_id` query parameter in the URL.
        """
        queryset = VehicleDetectionEvent.objects.all().order_by('-timestamp')
        camera_id = self.request.query_params.get('camera_id')
        vehicle_type = self.request.query_params.get('vehicle_type')
        event_type = self.request.query_params.get('event_type')
        crossed_line = self.request.query_params.get('crossed_line')
        
        if camera_id is not None:
            queryset = queryset.filter(camera_id=camera_id)
        if vehicle_type is not None:
            queryset = queryset.filter(vehicle_type=vehicle_type)
        if event_type is not None:
            queryset = queryset.filter(event_type=event_type)
        if crossed_line is not None:
            queryset = queryset.filter(crossed_line=(crossed_line.lower() == 'true'))
            
        return queryset
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        Get vehicle detection statistics.
        """
        # Get time range from query params (default to last 24 hours)
        from django.utils import timezone
        from datetime import timedelta
        
        end_time = timezone.now()
        start_time_str = request.query_params.get('start_time')
        end_time_str = request.query_params.get('end_time')
        
        if start_time_str:
            try:
                start_time = timezone.datetime.fromisoformat(start_time_str)
            except ValueError:
                # Default to 24 hours ago if invalid format
                start_time = end_time - timedelta(hours=24)
        else:
            start_time = end_time - timedelta(hours=24)
            
        if end_time_str:
            try:
                end_time = timezone.datetime.fromisoformat(end_time_str)
            except ValueError:
                pass  # Use current time if invalid
        
        # Filter events by time range
        events = VehicleDetectionEvent.objects.filter(
            timestamp__gte=start_time,
            timestamp__lte=end_time
        )
        
        # Get counts by vehicle type
        vehicle_counts = {}
        for vehicle_type, _ in VehicleDetectionEvent.VEHICLE_TYPES:
            vehicle_counts[vehicle_type] = events.filter(vehicle_type=vehicle_type).count()
        
        # Get counts by event type
        event_counts = {}
        for event_type, _ in VehicleDetectionEvent.EVENT_TYPES:
            event_counts[event_type] = events.filter(event_type=event_type).count()
        
        # Get counts by camera
        camera_counts = {}
        cameras = Camera.objects.all()
        for camera in cameras:
            camera_counts[camera.name] = events.filter(camera=camera).count()
        
        # Get line crossing counts
        line_crossing_count = events.filter(crossed_line=True).count()
        
        return Response({
            'total_vehicles': events.count(),
            'by_vehicle_type': vehicle_counts,
            'by_event_type': event_counts,
            'by_camera': camera_counts,
            'line_crossings': line_crossing_count,
            'time_range': {
                'start': start_time.isoformat(),
                'end': end_time.isoformat()
            }
        })


@api_view(['POST'])
@permission_classes([AllowAny])  # For testing; change to IsAuthenticated for production
def process_vehicle_detection(request):
    """
    Process a vehicle detection from a camera frame.
    
    Expected payload:
    {
        "camera_id": 1,
        "detections": [
            {
                "vehicle_type": "truck",
                "confidence": 0.85,
                "bbox": [x_min, y_min, x_max, y_max],
                "tracking_id": "vehicle_123",
                "crossed_line": true,
                "direction": "in"
            },
            ...
        ],
        "frame_data": "base64_encoded_image" (optional)
    }
    """
    try:
        camera_id = request.data.get('camera_id')
        detections = request.data.get('detections', [])
        frame_data = request.data.get('frame_data')
        
        if not camera_id or not detections:
            return Response(
                {'error': 'Missing required fields: camera_id and detections'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            camera = Camera.objects.get(pk=camera_id)
        except Camera.DoesNotExist:
            return Response(
                {'error': f'Camera with ID {camera_id} not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Process each detection
        created_events = []
        for detection in detections:
            # Extract detection data
            vehicle_type = detection.get('vehicle_type', 'unknown')
            confidence = detection.get('confidence', 0.0)
            bbox = detection.get('bbox', [0, 0, 0, 0])
            tracking_id = detection.get('tracking_id')
            crossed_line = detection.get('crossed_line', False)
            direction = detection.get('direction')
            estimated_speed = detection.get('estimated_speed')
            
            # Determine event type based on direction
            event_type = 'passing'
            if direction == 'in':
                event_type = 'entry'
            elif direction == 'out':
                event_type = 'exit'
            
            # Create vehicle detection event
            event = VehicleDetectionEvent.objects.create(
                camera=camera,
                vehicle_type=vehicle_type,
                event_type=event_type,
                confidence_score=confidence,
                x_min=bbox[0],
                y_min=bbox[1],
                x_max=bbox[2],
                y_max=bbox[3],
                tracking_id=tracking_id,
                crossed_line=crossed_line,
                direction=direction,
                estimated_speed=estimated_speed
            )
            
            # Save image snapshot if provided
            if frame_data:
                import base64
                from django.core.files.base import ContentFile
                from datetime import datetime
                
                try:
                    # Remove data URL prefix if present
                    if ',' in frame_data:
                        frame_data = frame_data.split(',')[1]
                    
                    # Decode base64 image
                    image_data = base64.b64decode(frame_data)
                    file_name = f"vehicle_{event.id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg"
                    event.image_snapshot.save(file_name, ContentFile(image_data), save=True)
                except Exception as e:
                    print(f"Error saving image: {e}")
            
            created_events.append(event)
        
        # Return serialized events
        serializer = VehicleDetectionEventSerializer(created_events, many=True)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    except Exception as e:
        return Response(
            {'error': f'Error processing vehicle detection: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
