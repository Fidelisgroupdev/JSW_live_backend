from rest_framework import serializers
from .models import Cluster, CementBag, Movement

class ClusterSerializer(serializers.ModelSerializer):
    """
    Serializer for Cluster model.
    """
    utilization_percentage = serializers.FloatField(read_only=True)
    available_capacity = serializers.IntegerField(read_only=True)
    is_full = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Cluster
        fields = [
            'id', 'name', 'location_x', 'location_y', 'length', 'width',
            'max_capacity', 'current_count', 'utilization_percentage',
            'available_capacity', 'is_full', 'created_at', 'updated_at'
        ]


class CementBagSerializer(serializers.ModelSerializer):
    """
    Serializer for CementBag model.
    """
    age_in_days = serializers.IntegerField(read_only=True)
    shelf_life_percentage = serializers.FloatField(read_only=True)
    cluster_name = serializers.CharField(source='cluster.name', read_only=True)
    
    class Meta:
        model = CementBag
        fields = [
            'id', 'barcode', 'manufacture_date', 'entry_date', 'cluster',
            'cluster_name', 'status', 'age_in_days', 'shelf_life_percentage',
            'created_at', 'updated_at'
        ]


class MovementSerializer(serializers.ModelSerializer):
    """
    Serializer for Movement model.
    """
    source_cluster_name = serializers.CharField(source='source_cluster.name', read_only=True)
    destination_cluster_name = serializers.CharField(source='destination_cluster.name', read_only=True)
    bag_barcode = serializers.CharField(source='bag.barcode', read_only=True)
    user_username = serializers.CharField(source='user.username', read_only=True)
    camera_name = serializers.CharField(source='camera.name', read_only=True)
    
    class Meta:
        model = Movement
        fields = [
            'id', 'timestamp', 'source_cluster', 'source_cluster_name',
            'destination_cluster', 'destination_cluster_name', 'bag', 'bag_barcode',
            'user', 'user_username', 'camera', 'camera_name', 'confidence_score', 'notes'
        ]


class ClusterDetailSerializer(ClusterSerializer):
    """
    Detailed serializer for Cluster model including bags.
    """
    bags = CementBagSerializer(many=True, read_only=True)
    
    class Meta(ClusterSerializer.Meta):
        fields = ClusterSerializer.Meta.fields + ['bags']


class CementBagDetailSerializer(CementBagSerializer):
    """
    Detailed serializer for CementBag model including movement history.
    """
    movements = MovementSerializer(many=True, read_only=True)
    
    class Meta(CementBagSerializer.Meta):
        fields = CementBagSerializer.Meta.fields + ['movements']


class BulkBagCreateSerializer(serializers.Serializer):
    """
    Serializer for bulk creation of cement bags.
    """
    count = serializers.IntegerField(min_value=1, max_value=1000)
    manufacture_date = serializers.DateField()
    cluster = serializers.PrimaryKeyRelatedField(queryset=Cluster.objects.all(), required=False)
    status = serializers.ChoiceField(choices=CementBag.STATUS_CHOICES, default='available')
    barcode_prefix = serializers.CharField(max_length=10, required=False, default='BAG')
