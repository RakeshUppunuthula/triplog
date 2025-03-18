from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
import os
import uuid


def report_file_path(instance, filename):
    """Generate file path for report files"""
    ext = filename.split('.')[-1]
    filename = f"{instance.technician.id}_report_{uuid.uuid4().hex[:8]}.{ext}"
    return os.path.join('reports', filename)


def upload_file_path(instance, filename):
    """Generate file path for uploaded Excel files"""
    ext = filename.split('.')[-1]
    filename = f"upload_{uuid.uuid4().hex[:8]}.{ext}"
    return os.path.join('uploads', filename)


class DataFile(models.Model):
    """Model to store uploaded data files"""
    file = models.FileField(upload_to=upload_file_path)
    original_filename = models.CharField(max_length=255)
    upload_date = models.DateTimeField(default=timezone.now)
    processed = models.BooleanField(default=False)
    record_count = models.IntegerField(null=True, blank=True)
    
    def __str__(self):
        return self.original_filename


class Technician(models.Model):
    """Model to store technician information"""
    technician_id = models.IntegerField(unique=True)
    data_file = models.ForeignKey(DataFile, on_delete=models.CASCADE, related_name='technicians')
    
    def __str__(self):
        return f"Technician {self.technician_id}"
    
    class Meta:
        ordering = ['technician_id']


class TripRecord(models.Model):
    """Model to store trip records for technicians"""
    TRIP_TYPE_CHOICES = [
        ('punch_in', 'Punch In'),
        ('punch_out', 'Punch Out'),
        ('start_trip', 'Start Trip'),
        ('end_trip', 'End Trip'),
        ('pickup', 'Pickup'),
        ('delivery', 'Delivery'),
        ('other', 'Other'),
    ]
    
    technician = models.ForeignKey(Technician, on_delete=models.CASCADE, related_name='trips')
    trip_type = models.CharField(max_length=20, choices=TRIP_TYPE_CHOICES)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField(null=True, blank=True)
    location = models.CharField(max_length=255, blank=True, null=True)
    latitude = models.FloatField(
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
        null=True, 
        blank=True
    )
    longitude = models.FloatField(
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
        null=True, 
        blank=True
    )
    duplicate = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.technician} - {self.trip_type} at {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}"
    
    class Meta:
        ordering = ['technician', 'created_at']
        indexes = [
            models.Index(fields=['technician', 'created_at']),
            models.Index(fields=['trip_type']),
        ]


class Report(models.Model):
    """Model to store generated reports"""
    REPORT_TYPE_CHOICES = [
        ('pdf', 'PDF'),
        ('html', 'HTML'),
    ]
    
    technician = models.ForeignKey(Technician, on_delete=models.CASCADE, related_name='reports')
    file = models.FileField(upload_to=report_file_path)
    report_type = models.CharField(max_length=10, choices=REPORT_TYPE_CHOICES)
    created_at = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"Report for {self.technician} ({self.report_type})"
    
    class Meta:
        ordering = ['-created_at']


class DistanceData(models.Model):
    """Model to store calculated distance data"""
    technician = models.OneToOneField(Technician, on_delete=models.CASCADE, related_name='distance_data')
    total_distance = models.FloatField(default=0)
    trip_count = models.IntegerField(default=0)
    
    def __str__(self):
        return f"Distance data for {self.technician}"
    
    class Meta:
        verbose_name_plural = "Distance Data"