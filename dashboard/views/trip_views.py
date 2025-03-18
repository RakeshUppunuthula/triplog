from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.db.models import Count
from dashboard.models import DataFile, Technician, TripRecord
from dashboard.forms import TechnicianFilterForm
from dashboard.utils.data_processor import get_trip_type_distribution, get_punch_in_distribution


def trip_analysis(request, file_id):
    """Trip type analysis page"""
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
    
    return render(request, 'dashboard/trip_analysis.html', context)


def get_trip_type_chart_data(request, file_id):
    """Get trip type distribution chart data as JSON"""
    data_file = get_object_or_404(DataFile, id=file_id)
    
    # Filter by technician if provided
    technician_id = request.GET.get('technician')
    technician = None
    
    if technician_id:
        try:
            technician = Technician.objects.get(id=technician_id, data_file=data_file)
        except Technician.DoesNotExist:
            return JsonResponse({'error': 'Technician not found'}, status=404)
    
    # Get trip type distribution
    trip_distribution = get_trip_type_distribution(data_file, technician)
    
    # Format for frontend chart
    chart_data = {
        'labels': [item['trip_type'] for item in trip_distribution],
        'datasets': [{
            'label': 'Trip Count',
            'data': [item['count'] for item in trip_distribution],
            'backgroundColor': [
                '#4e73df', '#1cc88a', '#36b9cc', '#f6c23e', 
                '#e74a3b', '#5a5c69', '#858796', '#6610f2'
            ],
        }]
    }
    
    return JsonResponse(chart_data)


def get_punch_in_chart_data(request, file_id):
    """Get punch-in distribution by hour chart data as JSON"""
    data_file = get_object_or_404(DataFile, id=file_id)
    
    # Filter by technician if provided
    technician_id = request.GET.get('technician')
    technician = None
    
    if technician_id:
        try:
            technician = Technician.objects.get(id=technician_id, data_file=data_file)
        except Technician.DoesNotExist:
            return JsonResponse({'error': 'Technician not found'}, status=404)
    
    # Get punch-in distribution
    punch_distribution = get_punch_in_distribution(data_file, technician)
    
    # Format for frontend chart
    chart_data = {
        'labels': [item['label'] for item in punch_distribution],
        'datasets': [{
            'label': 'Punch-in Count',
            'data': [item['count'] for item in punch_distribution],
            'backgroundColor': '#4e73df',
            'borderColor': '#2e59d9',
            'borderWidth': 1
        }]
    }
    
    return JsonResponse(chart_data)


def get_trip_type_summary(request, file_id):
    """Get trip type summary statistics as JSON"""
    data_file = get_object_or_404(DataFile, id=file_id)
    
    # Filter by technician if provided
    technician_id = request.GET.get('technician')
    technician = None
    
    if technician_id:
        try:
            technician = Technician.objects.get(id=technician_id, data_file=data_file)
        except Technician.DoesNotExist:
            return JsonResponse({'error': 'Technician not found'}, status=404)
    
    # Get trip type distribution
    trip_distribution = get_trip_type_distribution(data_file, technician)
    
    # Check if we have punch-in/out records
    has_punch_records = any(item['trip_type'] in ['punch_in', 'punch_out'] for item in trip_distribution)
    
    # Get total count
    total_count = sum(item['count'] for item in trip_distribution)
    
    summary = {
        'trip_types': trip_distribution,
        'total_count': total_count,
        'has_punch_records': has_punch_records
    }
    
    return JsonResponse(summary)