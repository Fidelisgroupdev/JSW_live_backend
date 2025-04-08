from django.shortcuts import render
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from .serializers import UserSerializer, UserProfileSerializer

User = get_user_model()

class UserViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing users.
    """
    queryset = User.objects.all().order_by('-date_joined')
    serializer_class = UserSerializer
    
    def get_permissions(self):
        """
        Custom permissions:
        - Admin users can perform any action
        - Users can view their own profile and update certain fields
        - List action requires authentication
        """
        if self.action == 'retrieve' or self.action == 'me' or self.action == 'update_profile':
            permission_classes = [permissions.IsAuthenticated]
        else:
            permission_classes = [permissions.IsAdminUser]
        return [permission() for permission in permission_classes]
    
    def get_serializer_class(self):
        """
        Use different serializers based on the action.
        """
        if self.action == 'me' or self.action == 'update_profile':
            return UserProfileSerializer
        return UserSerializer
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        """
        Return the authenticated user's profile.
        """
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)
    
    @action(detail=False, methods=['put', 'patch'])
    def update_profile(self, request):
        """
        Update the authenticated user's profile.
        """
        user = request.user
        serializer = self.get_serializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """
        Activate a user account.
        """
        user = self.get_object()
        user.is_active = True
        user.save()
        return Response({'status': 'user activated'})
    
    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """
        Deactivate a user account.
        """
        user = self.get_object()
        user.is_active = False
        user.save()
        return Response({'status': 'user deactivated'})
