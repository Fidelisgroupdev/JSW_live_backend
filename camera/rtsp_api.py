"""
API endpoints for RTSP streaming functionality.
"""
import cv2
import base64
import time
import threading
import numpy as np
import traceback
import sys
from django.http import JsonResponse, StreamingHttpResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework import status

# Dictionary to store active stream processors
active_processors = {}

class RTSPStream:
    """
    RTSP stream processor with optional GStreamer downscaling.
    Accepts resolution keywords ('low', 'medium', 'high') or specific 'WIDTHxHEIGHT'.
    """
    def __init__(self, rtsp_url, resolution='medium'):
        self.rtsp_url = rtsp_url
        self.raw_resolution_input = resolution # Keep original input
        self.cap = None
        self.last_frame = None
        self.last_frame_time = 0
        self.frame_count = 0
        self.dropped_frames = 0
        self.running = False
        self.lock = threading.Lock()
        self.fps = 0
        self.start_time = time.time()
        self.error_message = ""
        self.connection_attempts = 0
        self.last_error = None
        self.stream_width = 0
        self.stream_height = 0
        self.use_gstreamer = False
        self.target_width = 0
        self.target_height = 0

        # Predefined resolution keywords (width, height)
        self.predefined_resolutions = {
            'low': (640, 360),
            'medium': (1280, 720),
            'high': (1920, 1080)
            # Add more if needed, e.g., '4k': (3840, 2160)
        }

        # Parse resolution input
        if isinstance(resolution, str):
            if 'x' in resolution.lower(): # Check for 'WxH' format
                try:
                    w_str, h_str = resolution.lower().split('x')
                    self.target_width = int(w_str)
                    self.target_height = int(h_str)
                    if self.target_width > 0 and self.target_height > 0:
                        print(f"Using GStreamer for target resolution: {self.target_width}x{self.target_height}")
                        self.use_gstreamer = True
                    else:
                        print(f"Warning: Invalid dimensions in resolution '{resolution}'. Falling back to medium.")
                        self.target_width, self.target_height = self.predefined_resolutions['medium']
                        self.use_gstreamer = False # Fallback
                except ValueError:
                    print(f"Warning: Could not parse resolution '{resolution}'. Falling back to medium.")
                    self.target_width, self.target_height = self.predefined_resolutions['medium']
                    self.use_gstreamer = False # Fallback
            elif resolution.lower() in self.predefined_resolutions:
                self.target_width, self.target_height = self.predefined_resolutions[resolution.lower()]
                print(f"Using predefined resolution '{resolution}': {self.target_width}x{self.target_height}")
                self.use_gstreamer = False # Use direct capture for predefined
            else:
                print(f"Warning: Unknown resolution keyword '{resolution}'. Falling back to medium.")
                self.target_width, self.target_height = self.predefined_resolutions['medium']
                self.use_gstreamer = False # Fallback
        else:
            print("Warning: Invalid resolution type. Falling back to medium.")
            self.target_width, self.target_height = self.predefined_resolutions['medium']
            self.use_gstreamer = False # Fallback

        # Thread for background frame capture
        self.thread = None

    def _build_gstreamer_pipeline(self, width, height):
        # Basic H.264 pipeline, adapt if source uses H.265 (rtph265depay, avdec_h265)
        # Note: `latency=0` might increase CPU usage but reduces delay.
        # `rtspsrc` might handle transport internally, try without tcp in url first.
        pipeline = (
            f"rtspsrc location={self.rtsp_url} latency=0 ! "
            "rtph264depay ! h264parse ! avdec_h264 ! videoconvert ! "
            f"videoscale ! video/x-raw, width={width}, height={height} ! "
            "appsink drop=true max-buffers=1"
            # drop=true, max-buffers=1: Keep only the latest frame to reduce latency
        )
        print(f"Using GStreamer pipeline:\n{pipeline}")
        return pipeline

    def start(self):
        """Start the RTSP stream capture, using GStreamer if specified."""
        if self.running:
            return

        self.running = True
        self.start_time = time.time()
        self.frame_count = 0
        self.dropped_frames = 0
        self.error_message = ""
        self.connection_attempts = 0
        self.last_error = None

        capture_source = "Direct OpenCV"
        try:
            if self.use_gstreamer:
                capture_source = "GStreamer"
                pipeline = self._build_gstreamer_pipeline(self.target_width, self.target_height)
                print(f"Attempting to open GStreamer pipeline...")
                self.cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
            else:
                # Use direct OpenCV capture, try adding TCP transport
                rtsp_url = self.rtsp_url
                if 'rtsp://' in rtsp_url and '?' not in rtsp_url:
                    rtsp_url = f"{rtsp_url}?rtsp_transport=tcp"
                    print(f"Using URL with TCP transport: {rtsp_url}")
                else:
                     print(f"Using original URL or URL with existing params: {rtsp_url}")

                print(f"Connecting directly via OpenCV to: {rtsp_url}")
                self.cap = cv2.VideoCapture(rtsp_url)

            # --- Common Connection Check ---
            if not self.cap or not self.cap.isOpened():
                self.error_message = f"Failed to open RTSP stream via {capture_source}."
                # Specific GStreamer hint
                if self.use_gstreamer:
                    self.error_message += " Check GStreamer installation, plugins (h264), and pipeline syntax."
                else:
                     # Try direct OpenCV capture without added TCP param if it was added
                     if '?' in rtsp_url and '?rtsp_transport=tcp' in rtsp_url:
                        original_url = self.rtsp_url
                        print(f"Retrying direct OpenCV connection without TCP param: {original_url}")
                        self.cap = cv2.VideoCapture(original_url)
                        if not self.cap or not self.cap.isOpened():
                            self.error_message += f" Retried without TCP param, still failed for {original_url}."
                        else:
                            print("Successfully connected without TCP parameter after retry.")
                            self.error_message = "" # Clear error message on success

            # --- Final Check and Thread Start ---
            if not self.cap or not self.cap.isOpened():
                 print(f"Error: {self.error_message}")
                 self.running = False
                 return # Cannot proceed

            # Attempt to set buffer size (may not work/be relevant for GStreamer)
            if not self.use_gstreamer:
                try:
                    # Lower buffer size can reduce latency for direct capture
                    self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 3)
                    print("Direct capture buffer size set to 3")
                except Exception as e:
                    print(f"Warning: Error setting buffer size for direct capture: {str(e)}")

            # Get actual stream dimensions after connection (if possible)
            try:
                 self.stream_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                 self.stream_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                 print(f"Successfully connected. Stream properties: {self.stream_width}x{self.stream_height}")
            except Exception as e:
                 print(f"Warning: Could not get stream properties after connect: {e}")
                 # Use target dimensions as fallback info if GStreamer used
                 if self.use_gstreamer:
                    self.stream_width = self.target_width
                    self.stream_height = self.target_height

            # Start background thread for frame capture
            self.thread = threading.Thread(target=self._capture_frames)
            self.thread.daemon = True
            self.thread.start()
            print(f"Started RTSP stream capture thread via {capture_source} for {self.rtsp_url}")

        except Exception as e:
            self.error_message = f"Error during {capture_source} stream initialization: {str(e)}"
            self.last_error = e
            print(self.error_message)
            self.running = False
            if self.cap:
                 self.cap.release()
            self.cap = None

    def _capture_frames(self):
        """Background thread to continuously capture frames."""
        consecutive_errors = 0
        max_consecutive_errors = 10 # Increase tolerance slightly
        last_error_print_time = 0

        while self.running:
            try:
                if not self.cap or not self.cap.isOpened():
                    self.error_message = "RTSP stream capture is not open or has closed."
                    consecutive_errors += 1
                    if consecutive_errors >= max_consecutive_errors:
                        print(f"Too many consecutive capture errors ({consecutive_errors}), stopping stream thread.")
                        self.running = False
                        break
                    time.sleep(1)  # Wait before checking again
                    continue

                grabbed = self.cap.grab() # Use grab/retrieve for potentially better performance
                if not grabbed:
                    consecutive_errors += 1
                    self.dropped_frames += 1
                    current_time = time.time()
                    # Avoid flooding logs with the same error
                    if current_time - last_error_print_time > 5:
                        self.error_message = f"Failed to grab frame (attempt {consecutive_errors}) from stream."
                        print(self.error_message)
                        last_error_print_time = current_time

                    if consecutive_errors >= max_consecutive_errors:
                        print(f"Too many consecutive grab errors ({consecutive_errors}), stopping stream thread.")
                        self.running = False
                        break

                    time.sleep(0.1)  # Short pause after grab failure
                    continue

                ret, frame = self.cap.retrieve()
                if not ret or frame is None:
                    consecutive_errors += 1 # Count retrieve failure as well
                    self.dropped_frames += 1
                    current_time = time.time()
                    if current_time - last_error_print_time > 5:
                        self.error_message = f"Failed to retrieve frame after grab (attempt {consecutive_errors})."
                        print(self.error_message)
                        last_error_print_time = current_time

                    if consecutive_errors >= max_consecutive_errors:
                        print(f"Too many consecutive retrieve errors ({consecutive_errors}), stopping stream thread.")
                        self.running = False
                        break
                    continue # Try next grab/retrieve cycle

                # --- Frame successfully retrieved --- 
                consecutive_errors = 0 # Reset error counter
                # self.error_message = "" # Keep last error unless explicitly cleared

                current_time = time.time()
                with self.lock:
                    self.last_frame = frame
                    self.last_frame_time = current_time
                    self.frame_count += 1

                # Calculate FPS occasionally
                if self.frame_count % 30 == 0:
                    elapsed_time = current_time - self.start_time
                    self.fps = self.frame_count / elapsed_time if elapsed_time > 0 else 0

                # Small sleep to prevent busy-waiting if frame rate is low
                # Adjust based on expected frame rate
                time.sleep(0.005)

            except Exception as e:
                self.error_message = f"Exception in capture loop: {str(e)}"
                self.last_error = e
                print(self.error_message)
                consecutive_errors += 1 # Treat exception as an error
                if consecutive_errors >= max_consecutive_errors:
                    print(f"Stopping capture loop due to repeated exceptions.")
                    self.running = False
                time.sleep(1) # Wait after an exception

        # Cleanup when loop exits
        print(f"RTSP capture thread for {self.rtsp_url} finished.")
        if self.cap:
            self.cap.release()
        self.cap = None
        with self.lock:
            self.running = False # Ensure running is false

    def get_latest_frame(self):
        """Return the latest captured frame and its timestamp."""
        with self.lock:
            return self.last_frame, self.last_frame_time

    def get_status(self):
        """Return the current status of the stream."""
        with self.lock:
            status = {
                'running': self.running,
                'url': self.rtsp_url,
                'resolution_input': self.raw_resolution_input,
                'using_gstreamer': self.use_gstreamer,
                'target_resolution': f"{self.target_width}x{self.target_height}" if (self.target_width and self.target_height) else 'N/A',
                'actual_width': self.stream_width,
                'actual_height': self.stream_height,
                'fps': round(self.fps, 2),
                'frame_count': self.frame_count,
                'dropped_frames': self.dropped_frames,
                'last_frame_time': self.last_frame_time,
                'error': self.error_message if self.error_message else None,
                'connection_attempts': self.connection_attempts
            }
            return status

    def stop(self):
        """Stop the RTSP stream capture."""
        print(f"Stopping RTSP stream capture for {self.rtsp_url}...")
        with self.lock:
            self.running = False # Signal thread to stop

        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0) # Wait for thread to finish
            if self.thread.is_alive():
                print(f"Warning: Capture thread for {self.rtsp_url} did not stop gracefully.")

        if self.cap:
            self.cap.release()
            self.cap = None
            print(f"Released video capture for {self.rtsp_url}.")
        self.thread = None


