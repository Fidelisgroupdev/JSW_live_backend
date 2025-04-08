from rest_framework import serializers
from .models import Camera, CameraCalibration, DetectionEvent, VehicleDetectionEvent
from inventory.serializers import ClusterSerializer

class CameraSerializer(serializers.ModelSerializer):
    """
    Serializer for Camera model.
    """
    is_active = serializers.BooleanField(read_only=True)
    resolution = serializers.CharField(read_only=True)
    coverage_clusters_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Camera
        fields = [
            'id', 'name', 'location_description', 'rtsp_url', 'status',
            'last_status_change', 'coverage_clusters', 'coverage_clusters_count',
            'resolution_width', 'resolution_height', 'fps', 'detection_threshold',
            'is_active', 'resolution', 'created_at', 'updated_at'
        ]
    
    def get_coverage_clusters_count(self, obj):
        return obj.coverage_clusters.count()


class CameraDetailSerializer(CameraSerializer):
    """
    Detailed serializer for Camera model including coverage clusters.
    """
    coverage_clusters = ClusterSerializer(many=True, read_only=True)
    
    class Meta(CameraSerializer.Meta):
        pass


class CameraCalibrationSerializer(serializers.ModelSerializer):
    """
    Serializer for CameraCalibration model.
    """
    camera_name = serializers.CharField(source='camera.name', read_only=True)
    
    class Meta:
        model = CameraCalibration
        fields = [
            'id', 'camera', 'camera_name', 'calibration_date',
            'calibration_matrix', 'distortion_coefficients', 'reference_points'
        ]


class DetectionEventSerializer(serializers.ModelSerializer):
    """
    Serializer for DetectionEvent model.
    """
    camera_name = serializers.CharField(source='camera.name', read_only=True)
    source_cluster_name = serializers.CharField(source='source_cluster.name', read_only=True, allow_null=True)
    destination_cluster_name = serializers.CharField(source='destination_cluster.name', read_only=True, allow_null=True)
    bounding_box = serializers.ListField(read_only=True)
    
    class Meta:
        model = DetectionEvent
        fields = [
            'id', 'camera', 'camera_name', 'timestamp', 'event_type',
            'confidence_score', 'image_snapshot', 'x_min', 'y_min', 'x_max', 'y_max',
            'bounding_box', 'source_cluster', 'source_cluster_name',
            'destination_cluster', 'destination_cluster_name',
            'processed', 'resulting_movement'
        ]


class VehicleDetectionEventSerializer(serializers.ModelSerializer):
    camera_name = serializers.ReadOnlyField(source='camera.name')
    bounding_box = serializers.ReadOnlyField()
    
    class Meta:
        model = VehicleDetectionEvent
        fields = [
            'id', 'camera', 'camera_name', 'timestamp', 'vehicle_type', 
            'event_type', 'confidence_score', 'image_snapshot', 
            'x_min', 'y_min', 'x_max', 'y_max', 'bounding_box',
            'tracking_id', 'crossed_line', 'direction', 'estimated_speed'
        ]
        read_only_fields = ['id', 'timestamp', 'camera_name']


class RTSPStreamSerializer(serializers.Serializer):
    """
    Serializer for RTSP stream connection testing.
    """
    rtsp_url = serializers.URLField(required=True)
    timeout = serializers.IntegerField(default=5, min_value=1, max_value=30)


class CameraStatusUpdateSerializer(serializers.Serializer):
    """
    Serializer for updating camera status.
    """
    status = serializers.ChoiceField(choices=Camera.STATUS_CHOICES)


class HikvisionCameraSerializer(serializers.Serializer):
    """
    Serializer for Hikvision camera integration.
    """
    ip_address = serializers.IPAddressField(required=True)
    username = serializers.CharField(required=True)
    password = serializers.CharField(required=True, style={'input_type': 'password'})
    port = serializers.IntegerField(default=80, min_value=1, max_value=65535)
    add_all_cameras = serializers.BooleanField(default=True, help_text="If true, add all cameras from NVR. If false, add only the main device.")
