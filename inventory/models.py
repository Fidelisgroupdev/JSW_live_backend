from django.db import models
from django.conf import settings

# Create your models here.

class Cluster(models.Model):
    """
    Represents a storage cluster within the warehouse.
    """
    name = models.CharField(max_length=100)
    location_x = models.FloatField(help_text="X coordinate in warehouse layout")
    location_y = models.FloatField(help_text="Y coordinate in warehouse layout")
    length = models.FloatField(help_text="Length of cluster in meters")
    width = models.FloatField(help_text="Width of cluster in meters")
    max_capacity = models.PositiveIntegerField(help_text="Maximum number of bags this cluster can hold")
    current_count = models.PositiveIntegerField(default=0, help_text="Current number of bags in this cluster")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} ({self.current_count}/{self.max_capacity})"
    
    @property
    def utilization_percentage(self):
        """Calculate the utilization percentage of the cluster."""
        if self.max_capacity == 0:
            return 0
        return (self.current_count / self.max_capacity) * 100
    
    @property
    def is_full(self):
        """Check if the cluster is at full capacity."""
        return self.current_count >= self.max_capacity
    
    @property
    def available_capacity(self):
        """Calculate the remaining capacity of the cluster."""
        return max(0, self.max_capacity - self.current_count)


class CementBag(models.Model):
    """
    Represents a cement bag in the warehouse.
    """
    STATUS_CHOICES = (
        ('available', 'Available'),
        ('reserved', 'Reserved'),
        ('sold', 'Sold'),
        ('damaged', 'Damaged'),
    )
    
    barcode = models.CharField(max_length=100, unique=True, help_text="Unique identifier for the bag")
    manufacture_date = models.DateField(help_text="Date the cement bag was manufactured")
    entry_date = models.DateTimeField(help_text="Date and time the bag entered the warehouse")
    cluster = models.ForeignKey(Cluster, on_delete=models.SET_NULL, null=True, blank=True, related_name='bags')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Bag {self.barcode} ({self.status})"
    
    @property
    def age_in_days(self):
        """Calculate the age of the cement bag in days since manufacture date."""
        from django.utils import timezone
        import datetime
        
        today = timezone.now().date()
        return (today - self.manufacture_date).days
    
    @property
    def shelf_life_percentage(self):
        """Calculate the percentage of shelf life used (assuming 90-day shelf life)."""
        shelf_life_days = 90
        age = self.age_in_days
        
        if age >= shelf_life_days:
            return 100
        return (age / shelf_life_days) * 100


class Movement(models.Model):
    """
    Represents a movement of a cement bag between clusters.
    """
    timestamp = models.DateTimeField(auto_now_add=True)
    source_cluster = models.ForeignKey(
        Cluster, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='source_movements',
        help_text="Source cluster (null for new entries)"
    )
    destination_cluster = models.ForeignKey(
        Cluster, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='destination_movements',
        help_text="Destination cluster (null for exits)"
    )
    bag = models.ForeignKey(CementBag, on_delete=models.CASCADE, related_name='movements')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        help_text="User who initiated or approved the movement"
    )
    camera = models.ForeignKey(
        'camera.Camera', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        help_text="Camera that detected the movement"
    )
    confidence_score = models.FloatField(
        default=1.0, 
        help_text="Confidence score for automated detections (0.0 to 1.0)"
    )
    notes = models.TextField(blank=True, null=True)
    
    def __str__(self):
        source = self.source_cluster.name if self.source_cluster else "Warehouse Entry"
        destination = self.destination_cluster.name if self.destination_cluster else "Warehouse Exit"
        return f"{self.bag.barcode}: {source} → {destination}"
    
    def save(self, *args, **kwargs):
        """
        Override save method to update cluster counts when a movement is recorded.
        """
        # Check if this is a new movement (not an update to an existing one)
        is_new = self.pk is None
        
        if is_new and self.bag:
            # Update source cluster count if applicable
            if self.source_cluster:
                self.source_cluster.current_count = max(0, self.source_cluster.current_count - 1)
                self.source_cluster.save()
                
            # Update destination cluster count if applicable
            if self.destination_cluster:
                self.destination_cluster.current_count += 1
                self.destination_cluster.save()
                
            # Update bag's current cluster
            self.bag.cluster = self.destination_cluster
            self.bag.save()
            
        super().save(*args, **kwargs)