def get_or_create_processor(rtsp_url, resolution='medium'):
    """Get or create an RTSP stream processor for the given URL and settings."""
    # Create a unique key for this stream configuration
    key = f"{rtsp_url}_{resolution}"
    
    # Check if processor exists and is running
    if key in active_processors and active_processors[key].running:
        return active_processors[key]
    
    # Create new processor
    processor = RTSPStream(
        rtsp_url=rtsp_url,
        resolution=resolution
    )
    
    # Start processor
    processor.start()
    
    # Store processor
    active_processors[key] = processor
    
    return processor


def cleanup_processors():
    """Clean up inactive processors."""
    for key in list(active_processors.keys()):
        if not active_processors[key].running:
            del active_processors[key]


@api_view(['GET'])
@permission_classes([AllowAny])
def get_frame(request):
    """
    Get a single frame from an RTSP stream.
    
    Query parameters:
    - url: RTSP URL
    - resolution: low, medium, high (default: medium)
    """
    rtsp_url = request.GET.get('url')
    resolution = request.GET.get('resolution', 'medium')
    
    if not rtsp_url:
        return JsonResponse({
            'success': False,
            'error': 'RTSP URL is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # Get or create processor
        processor = get_or_create_processor(
            rtsp_url=rtsp_url,
            resolution=resolution
        )
        
        # Get frame as base64
        frame, _ = processor.get_latest_frame()
        if frame is not None:
            _, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            frame_base64 = base64.b64encode(jpeg).decode('utf-8')
            return JsonResponse({
                'success': True,
                'frame': frame_base64
            })
        else:
            # Check if there's an error message from the processor
            processor_status = processor.get_status()
            error_msg = processor_status.get('error', 'Failed to get frame from stream')
            
            return JsonResponse({
                'success': False,
                'error': error_msg,
                'status': processor_status
            })
    
    except Exception as e:
        # Get detailed exception info
        exc_type, exc_value, exc_traceback = sys.exc_info()
        stack_trace = traceback.format_exception(exc_type, exc_value, exc_traceback)
        error_details = {
            'error_type': exc_type.__name__ if exc_type else 'Unknown',
            'error_message': str(e),
            'stack_trace': stack_trace
        }
        
        print(f"Error in get_frame: {error_details['error_message']}")
        print(f"Stack trace: {''.join(stack_trace)}")
        
        return JsonResponse({
            'success': False,
            'error': f"Error processing RTSP stream: {str(e)}",
            'error_details': error_details
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_advanced_frame(request):
    """
    Get a single frame from an RTSP stream with advanced options.
    
    Query parameters:
    - url: RTSP URL
    - resolution: low, medium, high (default: medium)
    """
    rtsp_url = request.GET.get('url')
    resolution = request.GET.get('resolution', 'medium')
    
    if not rtsp_url:
        return JsonResponse({
            'success': False,
            'error': 'RTSP URL is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # Get or create processor
        processor = get_or_create_processor(
            rtsp_url=rtsp_url,
            resolution=resolution
        )
        
        # Get frame as base64
        frame, _ = processor.get_latest_frame()
        if frame is not None:
            _, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            frame_base64 = base64.b64encode(jpeg).decode('utf-8')
            return JsonResponse({
                'success': True,
                'frame': frame_base64,
                'status': processor.get_status()
            })
        else:
            # Check if there's an error message from the processor
            processor_status = processor.get_status()
            error_msg = processor_status.get('error', 'Failed to get frame from stream')
            
            return JsonResponse({
                'success': False,
                'error': error_msg,
                'status': processor_status
            })
    
    except Exception as e:
        # Get detailed exception info
        exc_type, exc_value, exc_traceback = sys.exc_info()
        stack_trace = traceback.format_exception(exc_type, exc_value, exc_traceback)
        error_details = {
            'error_type': exc_type.__name__ if exc_type else 'Unknown',
            'error_message': str(e),
            'stack_trace': stack_trace
        }
        
        print(f"Error in get_advanced_frame: {error_details['error_message']}")
        print(f"Stack trace: {''.join(stack_trace)}")
        
        return JsonResponse({
            'success': False,
            'error': f"Error processing RTSP stream: {str(e)}",
            'error_details': error_details
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_advanced_status(request):
    """
    Get status information for an RTSP stream.
    
    Query parameters:
    - url: RTSP URL
    """
    rtsp_url = request.GET.get('url')
    
    if not rtsp_url:
        return JsonResponse({
            'success': False,
            'error': 'RTSP URL is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Create key to look up processor
    key = f"{rtsp_url}_medium"
    
    if key in active_processors:
        return JsonResponse({
            'success': True,
            'status': active_processors[key].get_status()
        })
    else:
        return JsonResponse({
            'success': False,
            'error': 'Stream not found'
        })


@api_view(['POST'])
@permission_classes([AllowAny])
def stop_advanced_processor(request):
    """
    Stop an RTSP stream processor.
    
    Request body:
    {
        "url": "rtsp://..."
    }
    """
    data = request.data
    rtsp_url = data.get('url')
    
    if not rtsp_url:
        return JsonResponse({
            'success': False,
            'error': 'RTSP URL is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Create key to look up processor
    key = f"{rtsp_url}_medium"
    
    if key in active_processors:
        active_processors[key].stop()
        del active_processors[key]
        return JsonResponse({
            'success': True,
            'message': 'Stream processor stopped'
        })
    else:
        return JsonResponse({
            'success': False,
            'error': 'Stream not found'
        })


@api_view(['GET'])
@permission_classes([AllowAny])
def mjpeg_stream(request):
    """
    Stream MJPEG from an RTSP source.
    
    Query parameters:
    - url: RTSP URL
    - resolution: low, medium, high (default: medium)
    """
    from django.http import StreamingHttpResponse
    
    rtsp_url = request.GET.get('url')
    resolution = request.GET.get('resolution', 'medium')
    
    if not rtsp_url:
        return JsonResponse({
            'success': False,
            'error': 'RTSP URL is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    def generate_frames():
        try:
            # Get or create processor
            processor = get_or_create_processor(
                rtsp_url=rtsp_url,
                resolution=resolution
            )
            
            while True:
                # Get frame
                frame, _ = processor.get_latest_frame()
                
                if frame is not None:
                    _, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n\r\n')
                else:
                    # No frame available, yield empty frame
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n\r\n\r\n')
                
                # Limit frame rate
                time.sleep(0.033)  # ~30fps
                
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
def advanced_mjpeg_stream(request):
    """
    Stream MJPEG from an RTSP source with advanced options.
    
    Query parameters:
    - url: RTSP URL
    - resolution: low, medium, high (default: medium)
    """
    from django.http import StreamingHttpResponse
    
    rtsp_url = request.GET.get('url')
    resolution = request.GET.get('resolution', 'medium')
    
    if not rtsp_url:
        return JsonResponse({
            'success': False,
            'error': 'RTSP URL is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    def generate_frames():
        try:
            # Get or create processor
            processor = get_or_create_processor(
                rtsp_url=rtsp_url,
                resolution=resolution
            )
            
            while True:
                # Get frame
                frame, _ = processor.get_latest_frame()
                
                if frame is not None:
                    _, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n\r\n')
                else:
                    # No frame available, yield empty frame
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n\r\n\r\n')
                
                # Limit frame rate
                time.sleep(0.033)  # ~30fps
                
        except Exception as e:
            print(f"Error in advanced MJPEG stream: {str(e)}")
            yield (b'--frame\r\n'
                   b'Content-Type: text/plain\r\n\r\n' + str(e).encode() + b'\r\n\r\n')
    
    # Return streaming response
    return StreamingHttpResponse(
        generate_frames(),
        content_type='multipart/x-mixed-replace; boundary=frame'
    )
