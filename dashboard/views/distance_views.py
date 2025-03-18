from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib import messages
from django.views.decorators.http import require_POST
from dashboard.models import DataFile, Technician, DistanceData
from dashboard.forms import TechnicianFilterForm
from dashboard.utils.distance_analyzer import (
    calculate_technician_distances,
    get_trip_locations,
    get_distance_summary
)


def distance_analysis(request, file_id):
    """Distance analysis page"""
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
    
    return render(request, 'dashboard/distance_analysis.html', context)


@require_POST
def calculate_distances(request, file_id):
    """Calculate distances for all technicians in a data file"""
    data_file = get_object_or_404(DataFile, id=file_id)
    
    # Get technician if specified
    technician_id = request.POST.get('technician')
    technician = None
    
    if technician_id:
        try:
            technician = Technician.objects.get(id=technician_id, data_file=data_file)
        except Technician.DoesNotExist:
            return JsonResponse({'error': 'Technician not found'}, status=404)
    
    # Calculate distances
    results = calculate_technician_distances(data_file, technician)
    
    # Return success message with count of technicians processed
    return JsonResponse({
        'success': True,
        'message': f"Distance calculation completed for {len(results)} technician(s)",
        'results': results
    })


def get_distance_data(request, file_id):
    """Get distance data as JSON"""
    data_file = get_object_or_404(DataFile, id=file_id)
    
    # Get technician if specified
    technician_id = request.GET.get('technician')
    technician = None
    
    if technician_id:
        try:
            technician = Technician.objects.get(id=technician_id, data_file=data_file)
        except Technician.DoesNotExist:
            return JsonResponse({'error': 'Technician not found'}, status=404)
    
    # Get distance summary
    summary = get_distance_summary(data_file, technician)
    
    return JsonResponse(summary)


def get_location_map_data(request, file_id, technician_id):
    """Get location data for map visualization as JSON"""
    data_file = get_object_or_404(DataFile, id=file_id)
    technician = get_object_or_404(Technician, id=technician_id, data_file=data_file)
    
    # Get location data
    locations = get_trip_locations(technician)
    
    if not locations:
        return JsonResponse({
            'success': False,
            'message': 'No location data available'
        })
    
    # Count trip types for bar chart
    trip_type_counts = {}
    for loc in locations:
        trip_type = loc['trip_type']
        trip_type_counts[trip_type] = trip_type_counts.get(trip_type, 0) + 1
    
    # Format for frontend chart
    trip_data = [
        {'trip_type': trip_type, 'count': count}
        for trip_type, count in trip_type_counts.items()
    ]
    
    return JsonResponse({
        'success': True,
        'locations': locations,
        'trip_data': trip_data
    })


def get_distance_chart_data(request, file_id):
    """Get distance chart data as JSON"""
    data_file = get_object_or_404(DataFile, id=file_id)
    
    # Get all distance data for this file
    distance_data = DistanceData.objects.filter(
        technician__data_file=data_file
    ).select_related('technician').order_by('-total_distance')
    
    if not distance_data.exists():
        return JsonResponse({
            'success': False,
            'message': 'No distance data available'
        })
    
    # Format for frontend chart
    chart_data = {
        'labels': [f"Tech {item.technician.technician_id}" for item in distance_data],
        'datasets': [{
            'label': 'Total Distance (km)',
            'data': [item.total_distance for item in distance_data],
            'backgroundColor': '#4e73df',
            'borderColor': '#2e59d9',
            'borderWidth': 1
        }]
    }
    
    return JsonResponse({
        'success': True,
        'chart_data': chart_data
    })