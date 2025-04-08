"""
cement_track URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework import routers

from users.views import UserViewSet
from inventory.views import ClusterViewSet, CementBagViewSet, MovementViewSet
from camera.views import CameraViewSet, DetectionEventViewSet, test_rtsp_url
from analytics.views import (
    InventorySnapshotViewSet, MovementAnalyticsViewSet,
    FIFOComplianceViewSet, AlertViewSet
)

# API Router
router = routers.DefaultRouter()
# Users
router.register(r'users', UserViewSet)
# Inventory
router.register(r'clusters', ClusterViewSet)
router.register(r'bags', CementBagViewSet)
router.register(r'movements', MovementViewSet)
# Camera
router.register(r'cameras', CameraViewSet)
router.register(r'detection-events', DetectionEventViewSet)
# Analytics
router.register(r'inventory-snapshots', InventorySnapshotViewSet)
router.register(r'movement-analytics', MovementAnalyticsViewSet)
router.register(r'fifo-compliance', FIFOComplianceViewSet)
router.register(r'alerts', AlertViewSet)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),
    path('api/auth/', include('rest_framework.urls', namespace='rest_framework')),
    # Include camera app URLs
    path('api/camera/', include('camera.urls')),
    # Serve static files in development
    *static(settings.STATIC_URL, document_root=settings.STATIC_ROOT),
    *static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT),
]
