"""
Camera Monitor API

This module provides API endpoints for managing multiple camera streams
using the advanced RTSP processor with hardware acceleration.
"""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
import cv2
import base64
import json
import logging
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.conf import settings
import os
import time
from typing import Dict, List, Optional, Any

from .models import Camera
from .camera_monitor import camera_monitor

# Configure logging
logger = logging.getLogger(__name__)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_camera(request):
    """
    Start monitoring a camera with the advanced RTSP processor
    
    Request body:
    {
        "camera_id": 1,
        "config": {
            "hardware_acceleration": true,
            "low_latency": true,
            "transport": "tcp",
            "buffer_size": 5,
            "codec": "auto"
        }
    }
    """
    try:
        camera_id = request.data.get('camera_id')
        config = request.data.get('config', {})
        
        if not camera_id:
            return Response(
                {'error': 'camera_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Try to get the camera from the database
        try:
            camera = Camera.objects.get(id=camera_id)
        except Camera.DoesNotExist:
            return Response(
                {'error': f'Camera with ID {camera_id} does not exist'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Start camera
        success = camera_monitor.start_camera(camera_id, config)
        
        if success:
            # Update camera status in database
            camera.status = 'active'
            camera.config = json.dumps(config)
            camera.save()
            
            return Response({
                'success': True,
                'message': f'Camera {camera_id} started successfully'
            })
        else:
            return Response({
                'success': False,
                'error': f'Failed to start camera {camera_id}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    except Exception as e:
        logger.error(f"Error starting camera: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def stop_camera(request):
    """
    Stop monitoring a camera
    
    Request body:
    {
        "camera_id": 1
    }
    """
    try:
        camera_id = request.data.get('camera_id')
        
        if not camera_id:
            return Response(
                {'error': 'camera_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Try to get the camera from the database
        try:
            camera = Camera.objects.get(id=camera_id)
        except Camera.DoesNotExist:
            return Response(
                {'error': f'Camera with ID {camera_id} does not exist'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Stop camera
        success = camera_monitor.stop_camera(camera_id)
        
        if success:
            # Update camera status in database
            camera.status = 'inactive'
            camera.save()
            
            return Response({
                'success': True,
                'message': f'Camera {camera_id} stopped successfully'
            })
        else:
            return Response({
                'success': False,
                'error': f'Failed to stop camera {camera_id}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    except Exception as e:
        logger.error(f"Error stopping camera: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def stop_all_cameras(request):
    """
    Stop all active camera monitors
    """
    try:
        camera_monitor.stop_all_cameras()
        
        # Update camera statuses in database
        cameras = Camera.objects.all()
        for camera in cameras:
            camera.status = 'inactive'
            camera.save()
        
        return Response({
            'success': True,
            'message': 'All cameras stopped successfully'
        })
    
    except Exception as e:
        logger.error(f"Error stopping all cameras: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_camera_status(request, camera_id):
    """
    Get the current status of a camera
    """
    try:
        # Check if camera exists in database
        try:
            camera = Camera.objects.get(id=camera_id)
        except Camera.DoesNotExist:
            return Response(
                {'error': f'Camera with ID {camera_id} does not exist'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get status
        status_data = camera_monitor.get_camera_status(camera_id)
        
        return Response(status_data)
    
    except Exception as e:
        logger.error(f"Error getting camera status: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_all_camera_status(request):
    """
    Get the status of all cameras
    """
    try:
        # Get all cameras from database
        cameras = Camera.objects.all()
        
        # Get status for each camera
        status_data = {}
        for camera in cameras:
            camera_status = camera_monitor.get_camera_status(camera.id)
            status_data[camera.id] = {
                'name': camera.name,
                'location': camera.location_description,
                'rtsp_url': camera.rtsp_url,
                'status': camera_status
            }
        
        return Response(status_data)
    
    except Exception as e:
        logger.error(f"Error getting all camera status: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def get_camera_frame(request, camera_id):
    """
    Get the latest frame from a camera as a JPEG image
    
    Query parameters:
    - base64: If true, return the frame as a base64 encoded string
    - quality: JPEG quality (1-100), default 85
    """
    try:
        # Check if camera exists in database
        try:
            camera = Camera.objects.get(id=camera_id)
        except Camera.DoesNotExist:
            return Response(
                {'error': f'Camera with ID {camera_id} does not exist'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get frame
        frame, error = camera_monitor.get_frame(camera_id)
        
        if frame is None:
            return Response({
                'success': False,
                'error': error or 'No frame available'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check if we should return base64
        return_base64 = request.query_params.get('base64', 'false').lower() == 'true'
        
        # Get JPEG quality
        quality = int(request.query_params.get('quality', '85'))
        quality = max(1, min(100, quality))  # Ensure quality is between 1 and 100
        
        # Encode frame as JPEG
        _, jpeg_data = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
        
        if return_base64:
            # Return as base64 encoded string
            frame_base64 = base64.b64encode(jpeg_data).decode('utf-8')
            return Response({
                'success': True,
                'frame': frame_base64,
                'timestamp': time.time()
            })
        else:
            # Return as binary image
            return HttpResponse(
                jpeg_data.tobytes(),
                content_type='image/jpeg'
            )
    
    except Exception as e:
        logger.error(f"Error getting camera frame: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_camera_snapshot(request, camera_id):
    """
    Get a snapshot from a camera and optionally save it to disk
    
    Query parameters:
    - save: If true, save the snapshot to disk
    - base64: If true, return the frame as a base64 encoded string
    - quality: JPEG quality (1-100), default 85
    """
    try:
        # Check if camera exists in database
        try:
            camera = Camera.objects.get(id=camera_id)
        except Camera.DoesNotExist:
            return Response(
                {'error': f'Camera with ID {camera_id} does not exist'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get snapshot
        frame, filepath, error = camera_monitor.get_snapshot(camera_id, False)
        
        if frame is None:
            return Response({
                'success': False,
                'error': error or 'No frame available'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check if we should return base64
        return_base64 = request.query_params.get('base64', 'false').lower() == 'true'
        
        # Get JPEG quality
        quality = int(request.query_params.get('quality', '85'))
        quality = max(1, min(100, quality))  # Ensure quality is between 1 and 100
        
        # Encode frame as JPEG
        _, jpeg_data = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
        
        if return_base64:
            # Return as base64 encoded string
            frame_base64 = base64.b64encode(jpeg_data).decode('utf-8')
            return Response({
                'success': True,
                'frame': frame_base64,
                'filepath': filepath,
                'timestamp': time.time()
            })
        else:
            # Return as binary image
            return HttpResponse(
                jpeg_data.tobytes(),
                content_type='image/jpeg'
            )
    
    except Exception as e:
        logger.error(f"Error getting camera snapshot: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def camera_mjpeg_stream(request, camera_id):
    """
    Stream camera frames as MJPEG
    
    Query parameters:
    - quality: JPEG quality (1-100), default 85
    - fps: Target FPS, default 10
    """
    try:
        # Check if camera exists in database
        try:
            camera = Camera.objects.get(id=camera_id)
        except Camera.DoesNotExist:
            return Response(
                {'error': f'Camera with ID {camera_id} does not exist'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get JPEG quality
        quality = int(request.query_params.get('quality', '85'))
        quality = max(1, min(100, quality))  # Ensure quality is between 1 and 100
        
        # Get target FPS
        target_fps = int(request.query_params.get('fps', '10'))
        target_fps = max(1, min(30, target_fps))  # Ensure FPS is between 1 and 30
        
        # Calculate frame interval
        frame_interval = 1.0 / target_fps
        
        def generate():
            last_frame_time = 0
            
            while True:
                current_time = time.time()
                
                # Limit frame rate
                if current_time - last_frame_time < frame_interval:
                    time.sleep(0.01)
                    continue
                
                # Get frame
                frame, error = camera_monitor.get_frame(camera_id)
                
                if frame is not None:
                    # Encode frame as JPEG
                    _, jpeg_data = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
                    
                    # Yield frame
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + jpeg_data.tobytes() + b'\r\n')
                    
                    last_frame_time = time.time()
                else:
                    # No frame available, yield an empty frame
                    time.sleep(0.1)
        
        return HttpResponse(generate(), content_type='multipart/x-mixed-replace; boundary=frame')
    
    except Exception as e:
        logger.error(f"Error streaming camera: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_all_cameras(request):
    """
    Start monitoring all cameras with the advanced RTSP processor
    
    Request body:
    {
        "config": {
            "hardware_acceleration": true,
            "low_latency": true,
            "transport": "tcp",
            "buffer_size": 5,
            "codec": "auto"
        }
    }
    """
    try:
        # Get custom config if provided
        config = request.data.get('config', {})
        
        # Get all cameras from database
        cameras = Camera.objects.all()
        
        results = {}
        for camera in cameras:
            # Skip cameras that are already active
            if camera.status == 'active':
                results[camera.id] = {
                    'success': True,
                    'message': f'Camera {camera.id} ({camera.name}) already active'
                }
                continue
            
            # Start camera
            success = camera_monitor.start_camera(camera.id, config)
            
            results[camera.id] = {
                'success': success,
                'message': f'Camera {camera.id} ({camera.name}) started successfully' if success else f'Failed to start camera {camera.id} ({camera.name})'
            }
            
            if success:
                # Update camera status in database
                camera.status = 'active'
                camera.config = json.dumps(config)
                camera.save()
        
        return Response({
            'success': True,
            'results': results
        })
    
    except Exception as e:
        logger.error(f"Error starting all cameras: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
