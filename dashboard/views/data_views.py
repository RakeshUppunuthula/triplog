from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from dashboard.models import DataFile, Technician, TripRecord
from dashboard.forms import FileUploadForm
from dashboard.utils.data_processor import process_excel_file


def index(request):
    """Dashboard home page"""
    # Get the most recent data file
    latest_file = DataFile.objects.order_by('-upload_date').first()
    
    # Get upload form
    form = FileUploadForm()
    
    context = {
        'form': form,
        'latest_file': latest_file,
        'file_count': DataFile.objects.count(),
        'data_files': DataFile.objects.all().order_by('-upload_date')[:5]
    }
    
    return render(request, 'dashboard/index.html', context)


def upload_file(request):
    """Handle file upload"""
    if request.method == 'POST':
        form = FileUploadForm(request.POST, request.FILES)
        if form.is_valid():
            # Save the file
            data_file = form.save()
            
            # Process the file
            result = process_excel_file(data_file)
            
            if result['success']:
                messages.success(request, f"File processed successfully: {result['record_count']} records, {result['technician_count']} technicians")
                return redirect('data_overview', file_id=data_file.id)
            else:
                # Delete the file if processing failed
                data_file.delete()
                messages.error(request, f"Error processing file: {result['error']}")
                return redirect('index')
    else:
        form = FileUploadForm()
    
    return render(request, 'dashboard/upload.html', {'form': form})


def data_overview(request, file_id):
    """Data overview page"""
    data_file = get_object_or_404(DataFile, id=file_id)
    
    # Get technicians for this file
    technicians = Technician.objects.filter(data_file=data_file)
    
    # Get sample data
    sample_data = TripRecord.objects.filter(
        technician__data_file=data_file
    ).select_related('technician').order_by('created_at')[:10]
    
    # Get column names for display
    columns = [
        'ID', 'Technician', 'Trip Type', 'Created At', 
        'Location', 'Latitude', 'Longitude', 'Duplicate'
    ]
    
    # Format sample data for display
    formatted_data = []
    for record in sample_data:
        formatted_data.append({
            'id': record.id,
            'technician': f"Technician {record.technician.technician_id}",
            'trip_type': record.trip_type,
            'created_at': record.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'location': record.location if record.location else 'N/A',
            'latitude': f"{record.latitude:.6f}" if record.latitude else 'N/A',
            'longitude': f"{record.longitude:.6f}" if record.longitude else 'N/A',
            'duplicate': 'Yes' if record.duplicate else 'No'
        })
    
    # Basic summary stats
    stats = {
        'record_count': TripRecord.objects.filter(technician__data_file=data_file).count(),
        'technician_count': technicians.count(),
        'duplicate_count': TripRecord.objects.filter(technician__data_file=data_file, duplicate=True).count(),
    }
    
    # If we have trip_type field, add trip type counts
    trip_counts = TripRecord.objects.filter(
        technician__data_file=data_file, 
        duplicate=False
    ).values('trip_type').annotate(
        count=Count('id')
    ).order_by('-count')
    
    if trip_counts.exists():
        stats['trip_types'] = [
            {'trip_type': item['trip_type'], 'count': item['count']}
            for item in trip_counts
        ]
    
    # Get date range
    if sample_data.exists():
        first_record = TripRecord.objects.filter(
            technician__data_file=data_file
        ).order_by('created_at').first()
        
        last_record = TripRecord.objects.filter(
            technician__data_file=data_file
        ).order_by('created_at').last()
        
        if first_record and last_record:
            stats['date_range'] = {
                'start': first_record.created_at.strftime('%Y-%m-%d'),
                'end': last_record.created_at.strftime('%Y-%m-%d')
            }
    
    context = {
        'data_file': data_file,
        'technicians': technicians,
        'sample_data': formatted_data,
        'columns': columns,
        'stats': stats
    }
    
    return render(request, 'dashboard/data_overview.html', context)


@require_POST
def delete_file(request, file_id):
    """Delete a data file"""
    data_file = get_object_or_404(DataFile, id=file_id)
    
    # Delete the file
    data_file.delete()
    
    messages.success(request, "File deleted successfully")
    return redirect('index')


def switch_file(request):
    """Switch to a different data file"""
    if request.method == 'POST':
        file_id = request.POST.get('file_id')
        if file_id:
            return redirect('data_overview', file_id=file_id)
    
    return redirect('index')