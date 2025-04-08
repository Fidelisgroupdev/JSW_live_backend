from django.contrib import admin
from .models import Cluster, CementBag, Movement

# Register your models here.

@admin.register(Cluster)
class ClusterAdmin(admin.ModelAdmin):
    list_display = ('name', 'location_x', 'location_y', 'current_count', 'max_capacity', 'utilization_percentage')
    list_filter = ('created_at',)
    search_fields = ('name',)
    readonly_fields = ('utilization_percentage', 'is_full', 'available_capacity')

@admin.register(CementBag)
class CementBagAdmin(admin.ModelAdmin):
    list_display = ('barcode', 'manufacture_date', 'entry_date', 'cluster', 'status', 'age_in_days')
    list_filter = ('status', 'manufacture_date', 'entry_date', 'cluster')
    search_fields = ('barcode',)
    readonly_fields = ('age_in_days', 'shelf_life_percentage')
    date_hierarchy = 'manufacture_date'

@admin.register(Movement)
class MovementAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'bag', 'source_cluster', 'destination_cluster', 'user', 'camera')
    list_filter = ('timestamp', 'source_cluster', 'destination_cluster', 'user', 'camera')
    search_fields = ('bag__barcode', 'notes')
    date_hierarchy = 'timestamp'
