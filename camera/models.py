from django.db import models
from inventory.models import Cluster

class Camera(models.Model):
    """
    Represents an RTSP camera in the warehouse for cement bag tracking.
    """
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('error', 'Error'),
    )
    
    name = models.CharField(max_length=100)
    location_description = models.TextField(help_text="Description of camera location in the warehouse")
    rtsp_url = models.URLField(help_text="RTSP URL for the camera feed")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='inactive')
    last_status_change = models.DateTimeField(auto_now=True)
    coverage_clusters = models.ManyToManyField(
        Cluster, 
        related_name='monitoring_cameras',
        help_text="Clusters this camera monitors"
    )
    
    # Camera configuration parameters
    resolution_width = models.PositiveIntegerField(default=1280)
    resolution_height = models.PositiveIntegerField(default=720)
    fps = models.PositiveIntegerField(default=15, help_text="Frames per second")
    detection_threshold = models.FloatField(
        default=0.7,
        help_text="Confidence threshold for detecting cement bags (0.0 to 1.0)"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"
    
    @property
    def is_active(self):
        """Check if the camera is active."""
        return self.status == 'active'
    
    @property
    def resolution(self):
        """Get camera resolution as a string."""
        return f"{self.resolution_width}x{self.resolution_height}"


class CameraCalibration(models.Model):
    """
    Stores calibration data for a camera.
    """
    camera = models.OneToOneField(Camera, on_delete=models.CASCADE, related_name='calibration')
    calibration_date = models.DateTimeField(auto_now=True)
    calibration_matrix = models.JSONField(default=dict, help_text="Camera calibration matrix")
    distortion_coefficients = models.JSONField(default=dict, help_text="Camera distortion coefficients")
    reference_points = models.JSONField(default=list, help_text="Reference points used for calibration")
    
    def __str__(self):
        return f"Calibration for {self.camera.name}"


class DetectionEvent(models.Model):
    """
    Represents a cement bag detection event from a camera.
    """
    EVENT_TYPES = (
        ('entry', 'Cluster Entry'),
        ('exit', 'Cluster Exit'),
        ('movement', 'Internal Movement'),
        ('unknown', 'Unknown'),
    )
    
    camera = models.ForeignKey(Camera, on_delete=models.CASCADE, related_name='detection_events')
    timestamp = models.DateTimeField(auto_now_add=True)
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES, default='unknown')
    confidence_score = models.FloatField(help_text="Confidence score of the detection (0.0 to 1.0)")
    image_snapshot = models.ImageField(upload_to='detection_events/', null=True, blank=True)
    
    # Coordinates of the detected bag in the image
    x_min = models.IntegerField(null=True, blank=True)
    y_min = models.IntegerField(null=True, blank=True)
    x_max = models.IntegerField(null=True, blank=True)
    y_max = models.IntegerField(null=True, blank=True)
    
    # Related cluster(s)
    source_cluster = models.ForeignKey(
        Cluster, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='source_detection_events'
    )
    destination_cluster = models.ForeignKey(
        Cluster, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='destination_detection_events'
    )
    
    # Whether this event resulted in a movement record
    processed = models.BooleanField(default=False)
    resulting_movement = models.ForeignKey(
        'inventory.Movement', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='detection_events'
    )
    
    def __str__(self):
        return f"{self.event_type} detected by {self.camera.name} at {self.timestamp}"
    
    @property
    def bounding_box(self):
        """Get the bounding box coordinates as a tuple."""
        if all(coord is not None for coord in [self.x_min, self.y_min, self.x_max, self.y_max]):
            return (self.x_min, self.y_min, self.x_max, self.y_max)
        return None


class VehicleDetectionEvent(models.Model):
    """
    Represents a vehicle detection event from a camera in the warehouse.
    """
    VEHICLE_TYPES = (
        ('truck', 'Truck'),
        ('forklift', 'Forklift'),
        ('car', 'Car'),
        ('unknown', 'Unknown'),
    )
    
    EVENT_TYPES = (
        ('entry', 'Entry'),
        ('exit', 'Exit'),
        ('passing', 'Passing'),
    )
    
    camera = models.ForeignKey(Camera, on_delete=models.CASCADE, related_name='vehicle_detection_events')
    timestamp = models.DateTimeField(auto_now_add=True)
    vehicle_type = models.CharField(max_length=20, choices=VEHICLE_TYPES, default='unknown')
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES, default='passing')
    confidence_score = models.FloatField(help_text="Confidence score of the detection (0.0 to 1.0)")
    image_snapshot = models.ImageField(upload_to='vehicle_detection_events/', null=True, blank=True)
    
    # Coordinates of the detected vehicle in the image
    x_min = models.IntegerField(null=True, blank=True)
    y_min = models.IntegerField(null=True, blank=True)
    x_max = models.IntegerField(null=True, blank=True)
    y_max = models.IntegerField(null=True, blank=True)
    
    # Tracking information
    tracking_id = models.CharField(max_length=50, null=True, blank=True, 
                                  help_text="Unique ID for tracking this vehicle across frames")
    crossed_line = models.BooleanField(default=False, 
                                      help_text="Whether this vehicle crossed a counting line")
    direction = models.CharField(max_length=20, null=True, blank=True, 
                                help_text="Direction of movement (e.g., 'in', 'out')")
    
    # Speed estimation (if available)
    estimated_speed = models.FloatField(null=True, blank=True, 
                                       help_text="Estimated speed in km/h")
    
    def __str__(self):
        return f"{self.vehicle_type} {self.event_type} detected by {self.camera.name} at {self.timestamp}"
    
    @property
    def bounding_box(self):
        """Get the bounding box coordinates as a tuple."""
        if all(coord is not None for coord in [self.x_min, self.y_min, self.x_max, self.y_max]):
            return (self.x_min, self.y_min, self.x_max, self.y_max)
        return None
