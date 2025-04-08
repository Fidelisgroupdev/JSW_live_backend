from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views
from . import camera_monitor_api
from . import rtsp_api
from . import bag_detection_api
from . import counter_api
from . import counter_views

# Create a router for ViewSets
router = DefaultRouter()
router.register(r'cameras', views.CameraViewSet)
router.register(r'detection-events', views.DetectionEventViewSet)
router.register(r'calibrations', views.CameraCalibrationViewSet)
router.register(r'vehicle-detection-events', views.VehicleDetectionEventViewSet)

urlpatterns = [
    # Include router URLs
    path('', include(router.urls)),
    
    # Camera monitor API endpoints
    path('monitor/start/', camera_monitor_api.start_camera, name='start_camera'),
    path('monitor/stop/', camera_monitor_api.stop_camera, name='stop_camera'),
    path('monitor/start_all/', camera_monitor_api.start_all_cameras, name='start_all_cameras'),
    path('monitor/stop_all/', camera_monitor_api.stop_all_cameras, name='stop_all_cameras'),
    path('monitor/status/<int:camera_id>/', camera_monitor_api.get_camera_status, name='get_camera_status'),
    path('monitor/status/', camera_monitor_api.get_all_camera_status, name='get_all_camera_status'),
    path('monitor/frame/<int:camera_id>/', camera_monitor_api.get_camera_frame, name='get_camera_frame'),
    path('monitor/snapshot/<int:camera_id>/', camera_monitor_api.get_camera_snapshot, name='get_camera_snapshot'),
    
    # Test RTSP URL
    path('test-rtsp-url/', views.test_rtsp_url, name='test_rtsp_url'),
    path('process-vehicle-detection/', views.process_vehicle_detection, name='process-vehicle-detection'),
    
    # RTSP API endpoints
    path('frame/', rtsp_api.get_frame, name='get_frame'),
    path('advanced_frame/', rtsp_api.get_advanced_frame, name='get_advanced_frame'),
    path('advanced_status/', rtsp_api.get_advanced_status, name='get_advanced_status'),
    path('stop_advanced_processor/', rtsp_api.stop_advanced_processor, name='stop_advanced_processor'),
    path('mjpeg/', rtsp_api.mjpeg_stream, name='mjpeg_stream'),
    path('advanced_mjpeg/', rtsp_api.advanced_mjpeg_stream, name='advanced_mjpeg_stream'),
    
    # Cement Bag Detection API endpoints
    path('process-bag-detection/', bag_detection_api.process_bag_detection, name='process_bag_detection'),
    path('cluster-lines/<int:camera_id>/', bag_detection_api.get_cluster_lines, name='get_cluster_lines'),
    path('set-cluster-lines/<int:camera_id>/', bag_detection_api.set_cluster_lines, name='set_cluster_lines'),
    path('start-bag-detection/<int:camera_id>/', bag_detection_api.start_bag_detection, name='start_bag_detection'),
    path('stop-bag-detection/<int:camera_id>/', bag_detection_api.stop_bag_detection, name='stop_bag_detection'),
    
    # Cement Bag Counter API endpoints
    path('counter/start/', counter_api.start_counter, name='start_counter'),
    path('counter/status/', counter_api.get_counter_status, name='get_counter_status'),
    path('counter/frame/', counter_api.get_counter_frame, name='get_counter_frame'),
    path('counter/stop/', counter_api.stop_counter, name='stop_counter'),
    path('counter/mjpeg/', counter_api.counter_mjpeg_stream, name='counter_mjpeg_stream'),
    path('counter/list/', counter_api.list_active_counters, name='list_active_counters'),
    
    # Cement Bag Counter Web Interface
    path('counter/', counter_views.cement_counter_view, name='cement_counter_view'),
]
