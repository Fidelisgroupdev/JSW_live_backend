from django.contrib import admin
from .models import (
    InventorySnapshot, ClusterSnapshot, MovementAnalytics,
    FIFOCompliance, ClusterPerformance, PredictiveModel, Alert
)

@admin.register(InventorySnapshot)
class InventorySnapshotAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'total_bags', 'total_clusters', 'average_utilization', 'oldest_bag_age')
    list_filter = ('timestamp',)
    date_hierarchy = 'timestamp'

@admin.register(ClusterSnapshot)
class ClusterSnapshotAdmin(admin.ModelAdmin):
    list_display = ('inventory_snapshot', 'cluster', 'bag_count', 'utilization_percentage', 'oldest_bag_age')
    list_filter = ('inventory_snapshot__timestamp', 'cluster')
    search_fields = ('cluster__name',)

@admin.register(MovementAnalytics)
class MovementAnalyticsAdmin(admin.ModelAdmin):
    list_display = ('period_type', 'start_date', 'end_date', 'total_movements', 'new_entries', 'exits')
    list_filter = ('period_type', 'start_date', 'end_date')
    date_hierarchy = 'start_date'

@admin.register(FIFOCompliance)
class FIFOComplianceAdmin(admin.ModelAdmin):
    list_display = ('date', 'total_bags', 'compliant_bags', 'non_compliant_bags', 'compliance_percentage')
    list_filter = ('date',)
    date_hierarchy = 'date'

@admin.register(ClusterPerformance)
class ClusterPerformanceAdmin(admin.ModelAdmin):
    list_display = ('cluster', 'date', 'turnover_rate', 'average_residence_time', 'fifo_compliance', 'utilization_average')
    list_filter = ('date', 'cluster')
    search_fields = ('cluster__name',)
    date_hierarchy = 'date'

@admin.register(PredictiveModel)
class PredictiveModelAdmin(admin.ModelAdmin):
    list_display = ('name', 'model_type', 'created_by', 'created_at', 'last_trained', 'is_active')
    list_filter = ('model_type', 'is_active', 'created_at', 'last_trained')
    search_fields = ('name',)
    date_hierarchy = 'created_at'

@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'alert_type', 'severity', 'title', 'acknowledged', 'acknowledged_by')
    list_filter = ('alert_type', 'severity', 'acknowledged', 'timestamp')
    search_fields = ('title', 'description')
    date_hierarchy = 'timestamp'
