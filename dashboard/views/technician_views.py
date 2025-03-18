from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.db.models import Count
from dashboard.models import DataFile, Technician, TripRecord
from dashboard.forms import TechnicianFilterForm
from datetime import datetime


def technician_logs(request, file_id):
    """Technician logs page"""
    data_file = get_object_or_404(DataFile, id=file_id)
    
    # Get form for selecting technician
    form = TechnicianFilterForm(data_file=data_file)
    
    # Get the selected technician if any
    technician_id = request.GET.get('technician')
    technician = None
    
    if technician_id:
        try:
            technician = Technician.objects.get(id=technician_id, data_file=data_file)
            form = TechnicianFilterForm(data_file=data_file, initial={'technician': technician})
        except Technician.DoesNotExist:
            pass
    
    context = {
        'data_file': data_file,
        'form': form,
        'technician': technician
    }
    
    return render(request, 'dashboard/technician_logs.html', context)


def get_technician_summary(request, file_id, technician_id):
    """Get summary data for a technician as JSON"""
    data_file = get_object_or_404(DataFile, id=file_id)
    technician = get_object_or_404(Technician, id=technician_id, data_file=data_file)
    
    # Get all trip records for this technician
    trip_records = TripRecord.objects.filter(technician=technician, duplicate=False)
    
    # Get punch-in and punch-out records
    punch_in_records = trip_records.filter(trip_type='punch_in')
    punch_out_records = trip_records.filter(trip_type='punch_out')
    
    # Get trip type counts
    trip_type_counts = trip_records.values('trip_type').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Format trip type counts
    trip_types = [
        {'trip_type': item['trip_type'], 'count': item['count']}
        for item in trip_type_counts
    ]
    
    summary = {
        'technician_id': technician.technician_id,
        'total_records': trip_records.count(),
        'punch_in_count': punch_in_records.count(),
        'punch_out_count': punch_out_records.count(),
        'trip_types': trip_types
    }
    
    # Get date range if records exist
    if trip_records.exists():
        first_record = trip_records.order_by('created_at').first()
        last_record = trip_records.order_by('created_at').last()
        
        if first_record and last_record:
            summary['date_range'] = {
                'start': first_record.created_at.strftime('%Y-%m-%d'),
                'end': last_record.created_at.strftime('%Y-%m-%d')
            }
    
    return JsonResponse(summary)


def get_punch_in_out_data(request, file_id, technician_id):
    """Get punch-in/out data for a technician as JSON"""
    data_file = get_object_or_404(DataFile, id=file_id)
    technician = get_object_or_404(Technician, id=technician_id, data_file=data_file)
    
    # Get punch-in and punch-out records
    punch_in_records = TripRecord.objects.filter(
        technician=technician, 
        trip_type='punch_in',
        duplicate=False
    ).order_by('created_at')
    
    punch_out_records = TripRecord.objects.filter(
        technician=technician, 
        trip_type='punch_out',
        duplicate=False
    ).order_by('created_at')
    
    # Group by date
    daily_records = {}
    
    # Process punch-in records
    for record in punch_in_records:
        date_str = record.created_at.strftime('%Y-%m-%d')
        time_str = record.created_at.strftime('%H:%M:%S')
        
        if date_str not in daily_records:
            daily_records[date_str] = {
                'date': date_str,
                'punch_in_times': [],
                'punch_out_times': []
            }
        
        daily_records[date_str]['punch_in_times'].append(time_str)
    
    # Process punch-out records
    for record in punch_out_records:
        date_str = record.created_at.strftime('%Y-%m-%d')
        time_str = record.created_at.strftime('%H:%M:%S')
        
        if date_str not in daily_records:
            daily_records[date_str] = {
                'date': date_str,
                'punch_in_times': [],
                'punch_out_times': []
            }
        
        daily_records[date_str]['punch_out_times'].append(time_str)
    
    # Convert to list and sort by date
    result = list(daily_records.values())
    result.sort(key=lambda x: x['date'])
    
    return JsonResponse({'daily_records': result})


def get_timeline_data(request, file_id, technician_id):
    """Get timeline data for a technician as JSON"""
    data_file = get_object_or_404(DataFile, id=file_id)
    technician = get_object_or_404(Technician, id=technician_id, data_file=data_file)
    
    # Get all trip records for this technician
    trip_records = TripRecord.objects.filter(
        technician=technician, 
        duplicate=False
    ).order_by('created_at')
    
    # Format for Plotly timeline chart
    timeline_data = []
    
    for record in trip_records:
        event = {
            'id': record.id,
            'trip_type': record.trip_type,
            'created_at': record.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'location': record.location if record.location else 'N/A'
        }
        
        if record.latitude is not None and record.longitude is not None:
            event['coordinates'] = f"({record.latitude:.6f}, {record.longitude:.6f})"
        
        timeline_data.append(event)
    
    return JsonResponse({
        'timeline_data': timeline_data,
        'trip_types': list(set(record.trip_type for record in trip_records))
    })