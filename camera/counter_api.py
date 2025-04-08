"""
API endpoints for cement bag counting functionality.
"""
import cv2
import base64
import time
import json
from django.http import JsonResponse, HttpResponse, StreamingHttpResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework import status
from .cement_counter import get_or_create_counter, cleanup_counters

@api_view(['GET'])
@permission_classes([AllowAny])
def start_counter(request):
    """
    Start a cement bag counter for an RTSP stream.
    
    Query parameters:
    - url: RTSP URL
    - line_position: Position of counting line (0.0-1.0, default: 0.5)
    - count_direction: 'up', 'down', or 'both' (default: 'both')
    - resolution: 'low', 'medium', 'high' (default: 'medium')
    - codec: 'auto', 'h264', 'h265' (default: 'auto')
    - transport: 'tcp', 'udp' (default: 'tcp')
    """
    rtsp_url = request.GET.get('url')
    line_position = float(request.GET.get('line_position', 0.5))
    count_direction = request.GET.get('count_direction', 'both')
    resolution = request.GET.get('resolution', 'medium')
    codec = request.GET.get('codec', 'auto')
    transport = request.GET.get('transport', 'tcp')
    
    if not rtsp_url:
        return JsonResponse({
            'success': False,
            'error': 'RTSP URL is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # Get or create counter
        counter = get_or_create_counter(
            rtsp_url=rtsp_url,
            line_position=line_position,
            count_direction=count_direction,
            resolution=resolution,
            codec=codec,
            transport=transport
        )
        
        # Return success response
        return JsonResponse({
            'success': True,
            'message': 'Cement bag counter started',
            'status': counter.get_status()
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([AllowAny])
def get_counter_status(request):
    """
    Get status information for a cement bag counter.
    
    Query parameters:
    - url: RTSP URL
    - line_position: Position of counting line (0.0-1.0, default: 0.5)
    - count_direction: 'up', 'down', or 'both' (default: 'both')
    """
    rtsp_url = request.GET.get('url')
    line_position = float(request.GET.get('line_position', 0.5))
    count_direction = request.GET.get('count_direction', 'both')
    
    if not rtsp_url:
        return JsonResponse({
            'success': False,
            'error': 'RTSP URL is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Create key for counter lookup
    key = f"{rtsp_url}_medium_auto_tcp_{line_position}_{count_direction}"
    
    # Import here to avoid circular import
    from .cement_counter import active_counters
    
    if key in active_counters:
        return JsonResponse({
            'success': True,
            'status': active_counters[key].get_status()
        })
    else:
        return JsonResponse({
            'success': False,
            'error': 'Counter not found'
        })

@api_view(['GET'])
@permission_classes([AllowAny])
def get_counter_frame(request):
    """
    Get the latest processed frame from a cement bag counter.
    
    Query parameters:
    - url: RTSP URL
    - line_position: Position of counting line (0.0-1.0, default: 0.5)
    - count_direction: 'up', 'down', or 'both' (default: 'both')
    """
    rtsp_url = request.GET.get('url')
    line_position = float(request.GET.get('line_position', 0.5))
    count_direction = request.GET.get('count_direction', 'both')
    
    if not rtsp_url:
        return JsonResponse({
            'success': False,
            'error': 'RTSP URL is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # Get or create counter
        counter = get_or_create_counter(
            rtsp_url=rtsp_url,
            line_position=line_position,
            count_direction=count_direction
        )
        
        # Get frame as base64
        frame_base64 = counter.get_frame_base64()
        
        if frame_base64:
            return JsonResponse({
                'success': True,
                'frame': frame_base64,
                'status': counter.get_status()
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'No frame available'
            })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([AllowAny])
def stop_counter(request):
    """
    Stop a cement bag counter.
    
    Request body:
    {
        "url": "rtsp://...",
        "line_position": 0.5,
        "count_direction": "both"
    }
    """
    data = request.data
    rtsp_url = data.get('url')
    line_position = float(data.get('line_position', 0.5))
    count_direction = data.get('count_direction', 'both')
    
    if not rtsp_url:
        return JsonResponse({
            'success': False,
            'error': 'RTSP URL is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Create key for counter lookup
    key = f"{rtsp_url}_medium_auto_tcp_{line_position}_{count_direction}"
    
    # Import here to avoid circular import
    from .cement_counter import active_counters
    
    if key in active_counters:
        # Get final status before stopping
        final_status = active_counters[key].get_status()
        
        # Stop the counter
        active_counters[key].stop()
        del active_counters[key]
        
        return JsonResponse({
            'success': True,
            'message': 'Cement bag counter stopped',
            'final_status': final_status
        })
    else:
        return JsonResponse({
            'success': False,
            'error': 'Counter not found'
        })

@api_view(['GET'])
@permission_classes([AllowAny])
def counter_mjpeg_stream(request):
    """
    Stream MJPEG from a cement bag counter.
    
    Query parameters:
    - url: RTSP URL
    - line_position: Position of counting line (0.0-1.0, default: 0.5)
    - count_direction: 'up', 'down', or 'both' (default: 'both')
    """
    rtsp_url = request.GET.get('url')
    line_position = float(request.GET.get('line_position', 0.5))
    count_direction = request.GET.get('count_direction', 'both')
    
    if not rtsp_url:
        return JsonResponse({
            'success': False,
            'error': 'RTSP URL is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    def generate_frames():
        try:
            # Get or create counter
            counter = get_or_create_counter(
                rtsp_url=rtsp_url,
                line_position=line_position,
                count_direction=count_direction
            )
            
            while True:
                # Get frame
                frame_bytes = counter.get_frame()
                
                if frame_bytes:
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n\r\n')
                else:
                    # No frame available, yield empty frame
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n\r\n\r\n')
                
                # Limit frame rate
                time.sleep(0.1)
                
        except Exception as e:
            print(f"Error in MJPEG stream: {str(e)}")
            yield (b'--frame\r\n'
                   b'Content-Type: text/plain\r\n\r\n' + str(e).encode() + b'\r\n\r\n')
    
    # Return streaming response
    return StreamingHttpResponse(
        generate_frames(),
        content_type='multipart/x-mixed-replace; boundary=frame'
    )

@api_view(['GET'])
@permission_classes([AllowAny])
def list_active_counters(request):
    """
    List all active cement bag counters.
    """
    # Import here to avoid circular import
    from .cement_counter import active_counters
    
    # Clean up inactive counters
    cleanup_counters()
    
    # Get status for all active counters
    counters_status = {}
    for key, counter in active_counters.items():
        counters_status[key] = counter.get_status()
    
    return JsonResponse({
        'success': True,
        'active_counters': len(active_counters),
        'counters': counters_status
    })
