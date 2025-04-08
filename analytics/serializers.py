from rest_framework import serializers
from .models import (
    InventorySnapshot, ClusterSnapshot, MovementAnalytics,
    FIFOCompliance, ClusterPerformance, PredictiveModel, Alert
)
from inventory.serializers import ClusterSerializer

class InventorySnapshotSerializer(serializers.ModelSerializer):
    """
    Serializer for InventorySnapshot model.
    """
    class Meta:
        model = InventorySnapshot
        fields = [
            'id', 'timestamp', 'total_bags', 'total_clusters',
            'average_utilization', 'oldest_bag_age'
        ]


class ClusterSnapshotSerializer(serializers.ModelSerializer):
    """
    Serializer for ClusterSnapshot model.
    """
    cluster_name = serializers.CharField(source='cluster.name', read_only=True)
    
    class Meta:
        model = ClusterSnapshot
        fields = [
            'id', 'inventory_snapshot', 'cluster', 'cluster_name',
            'bag_count', 'utilization_percentage', 'oldest_bag_age'
        ]


class MovementAnalyticsSerializer(serializers.ModelSerializer):
    """
    Serializer for MovementAnalytics model.
    """
    class Meta:
        model = MovementAnalytics
        fields = [
            'id', 'period_type', 'start_date', 'end_date', 'total_movements',
            'new_entries', 'exits', 'internal_movements', 'automated_detections',
            'manual_entries'
        ]


class FIFOComplianceSerializer(serializers.ModelSerializer):
    """
    Serializer for FIFOCompliance model.
    """
    class Meta:
        model = FIFOCompliance
        fields = [
            'id', 'date', 'total_bags', 'compliant_bags',
            'non_compliant_bags', 'compliance_percentage'
        ]


class ClusterPerformanceSerializer(serializers.ModelSerializer):
    """
    Serializer for ClusterPerformance model.
    """
    cluster_name = serializers.CharField(source='cluster.name', read_only=True)
    
    class Meta:
        model = ClusterPerformance
        fields = [
            'id', 'cluster', 'cluster_name', 'date', 'turnover_rate',
            'average_residence_time', 'fifo_compliance', 'utilization_average'
        ]


class PredictiveModelSerializer(serializers.ModelSerializer):
    """
    Serializer for PredictiveModel model.
    """
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    model_type_display = serializers.CharField(source='get_model_type_display', read_only=True)
    
    class Meta:
        model = PredictiveModel
        fields = [
            'id', 'name', 'model_type', 'model_type_display', 'created_by',
            'created_by_username', 'created_at', 'last_trained',
            'parameters', 'accuracy_metrics', 'is_active'
        ]


class AlertSerializer(serializers.ModelSerializer):
    """
    Serializer for Alert model.
    """
    alert_type_display = serializers.CharField(source='get_alert_type_display', read_only=True)
    severity_display = serializers.CharField(source='get_severity_display', read_only=True)
    related_cluster_name = serializers.CharField(source='related_cluster.name', read_only=True, allow_null=True)
    related_bag_barcode = serializers.CharField(source='related_bag.barcode', read_only=True, allow_null=True)
    acknowledged_by_username = serializers.CharField(source='acknowledged_by.username', read_only=True, allow_null=True)
    
    class Meta:
        model = Alert
        fields = [
            'id', 'timestamp', 'alert_type', 'alert_type_display', 'severity',
            'severity_display', 'title', 'description', 'related_cluster',
            'related_cluster_name', 'related_bag', 'related_bag_barcode',
            'acknowledged', 'acknowledged_by', 'acknowledged_by_username',
            'acknowledged_at'
        ]


class AlertAcknowledgeSerializer(serializers.Serializer):
    """
    Serializer for acknowledging an alert.
    """
    acknowledged = serializers.BooleanField(required=True)
