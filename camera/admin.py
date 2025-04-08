from django.contrib import admin
from .models import Camera, CameraCalibration, DetectionEvent

# Register your models here.

@admin.register(Camera)
class CameraAdmin(admin.ModelAdmin):
    list_display = ('name', 'location_description', 'status', 'resolution', 'fps')
    list_filter = ('status', 'created_at')
    search_fields = ('name', 'location_description')
    readonly_fields = ('is_active', 'resolution')
    filter_horizontal = ('coverage_clusters',)

@admin.register(CameraCalibration)
class CameraCalibrationAdmin(admin.ModelAdmin):
    list_display = ('camera', 'calibration_date')
    list_filter = ('calibration_date',)
    search_fields = ('camera__name',)

@admin.register(DetectionEvent)
class DetectionEventAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'camera', 'event_type', 'confidence_score', 'processed')
    list_filter = ('event_type', 'processed', 'timestamp', 'camera')
    search_fields = ('camera__name',)
    readonly_fields = ('bounding_box',)
    date_hierarchy = 'timestamp'
