from django.shortcuts import render
from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Avg, Count, Sum, F, Q
import datetime

from .models import (
    InventorySnapshot, ClusterSnapshot, MovementAnalytics,
    FIFOCompliance, ClusterPerformance, PredictiveModel, Alert
)
from .serializers import (
    InventorySnapshotSerializer, ClusterSnapshotSerializer,
    MovementAnalyticsSerializer, FIFOComplianceSerializer,
    ClusterPerformanceSerializer, PredictiveModelSerializer,
    AlertSerializer, AlertAcknowledgeSerializer
)
from inventory.models import Cluster, CementBag, Movement

class InventorySnapshotViewSet(viewsets.ModelViewSet):
    """
    API endpoint for inventory snapshots.
    """
    queryset = InventorySnapshot.objects.all().order_by('-timestamp')
    serializer_class = InventorySnapshotSerializer
    
    @action(detail=True, methods=['get'])
    def clusters(self, request, pk=None):
        """
        Return cluster snapshots for a specific inventory snapshot.
        """
        snapshot = self.get_object()
        cluster_snapshots = snapshot.cluster_snapshots.all()
        
        page = self.paginate_queryset(cluster_snapshots)
        if page is not None:
            serializer = ClusterSnapshotSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
            
        serializer = ClusterSnapshotSerializer(cluster_snapshots, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def create_snapshot(self, request):
        """
        Create a new inventory snapshot.
        """
        # Get all clusters
        clusters = Cluster.objects.all()
        
        # Calculate total bags
        total_bags = CementBag.objects.filter(status='available').count()
        
        # Calculate average utilization
        total_clusters = clusters.count()
        if total_clusters > 0:
            average_utilization = clusters.aggregate(
                avg_util=Avg(F('current_count') * 100.0 / F('max_capacity'))
            )['avg_util'] or 0
        else:
            average_utilization = 0
            
        # Find oldest bag age
        oldest_bag = CementBag.objects.filter(status='available').order_by('manufacture_date').first()
        if oldest_bag:
            oldest_bag_age = (timezone.now().date() - oldest_bag.manufacture_date).days
        else:
            oldest_bag_age = 0
            
        # Create inventory snapshot
        snapshot = InventorySnapshot.objects.create(
            total_bags=total_bags,
            total_clusters=total_clusters,
            average_utilization=average_utilization,
            oldest_bag_age=oldest_bag_age
        )
        
        # Create cluster snapshots
        cluster_snapshots = []
        for cluster in clusters:
            oldest_cluster_bag = CementBag.objects.filter(
                cluster=cluster, 
                status='available'
            ).order_by('manufacture_date').first()
            
            oldest_age = None
            if oldest_cluster_bag:
                oldest_age = (timezone.now().date() - oldest_cluster_bag.manufacture_date).days
                
            cluster_snapshot = ClusterSnapshot(
                inventory_snapshot=snapshot,
                cluster=cluster,
                bag_count=cluster.current_count,
                utilization_percentage=cluster.utilization_percentage,
                oldest_bag_age=oldest_age
            )
            cluster_snapshots.append(cluster_snapshot)
            
        ClusterSnapshot.objects.bulk_create(cluster_snapshots)
        
        return Response(InventorySnapshotSerializer(snapshot).data, status=status.HTTP_201_CREATED)


class MovementAnalyticsViewSet(viewsets.ModelViewSet):
    """
    API endpoint for movement analytics.
    """
    queryset = MovementAnalytics.objects.all().order_by('-start_date')
    serializer_class = MovementAnalyticsSerializer
    
    @action(detail=False, methods=['post'])
    def generate(self, request):
        """
        Generate movement analytics for a specific period.
        """
        period_type = request.data.get('period_type', 'daily')
        date_str = request.data.get('date', None)
        
        if not date_str:
            date = timezone.now().date()
        else:
            try:
                date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                return Response({
                    'error': 'Invalid date format. Use YYYY-MM-DD.'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Calculate start and end dates based on period type
        if period_type == 'daily':
            start_date = date
            end_date = date
        elif period_type == 'weekly':
            # Start from Monday of the week
            start_date = date - datetime.timedelta(days=date.weekday())
            end_date = start_date + datetime.timedelta(days=6)
        elif period_type == 'monthly':
            # Start from the first day of the month
            start_date = date.replace(day=1)
            # End on the last day of the month
            if date.month == 12:
                end_date = date.replace(year=date.year + 1, month=1, day=1) - datetime.timedelta(days=1)
            else:
                end_date = date.replace(month=date.month + 1, day=1) - datetime.timedelta(days=1)
        else:
            return Response({
                'error': 'Invalid period type. Use daily, weekly, or monthly.'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        # Check if analytics already exist for this period
        existing = MovementAnalytics.objects.filter(
            period_type=period_type,
            start_date=start_date,
            end_date=end_date
        ).first()
        
        if existing:
            return Response(MovementAnalyticsSerializer(existing).data)
            
        # Get movements for the period
        movements = Movement.objects.filter(
            timestamp__date__gte=start_date,
            timestamp__date__lte=end_date
        )
        
        # Calculate analytics
        total_movements = movements.count()
        new_entries = movements.filter(source_cluster__isnull=True, destination_cluster__isnull=False).count()
        exits = movements.filter(source_cluster__isnull=False, destination_cluster__isnull=True).count()
        internal_movements = movements.filter(source_cluster__isnull=False, destination_cluster__isnull=False).count()
        automated_detections = movements.filter(camera__isnull=False).count()
        manual_entries = movements.filter(camera__isnull=True).count()
        
        # Create analytics record
        analytics = MovementAnalytics.objects.create(
            period_type=period_type,
            start_date=start_date,
            end_date=end_date,
            total_movements=total_movements,
            new_entries=new_entries,
            exits=exits,
            internal_movements=internal_movements,
            automated_detections=automated_detections,
            manual_entries=manual_entries
        )
        
        return Response(MovementAnalyticsSerializer(analytics).data, status=status.HTTP_201_CREATED)


class FIFOComplianceViewSet(viewsets.ModelViewSet):
    """
    API endpoint for FIFO compliance.
    """
    queryset = FIFOCompliance.objects.all().order_by('-date')
    serializer_class = FIFOComplianceSerializer
    
    @action(detail=False, methods=['post'])
    def calculate(self, request):
        """
        Calculate FIFO compliance for a specific date.
        """
        date_str = request.data.get('date', None)
        
        if not date_str:
            date = timezone.now().date()
        else:
            try:
                date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                return Response({
                    'error': 'Invalid date format. Use YYYY-MM-DD.'
                }, status=status.HTTP_400_BAD_REQUEST)
                
        # Check if compliance already exists for this date
        existing = FIFOCompliance.objects.filter(date=date).first()
        if existing:
            return Response(FIFOComplianceSerializer(existing).data)
            
        # Get all bags
        bags = CementBag.objects.filter(status='available')
        total_bags = bags.count()
        
        if total_bags == 0:
            return Response({
                'error': 'No bags available for FIFO compliance calculation.'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        # In a real application, we would have a more sophisticated algorithm
        # to determine FIFO compliance based on movement history and cluster layout
        # For this example, we'll use a simple heuristic:
        # A bag is FIFO compliant if it's in a cluster where all older bags have been used
        
        compliant_bags = 0
        non_compliant_bags = 0
        
        # Group bags by cluster
        clusters = Cluster.objects.all()
        for cluster in clusters:
            cluster_bags = bags.filter(cluster=cluster).order_by('manufacture_date')
            cluster_bag_count = cluster_bags.count()
            
            if cluster_bag_count == 0:
                continue
                
            # Check if bags are being used in FIFO order
            # For simplicity, we'll assume the oldest 20% of bags should be in use
            oldest_bags = cluster_bags[:max(1, int(cluster_bag_count * 0.2))]
            newest_bags = cluster_bags[max(1, int(cluster_bag_count * 0.2)):]
            
            # Check if any newer bags have movements after older bags
            for old_bag in oldest_bags:
                old_bag_last_movement = old_bag.movements.order_by('-timestamp').first()
                if not old_bag_last_movement:
                    # If an old bag has no movements, it's not compliant
                    non_compliant_bags += 1
                    continue
                    
                old_movement_time = old_bag_last_movement.timestamp
                
                # Count newer bags with more recent movements
                for new_bag in newest_bags:
                    new_bag_last_movement = new_bag.movements.order_by('-timestamp').first()
                    if new_bag_last_movement and new_bag_last_movement.timestamp > old_movement_time:
                        non_compliant_bags += 1
                        break
                else:
                    compliant_bags += 1
            
            # All newer bags are compliant if older bags are being used properly
            compliant_bags += newest_bags.count()
            
        # Calculate compliance percentage
        if total_bags > 0:
            compliance_percentage = (compliant_bags / total_bags) * 100
        else:
            compliance_percentage = 0
            
        # Create compliance record
        compliance = FIFOCompliance.objects.create(
            date=date,
            total_bags=total_bags,
            compliant_bags=compliant_bags,
            non_compliant_bags=non_compliant_bags,
            compliance_percentage=compliance_percentage
        )
        
        return Response(FIFOComplianceSerializer(compliance).data, status=status.HTTP_201_CREATED)


class AlertViewSet(viewsets.ModelViewSet):
    """
    API endpoint for alerts.
    """
    queryset = Alert.objects.all().order_by('-timestamp')
    serializer_class = AlertSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'description']
    ordering_fields = ['timestamp', 'severity', 'alert_type']
    
    def get_queryset(self):
        queryset = Alert.objects.all()
        
        # Filter by alert type if provided
        alert_type = self.request.query_params.get('alert_type', None)
        if alert_type:
            queryset = queryset.filter(alert_type=alert_type)
            
        # Filter by severity if provided
        severity = self.request.query_params.get('severity', None)
        if severity:
            queryset = queryset.filter(severity=severity)
            
        # Filter by acknowledged status if provided
        acknowledged = self.request.query_params.get('acknowledged', None)
        if acknowledged is not None:
            acknowledged = acknowledged.lower() == 'true'
            queryset = queryset.filter(acknowledged=acknowledged)
            
        # Filter by date range if provided
        start_date = self.request.query_params.get('start_date', None)
        end_date = self.request.query_params.get('end_date', None)
        
        if start_date:
            queryset = queryset.filter(timestamp__date__gte=start_date)
            
        if end_date:
            queryset = queryset.filter(timestamp__date__lte=end_date)
            
        return queryset
    
    @action(detail=True, methods=['post'])
    def acknowledge(self, request, pk=None):
        """
        Acknowledge or unacknowledge an alert.
        """
        alert = self.get_object()
        serializer = AlertAcknowledgeSerializer(data=request.data)
        
        if serializer.is_valid():
            acknowledged = serializer.validated_data['acknowledged']
            
            if acknowledged:
                alert.acknowledged = True
                alert.acknowledged_by = request.user if request.user.is_authenticated else None
                alert.acknowledged_at = timezone.now()
            else:
                alert.acknowledged = False
                alert.acknowledged_by = None
                alert.acknowledged_at = None
                
            alert.save()
            return Response(AlertSerializer(alert).data)
            
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    def generate_alerts(self, request):
        """
        Generate system alerts based on current inventory state.
        """
        alerts_generated = 0
        
        # Check for bags approaching shelf life limit
        shelf_life_days = 90
        warning_threshold_days = 75
        
        old_bags = CementBag.objects.filter(
            status='available',
            manufacture_date__lte=timezone.now().date() - datetime.timedelta(days=warning_threshold_days)
        )
        
        for bag in old_bags:
            age = (timezone.now().date() - bag.manufacture_date).days
            remaining_days = shelf_life_days - age
            
            # Determine severity based on remaining days
            if remaining_days <= 5:
                severity = 'critical'
            elif remaining_days <= 15:
                severity = 'warning'
            else:
                severity = 'info'
                
            # Check if an alert already exists for this bag
            existing_alert = Alert.objects.filter(
                alert_type='shelf_life',
                related_bag=bag,
                acknowledged=False
            ).first()
            
            if not existing_alert:
                Alert.objects.create(
                    alert_type='shelf_life',
                    severity=severity,
                    title=f"Bag {bag.barcode} approaching shelf life limit",
                    description=f"Cement bag {bag.barcode} is {age} days old with {remaining_days} days remaining before shelf life expiration.",
                    related_bag=bag,
                    related_cluster=bag.cluster
                )
                alerts_generated += 1
                
        # Check for clusters approaching capacity
        capacity_warning_threshold = 0.9  # 90%
        
        full_clusters = Cluster.objects.filter(
            current_count__gte=F('max_capacity') * capacity_warning_threshold
        )
        
        for cluster in full_clusters:
            utilization = cluster.utilization_percentage
            
            # Determine severity based on utilization
            if utilization >= 98:
                severity = 'critical'
            elif utilization >= 95:
                severity = 'warning'
            else:
                severity = 'info'
                
            # Check if an alert already exists for this cluster
            existing_alert = Alert.objects.filter(
                alert_type='capacity',
                related_cluster=cluster,
                acknowledged=False
            ).first()
            
            if not existing_alert:
                Alert.objects.create(
                    alert_type='capacity',
                    severity=severity,
                    title=f"Cluster {cluster.name} approaching capacity",
                    description=f"Cluster {cluster.name} is at {utilization:.1f}% capacity with {cluster.current_count}/{cluster.max_capacity} bags.",
                    related_cluster=cluster
                )
                alerts_generated += 1
                
        # Check for FIFO violations
        latest_compliance = FIFOCompliance.objects.order_by('-date').first()
        
        if latest_compliance and latest_compliance.compliance_percentage < 90:
            # Check if an alert already exists
            existing_alert = Alert.objects.filter(
                alert_type='fifo_violation',
                acknowledged=False
            ).first()
            
            if not existing_alert:
                Alert.objects.create(
                    alert_type='fifo_violation',
                    severity='warning',
                    title="FIFO compliance below threshold",
                    description=f"FIFO compliance is at {latest_compliance.compliance_percentage:.1f}%, which is below the 90% threshold."
                )
                alerts_generated += 1
                
        return Response({
            'message': f'Generated {alerts_generated} new alerts',
            'count': alerts_generated
        })
