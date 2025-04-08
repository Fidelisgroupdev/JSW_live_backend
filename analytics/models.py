from django.db import models
from inventory.models import Cluster, CementBag, Movement
from django.conf import settings

# Create your models here.

class InventorySnapshot(models.Model):
    """
    Represents a point-in-time snapshot of the warehouse inventory.
    Used for historical tracking and trend analysis.
    """
    timestamp = models.DateTimeField(auto_now_add=True)
    total_bags = models.PositiveIntegerField(help_text="Total number of bags in the warehouse")
    total_clusters = models.PositiveIntegerField(help_text="Total number of active clusters")
    average_utilization = models.FloatField(help_text="Average utilization percentage across all clusters")
    oldest_bag_age = models.PositiveIntegerField(help_text="Age in days of the oldest bag in the warehouse")
    
    def __str__(self):
        return f"Inventory Snapshot at {self.timestamp}"


class ClusterSnapshot(models.Model):
    """
    Represents a point-in-time snapshot of a specific cluster.
    """
    inventory_snapshot = models.ForeignKey(
        InventorySnapshot, 
        on_delete=models.CASCADE, 
        related_name='cluster_snapshots'
    )
    cluster = models.ForeignKey(Cluster, on_delete=models.CASCADE, related_name='snapshots')
    bag_count = models.PositiveIntegerField()
    utilization_percentage = models.FloatField()
    oldest_bag_age = models.PositiveIntegerField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.cluster.name} Snapshot at {self.inventory_snapshot.timestamp}"


class MovementAnalytics(models.Model):
    """
    Aggregated movement analytics for a specific time period.
    """
    PERIOD_CHOICES = (
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    )
    
    period_type = models.CharField(max_length=10, choices=PERIOD_CHOICES)
    start_date = models.DateField()
    end_date = models.DateField()
    total_movements = models.PositiveIntegerField(default=0)
    new_entries = models.PositiveIntegerField(default=0)
    exits = models.PositiveIntegerField(default=0)
    internal_movements = models.PositiveIntegerField(default=0)
    automated_detections = models.PositiveIntegerField(default=0)
    manual_entries = models.PositiveIntegerField(default=0)
    
    class Meta:
        unique_together = ('period_type', 'start_date', 'end_date')
        verbose_name_plural = 'Movement Analytics'
    
    def __str__(self):
        return f"{self.get_period_type_display()} Movement Analytics: {self.start_date} to {self.end_date}"


class FIFOCompliance(models.Model):
    """
    Tracks FIFO compliance metrics for the warehouse.
    """
    date = models.DateField(unique=True)
    total_bags = models.PositiveIntegerField()
    compliant_bags = models.PositiveIntegerField(help_text="Bags that are being used in FIFO order")
    non_compliant_bags = models.PositiveIntegerField(help_text="Bags that are not being used in FIFO order")
    compliance_percentage = models.FloatField(help_text="Percentage of bags that are FIFO compliant")
    
    def __str__(self):
        return f"FIFO Compliance for {self.date}: {self.compliance_percentage:.2f}%"


class ClusterPerformance(models.Model):
    """
    Tracks performance metrics for individual clusters.
    """
    cluster = models.ForeignKey(Cluster, on_delete=models.CASCADE, related_name='performance_metrics')
    date = models.DateField()
    turnover_rate = models.FloatField(help_text="Rate at which inventory turns over in this cluster")
    average_residence_time = models.FloatField(help_text="Average time (in days) bags stay in this cluster")
    fifo_compliance = models.FloatField(help_text="FIFO compliance percentage for this cluster")
    utilization_average = models.FloatField(help_text="Average utilization percentage for the day")
    
    class Meta:
        unique_together = ('cluster', 'date')
    
    def __str__(self):
        return f"{self.cluster.name} Performance on {self.date}"


class PredictiveModel(models.Model):
    """
    Stores parameters and metadata for predictive analytics models.
    """
    MODEL_TYPES = (
        ('inventory_forecast', 'Inventory Forecast'),
        ('movement_prediction', 'Movement Prediction'),
        ('fifo_optimization', 'FIFO Optimization'),
    )
    
    name = models.CharField(max_length=100)
    model_type = models.CharField(max_length=30, choices=MODEL_TYPES)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_trained = models.DateTimeField()
    parameters = models.JSONField(default=dict)
    accuracy_metrics = models.JSONField(default=dict)
    is_active = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.name} ({self.get_model_type_display()})"


class Alert(models.Model):
    """
    System alerts for inventory issues, FIFO violations, etc.
    """
    ALERT_TYPES = (
        ('fifo_violation', 'FIFO Violation'),
        ('shelf_life', 'Shelf Life Warning'),
        ('capacity', 'Capacity Warning'),
        ('camera_issue', 'Camera Issue'),
        ('system', 'System Alert'),
    )
    
    SEVERITY_LEVELS = (
        ('info', 'Information'),
        ('warning', 'Warning'),
        ('critical', 'Critical'),
    )
    
    timestamp = models.DateTimeField(auto_now_add=True)
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPES)
    severity = models.CharField(max_length=10, choices=SEVERITY_LEVELS)
    title = models.CharField(max_length=200)
    description = models.TextField()
    related_cluster = models.ForeignKey(Cluster, on_delete=models.SET_NULL, null=True, blank=True)
    related_bag = models.ForeignKey(CementBag, on_delete=models.SET_NULL, null=True, blank=True)
    acknowledged = models.BooleanField(default=False)
    acknowledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='acknowledged_alerts'
    )
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.get_alert_type_display()}: {self.title}"
