from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse, FileResponse
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.conf import settings
import os
from dashboard.models import DataFile, Technician, Report
from dashboard.forms import ReportGenerationForm
from dashboard.utils.report_generator import generate_technician_report


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