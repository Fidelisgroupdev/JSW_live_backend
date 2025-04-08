"""
Views for the cement bag counter web interface.
"""
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny

@api_view(['GET'])
@permission_classes([AllowAny])
def cement_counter_view(request):
    """
    Render the cement bag counter web interface.
    """
    return render(request, 'camera/cement_counter.html')
