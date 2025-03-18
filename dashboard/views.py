from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, FileResponse
from django.views.decorators.http import require_POST
from django.db.models import Count
from django.conf import settings
import os
import datetime
import uuid
import pandas as pd
import numpy as np

from dashboard.models import DataFile, Technician, TripRecord, Report, DistanceData
from dashboard.forms import FileUploadForm, TechnicianFilterForm, ReportGenerationForm
from dashboard.utils.data_processor import process_excel_file, get_trip_type_distribution, get_punch_in_distribution
from dashboard.utils.distance_analyzer import calculate_technician_distances, get_trip_locations, get_distance_summary
from dashboard.utils.report_generator import generate_technician_report

# ------------------------------
# Data Views
# ------------------------------

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

# ------------------------------
# Duplicate Analysis Views
# ------------------------------

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

# ------------------------------
# Trip Analysis Views
# ------------------------------

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

# ------------------------------
# Technician Logs Views
# ------------------------------

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
            'technician_id': technician.technician_id,
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

# ------------------------------
# Distance Analysis Views
# ------------------------------

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

# ------------------------------
# Report Generation Views
# ------------------------------

def report_generation(request, file_id):
    """Report generation page"""
    data_file = get_object_or_404(DataFile, id=file_id)
    
    # Get form for report generation
    form = ReportGenerationForm(data_file=data_file)
    
    # Get recent reports for this data file
    recent_reports = Report.objects.filter(
        technician__data_file=data_file
    ).select_related('technician').order_by('-created_at')[:5]
    
    context = {
        'data_file': data_file,
        'form': form,
        'recent_reports': recent_reports
    }
    
    return render(request, 'dashboard/report_generation.html', context)


@require_POST
def generate_report(request, file_id):
    """Generate a report for a technician"""
    data_file = get_object_or_404(DataFile, id=file_id)
    
    form = ReportGenerationForm(request.POST, data_file=data_file)
    
    if form.is_valid():
        technician_id = form.cleaned_data['technician'].id
        report_format = form.cleaned_data['report_type']
        
        # Get technician
        technician = get_object_or_404(Technician, id=technician_id, data_file=data_file)
        
        # Generate report
        report, message = generate_technician_report(technician, report_format)
        
        if report:
            # Success
            messages.success(request, message)
            return redirect('view_report', report_id=report.id)
        else:
            # Error
            messages.error(request, message)
    else:
        messages.error(request, "Please select a technician and report format")
    
    return redirect('report_generation', file_id=file_id)


def view_report(request, report_id):
    """View a generated report"""
    report = get_object_or_404(Report, id=report_id)
    
    # Get the file path
    file_path = os.path.join(settings.MEDIA_ROOT, report.file.name)
    
    # Check if file exists
    if not os.path.exists(file_path):
        messages.error(request, "Report file not found")
        return redirect('report_generation', file_id=report.technician.data_file.id)
    
    # Get file extension
    file_ext = os.path.splitext(file_path)[1].lower()
    
    # Set the appropriate content type
    if file_ext == '.pdf':
        content_type = 'application/pdf'
    elif file_ext == '.html':
        content_type = 'text/html'
    else:
        content_type = 'application/octet-stream'
    
    # Return the file
    return FileResponse(
        open(file_path, 'rb'),
        content_type=content_type,
        as_attachment=False,
        filename=os.path.basename(file_path)
    )


def download_report(request, report_id):
    """Download a generated report"""
    report = get_object_or_404(Report, id=report_id)
    
    # Get the file path
    file_path = os.path.join(settings.MEDIA_ROOT, report.file.name)
    
    # Check if file exists
    if not os.path.exists(file_path):
        messages.error(request, "Report file not found")
        return redirect('report_generation', file_id=report.technician.data_file.id)
    
    # Set the appropriate content type
    if report.report_type == 'pdf':
        content_type = 'application/pdf'
    else:
        content_type = 'text/html'
    
    # Return the file as attachment
    return FileResponse(
        open(file_path, 'rb'),
        content_type=content_type,
        as_attachment=True,
        filename=os.path.basename(file_path)
    )


@require_POST
def delete_report(request, report_id):
    """Delete a generated report"""
    report = get_object_or_404(Report, id=report_id)
    file_id = report.technician.data_file.id
    
    # Delete the report
    report.delete()
    
    messages.success(request, "Report deleted successfully")
    return redirect('report_generation', file_id=file_id)


def get_reports_list(request, file_id):
    """Get list of reports for a data file as JSON"""
    data_file = get_object_or_404(DataFile, id=file_id)
    
    # Get all reports for this data file
    reports = Report.objects.filter(
        technician__data_file=data_file
    ).select_related('technician').order_by('-created_at')
    
    # Format for frontend
    formatted_reports = []
    for report in reports:
        formatted_reports.append({
            'id': report.id,
            'technician_id': report.technician.technician_id,
            'report_type': report.report_type,
            'created_at': report.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'file_name': os.path.basename(report.file.name),
            'file_url': report.file.url
        })
    
    return JsonResponse({
        'reports': formatted_reports
    })