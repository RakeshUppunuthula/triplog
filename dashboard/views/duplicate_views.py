from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.db.models import Count
from dashboard.models import DataFile, Technician, TripRecord
from dashboard.forms import TechnicianFilterForm


def duplicate_analysis(request, file_id):
    """Duplicate records analysis page"""
    data_file = get_object_or_404(DataFile, id=file_id)
    
    # Get technician filter form
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
    
    return render(request, 'dashboard/duplicate_analysis.html', context)


def get_duplicate_summary(request, file_id):
    """Get duplicate records summary as JSON"""
    data_file = get_object_or_404(DataFile, id=file_id)
    
    # Filter by technician if provided
    technician_id = request.GET.get('technician')
    
    base_query = TripRecord.objects.filter(technician__data_file=data_file)
    
    if technician_id:
        try:
            technician = Technician.objects.get(id=technician_id, data_file=data_file)
            base_query = base_query.filter(technician=technician)
        except Technician.DoesNotExist:
            return JsonResponse({'error': 'Technician not found'}, status=404)
    
    # Get duplicate records
    duplicate_records = base_query.filter(duplicate=True)
    
    # Count by trip type
    trip_type_counts = duplicate_records.values('trip_type').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Calculate percentages
    total_records = base_query.count()
    duplicate_count = duplicate_records.count()
    duplicate_percent = round((duplicate_count / total_records) * 100, 2) if total_records > 0 else 0
    
    # Format trip type counts for the frontend
    trip_types = [
        {'trip_type': item['trip_type'], 'count': item['count']}
        for item in trip_type_counts
    ]
    
    summary = {
        'total_records': total_records,
        'duplicate_count': duplicate_count,
        'duplicate_percent': duplicate_percent,
        'trip_types': trip_types
    }
    
    return JsonResponse(summary)


def get_duplicate_records(request, file_id):
    """Get duplicate records as JSON for display in table"""
    data_file = get_object_or_404(DataFile, id=file_id)
    
    # Filter by technician if provided
    technician_id = request.GET.get('technician')
    
    base_query = TripRecord.objects.filter(
        technician__data_file=data_file,
        duplicate=True
    ).select_related('technician')
    
    if technician_id:
        try:
            technician = Technician.objects.get(id=technician_id, data_file=data_file)
            base_query = base_query.filter(technician=technician)
        except Technician.DoesNotExist:
            return JsonResponse({'error': 'Technician not found'}, status=404)
    
    # Paginate results
    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 20))
    
    start = (page - 1) * page_size
    end = start + page_size
    
    # Get a slice of records
    records = base_query.order_by('technician__technician_id', 'created_at')[start:end]
    
    # Format for the frontend
    formatted_records = []
    for record in records:
        formatted_records.append({
            'id': record.id,
            'technician_id': record.technician.technician_id,
            'trip_type': record.trip_type,
            'created_at': record.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'location': record.location if record.location else 'N/A',
            'latitude': f"{record.latitude:.6f}" if record.latitude else 'N/A',
            'longitude': f"{record.longitude:.6f}" if record.longitude else 'N/A',
        })
    
    # Total count for pagination
    total_count = base_query.count()
    
    result = {
        'records': formatted_records,
        'total_count': total_count,
        'page': page,
        'page_size': page_size,
        'total_pages': (total_count + page_size - 1) // page_size
    }
    
    return JsonResponse(result)