from django.contrib.auth.models import AbstractUser
from django.db import models

# Create your models here.

class User(AbstractUser):
    """
    Custom user model for the CementTrack system.
    Extends Django's AbstractUser to add additional fields.
    """
    ROLE_CHOICES = (
        ('admin', 'Administrator'),
        ('manager', 'Warehouse Manager'),
        ('operator', 'Warehouse Operator'),
        ('viewer', 'Viewer'),
    )
    
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='viewer')
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    department = models.CharField(max_length=50, blank=True, null=True)
    last_login_ip = models.GenericIPAddressField(blank=True, null=True)
    
    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
    
    def __str__(self):
        return self.username
