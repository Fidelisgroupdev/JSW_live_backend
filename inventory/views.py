from django.shortcuts import render
from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.utils import timezone
from django.db.models import Q
import uuid
import datetime

from .models import Cluster, CementBag, Movement
from .serializers import (
    ClusterSerializer, ClusterDetailSerializer,
    CementBagSerializer, CementBagDetailSerializer,
    MovementSerializer, BulkBagCreateSerializer
)

class ClusterViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing clusters.
    """
    queryset = Cluster.objects.all()
    serializer_class = ClusterSerializer
    permission_classes = [AllowAny]  # Allow unauthenticated access for testing
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name']
    ordering_fields = ['name', 'current_count', 'max_capacity', 'created_at']
    
    def get_serializer_class(self):
        if self.action == 'retrieve' or self.action == 'bags':
            return ClusterDetailSerializer
        return ClusterSerializer
    
    @action(detail=True, methods=['get'])
    def bags(self, request, pk=None):
        """
        Return all bags in a specific cluster.
        """
        cluster = self.get_object()
        bags = cluster.bags.all()
        
        # Apply filters if provided
        status_filter = request.query_params.get('status', None)
        if status_filter:
            bags = bags.filter(status=status_filter)
            
        # Apply sorting
        sort_by = request.query_params.get('sort_by', 'entry_date')
        sort_order = '-' if request.query_params.get('desc', 'false').lower() == 'true' else ''
        bags = bags.order_by(f'{sort_order}{sort_by}')
        
        page = self.paginate_queryset(bags)
        if page is not None:
            serializer = CementBagSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
            
        serializer = CementBagSerializer(bags, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def adjust_count(self, request, pk=None):
        """
        Manually adjust the bag count for a cluster.
        """
        cluster = self.get_object()
        new_count = request.data.get('count', None)
        
        if new_count is None:
            return Response(
                {'error': 'Count parameter is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            new_count = int(new_count)
            if new_count < 0:
                return Response(
                    {'error': 'Count cannot be negative'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            # Update the cluster count
            cluster.current_count = new_count
            cluster.save()
            
            # Return the updated cluster
            serializer = self.get_serializer(cluster)
            return Response(serializer.data)
            
        except ValueError:
            return Response(
                {'error': 'Count must be an integer'}, 
                status=status.HTTP_400_BAD_REQUEST
            )


class CementBagViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing cement bags.
    """
    queryset = CementBag.objects.all()
    serializer_class = CementBagSerializer
    permission_classes = [AllowAny]  # Allow unauthenticated access for testing
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['barcode']
    ordering_fields = ['barcode', 'manufacture_date', 'entry_date', 'status']
    
    def get_serializer_class(self):
        if self.action == 'retrieve' or self.action == 'history':
            return CementBagDetailSerializer
        elif self.action == 'bulk_create':
            return BulkBagCreateSerializer
        return CementBagSerializer
    
    def get_queryset(self):
        queryset = CementBag.objects.all()
        
        # Filter by status if provided
        status = self.request.query_params.get('status', None)
        if status:
            queryset = queryset.filter(status=status)
            
        # Filter by cluster if provided
        cluster_id = self.request.query_params.get('cluster', None)
        if cluster_id:
            queryset = queryset.filter(cluster_id=cluster_id)
            
        # Filter by age if provided
        min_age = self.request.query_params.get('min_age', None)
        max_age = self.request.query_params.get('max_age', None)
        
        if min_age:
            min_date = timezone.now().date() - datetime.timedelta(days=int(min_age))
            queryset = queryset.filter(manufacture_date__lte=min_date)
            
        if max_age:
            max_date = timezone.now().date() - datetime.timedelta(days=int(max_age))
            queryset = queryset.filter(manufacture_date__gte=max_date)
            
        return queryset
    
    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        """
        Return the movement history of a specific bag.
        """
        bag = self.get_object()
        movements = bag.movements.all().order_by('-timestamp')
        
        page = self.paginate_queryset(movements)
        if page is not None:
            serializer = MovementSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
            
        serializer = MovementSerializer(movements, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        """
        Create multiple cement bags at once.
        """
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            count = serializer.validated_data['count']
            manufacture_date = serializer.validated_data['manufacture_date']
            cluster = serializer.validated_data.get('cluster', None)
            status = serializer.validated_data.get('status', 'available')
            barcode_prefix = serializer.validated_data.get('barcode_prefix', 'BAG')
            
            # Create the bags
            bags = []
            for i in range(count):
                # Generate a unique barcode
                barcode = f"{barcode_prefix}-{uuid.uuid4().hex[:8].upper()}"
                
                # Create the bag
                bag = CementBag(
                    barcode=barcode,
                    manufacture_date=manufacture_date,
                    entry_date=timezone.now(),
                    cluster=cluster,
                    status=status
                )
                bags.append(bag)
                
            # Bulk create the bags
            created_bags = CementBag.objects.bulk_create(bags)
            
            # If a cluster was specified, update its count
            if cluster:
                cluster.current_count += count
                cluster.save()
                
            # Create movement records for the new bags
            movements = []
            for bag in created_bags:
                if cluster:
                    movement = Movement(
                        source_cluster=None,
                        destination_cluster=cluster,
                        bag=bag,
                        user=request.user if request.user.is_authenticated else None,
                        confidence_score=1.0,
                        notes="Bulk creation"
                    )
                    movements.append(movement)
                    
            if movements:
                Movement.objects.bulk_create(movements)
                
            return Response({
                'message': f'Successfully created {count} bags',
                'count': count,
                'first_barcode': created_bags[0].barcode if created_bags else None
            }, status=status.HTTP_201_CREATED)
            
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def move(self, request, pk=None):
        """
        Move a bag to a different cluster.
        """
        bag = self.get_object()
        destination_cluster_id = request.data.get('destination_cluster', None)
        
        if destination_cluster_id is None:
            return Response(
                {'error': 'Destination cluster is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            destination_cluster = Cluster.objects.get(pk=destination_cluster_id)
            
            # Check if the destination cluster is full
            if destination_cluster.is_full:
                return Response(
                    {'error': 'Destination cluster is at full capacity'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            # Create a movement record
            movement = Movement(
                source_cluster=bag.cluster,
                destination_cluster=destination_cluster,
                bag=bag,
                user=request.user if request.user.is_authenticated else None,
                confidence_score=1.0,
                notes=request.data.get('notes', 'Manual movement')
            )
            movement.save()  # This will also update the bag's cluster and cluster counts
            
            # Return the updated bag
            serializer = CementBagDetailSerializer(bag)
            return Response(serializer.data)
            
        except Cluster.DoesNotExist:
            return Response(
                {'error': 'Destination cluster not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )


class MovementViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing movements.
    """
    queryset = Movement.objects.all().order_by('-timestamp')
    serializer_class = MovementSerializer
    permission_classes = [AllowAny]  # Allow unauthenticated access for testing
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['bag__barcode', 'notes']
    ordering_fields = ['timestamp', 'confidence_score']
    
    def get_queryset(self):
        queryset = Movement.objects.all()
        
        # Filter by source cluster if provided
        source_cluster = self.request.query_params.get('source_cluster', None)
        if source_cluster:
            queryset = queryset.filter(source_cluster_id=source_cluster)
            
        # Filter by destination cluster if provided
        destination_cluster = self.request.query_params.get('destination_cluster', None)
        if destination_cluster:
            queryset = queryset.filter(destination_cluster_id=destination_cluster)
            
        # Filter by bag if provided
        bag = self.request.query_params.get('bag', None)
        if bag:
            queryset = queryset.filter(bag_id=bag)
            
        # Filter by date range if provided
        start_date = self.request.query_params.get('start_date', None)
        end_date = self.request.query_params.get('end_date', None)
        
        if start_date:
            queryset = queryset.filter(timestamp__gte=start_date)
            
        if end_date:
            queryset = queryset.filter(timestamp__lte=end_date)
            
        # Filter by movement type
        movement_type = self.request.query_params.get('type', None)
        if movement_type == 'entry':
            queryset = queryset.filter(source_cluster__isnull=True, destination_cluster__isnull=False)
        elif movement_type == 'exit':
            queryset = queryset.filter(source_cluster__isnull=False, destination_cluster__isnull=True)
        elif movement_type == 'internal':
            queryset = queryset.filter(source_cluster__isnull=False, destination_cluster__isnull=False)
            
        return queryset
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        Return movement statistics.
        """
        # Get date range from query parameters or default to last 30 days
        days = int(request.query_params.get('days', 30))
        end_date = timezone.now()
        start_date = end_date - datetime.timedelta(days=days)
        
        # Filter movements by date range
        movements = Movement.objects.filter(timestamp__gte=start_date, timestamp__lte=end_date)
        
        # Calculate statistics
        total_movements = movements.count()
        entries = movements.filter(source_cluster__isnull=True, destination_cluster__isnull=False).count()
        exits = movements.filter(source_cluster__isnull=False, destination_cluster__isnull=True).count()
        internal = movements.filter(source_cluster__isnull=False, destination_cluster__isnull=False).count()
        
        # Get top clusters by movement activity
        source_clusters = {}
        destination_clusters = {}
        
        for movement in movements:
            if movement.source_cluster:
                source_clusters[movement.source_cluster.id] = source_clusters.get(movement.source_cluster.id, 0) + 1
            if movement.destination_cluster:
                destination_clusters[movement.destination_cluster.id] = destination_clusters.get(movement.destination_cluster.id, 0) + 1
        
        # Sort clusters by activity
        top_source_clusters = sorted(source_clusters.items(), key=lambda x: x[1], reverse=True)[:5]
        top_destination_clusters = sorted(destination_clusters.items(), key=lambda x: x[1], reverse=True)[:5]
        
        # Get cluster details
        top_source_clusters_data = []
        for cluster_id, count in top_source_clusters:
            cluster = Cluster.objects.get(pk=cluster_id)
            top_source_clusters_data.append({
                'id': cluster.id,
                'name': cluster.name,
                'count': count
            })
            
        top_destination_clusters_data = []
        for cluster_id, count in top_destination_clusters:
            cluster = Cluster.objects.get(pk=cluster_id)
            top_destination_clusters_data.append({
                'id': cluster.id,
                'name': cluster.name,
                'count': count
            })
        
        return Response({
            'total_movements': total_movements,
            'entries': entries,
            'exits': exits,
            'internal': internal,
            'top_source_clusters': top_source_clusters_data,
            'top_destination_clusters': top_destination_clusters_data,
            'period': {
                'start_date': start_date,
                'end_date': end_date,
                'days': days
            }
        })
