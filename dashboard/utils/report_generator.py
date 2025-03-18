import os
import numpy as np
import pandas as pd
from django.conf import settings
from django.template.loader import render_to_string
from django.core.files.base import ContentFile
from dashboard.models import Report, TripRecord, Technician, DistanceData
from datetime import datetime
import uuid


def generate_technician_report(technician, report_format="pdf"):
    """
    Generate a comprehensive report for a technician
    
    Args:
        technician: Technician model instance
        report_format: Format of the report (pdf or html)
        
    Returns:
        Report: Report model instance
    """
    # Get all trip records for this technician
    trip_records = TripRecord.objects.filter(technician=technician, duplicate=False).order_by('created_at')
    
    if not trip_records.exists():
        return None, "No data available for this technician"
    
    # Analyze trip records
    context = analyze_technician_data(technician, trip_records)
    
    # Generate HTML content
    html_content = render_to_string('reports/technician_report.html', context)
    
    # Create report record
    report = Report(
        technician=technician,
        report_type=report_format
    )
    
    # Generate unique filename
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    unique_id = uuid.uuid4().hex[:8]
    
    if report_format == 'html':
        # Save HTML content
        report_filename = f"Technician_{technician.technician_id}_Report_{timestamp}_{unique_id}.html"
        report.file.save(report_filename, ContentFile(html_content))
        return report, f"HTML report generated successfully: {report.file.name}"
    
    else:  # PDF format
        # Try multiple PDF generation methods
        pdf_path = generate_pdf(html_content, technician.technician_id, timestamp, unique_id)
        
        if pdf_path:
            # Open the generated PDF file
            with open(pdf_path, 'rb') as pdf_file:
                report_filename = f"Technician_{technician.technician_id}_Report_{timestamp}_{unique_id}.pdf"
                report.file.save(report_filename, ContentFile(pdf_file.read()))
            
            # Remove temporary file
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
            
            return report, f"PDF report generated successfully: {report.file.name}"
        else:
            # Fallback to HTML if PDF generation fails
            report.report_type = 'html'
            report_filename = f"Technician_{technician.technician_id}_Report_{timestamp}_{unique_id}.html"
            report.file.save(report_filename, ContentFile(html_content))
            return report, f"PDF generation failed. HTML report is available: {report.file.name}"


def analyze_technician_data(technician, trip_records):
    """
    Analyze technician data for report generation
    
    Args:
        technician: Technician model instance
        trip_records: QuerySet of TripRecord instances
        
    Returns:
        dict: Context data for the report template
    """
    context = {
        'technician_id': technician.technician_id,
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'total_records': trip_records.count(),
    }
    
    # Get date range
    if trip_records.exists():
        min_date = trip_records.first().created_at
        max_date = trip_records.last().created_at
        context['date_range'] = {
            'start': min_date.strftime('%Y-%m-%d'),
            'end': max_date.strftime('%Y-%m-%d'),
        }
    
    # Trip type statistics
    trip_type_stats = get_trip_type_stats(trip_records)
    context['trip_type_stats'] = trip_type_stats
    
    # Punch-in/out analysis
    punch_analysis = analyze_punch_records(trip_records)
    context['punch_analysis'] = punch_analysis
    
    # Distance analysis
    try:
        distance_data = DistanceData.objects.get(technician=technician)
        context['distance_stats'] = {
            'total_distance': distance_data.total_distance,
            'trip_count': distance_data.trip_count,
            'avg_distance': round(distance_data.total_distance / distance_data.trip_count, 2) if distance_data.trip_count > 0 else 0
        }
    except DistanceData.DoesNotExist:
        context['distance_stats'] = None
    
    # Trip records formatted for display
    context['trip_records'] = [{
        'created_at': trip.created_at.strftime('%Y-%m-%d %H:%M:%S'),
        'trip_type': trip.trip_type,
        'location': trip.location or 'N/A',
        'coordinates': f"({trip.latitude:.6f}, {trip.longitude:.6f})" if trip.latitude and trip.longitude else 'N/A'
    } for trip in trip_records]
    
    return context


def get_trip_type_stats(trip_records):
    """
    Calculate trip type statistics
    
    Args:
        trip_records: QuerySet of TripRecord instances
        
    Returns:
        list: Trip type statistics
    """
    trip_types = {}
    total = trip_records.count()
    
    # Count trips by type
    for trip in trip_records:
        if trip.trip_type in trip_types:
            trip_types[trip.trip_type] += 1
        else:
            trip_types[trip.trip_type] = 1
    
    # Format for the template
    return [
        {
            'trip_type': trip_type,
            'count': count,
            'percentage': round((count / total) * 100, 2) if total > 0 else 0
        }
        for trip_type, count in trip_types.items()
    ]


def analyze_punch_records(trip_records):
    """
    Analyze punch-in and punch-out records
    
    Args:
        trip_records: QuerySet of TripRecord instances
        
    Returns:
        dict: Punch-in/out analysis data
    """
    punch_in_records = [trip for trip in trip_records if trip.trip_type == 'punch_in']
    punch_out_records = [trip for trip in trip_records if trip.trip_type == 'punch_out']
    
    if not punch_in_records and not punch_out_records:
        return None
    
    # Analyze punch-in/out pairs
    punch_pairs = []
    durations = []
    
    # Group by date
    date_groups = {}
    
    for record in punch_in_records:
        date = record.created_at.date()
        if date not in date_groups:
            date_groups[date] = {'punch_in': [], 'punch_out': []}
        date_groups[date]['punch_in'].append(record)
    
    for record in punch_out_records:
        date = record.created_at.date()
        if date not in date_groups:
            date_groups[date] = {'punch_in': [], 'punch_out': []}
        date_groups[date]['punch_out'].append(record)
    
    # Process each date
    for date, records in date_groups.items():
        # Sort by time
        records['punch_in'].sort(key=lambda x: x.created_at)
        records['punch_out'].sort(key=lambda x: x.created_at)
        
        # Match punch-ins with punch-outs
        for punch_in in records['punch_in']:
            # Find the next punch-out after this punch-in
            next_punch_out = None
            for punch_out in records['punch_out']:
                if punch_out.created_at > punch_in.created_at:
                    next_punch_out = punch_out
                    break
            
            if next_punch_out:
                # Calculate duration in hours
                duration = (next_punch_out.created_at - punch_in.created_at).total_seconds() / 3600
                
                punch_pairs.append({
                    'date': date.strftime('%Y-%m-%d'),
                    'punch_in': punch_in.created_at.strftime('%H:%M:%S'),
                    'punch_out': next_punch_out.created_at.strftime('%H:%M:%S'),
                    'duration_hours': round(duration, 2)
                })
                
                durations.append(duration)
                
                # Remove this punch-out from consideration
                records['punch_out'].remove(next_punch_out)
    
    # Compile statistics
    return {
        'pairs': punch_pairs,
        'stats': {
            'total_pairs': len(punch_pairs),
            'avg_duration': round(np.mean(durations), 2) if durations else 0,
            'max_duration': round(max(durations), 2) if durations else 0,
            'min_duration': round(min(durations), 2) if durations else 0,
            'total_hours': round(sum(durations), 2) if durations else 0
        }
    }


def generate_pdf(html_content, technician_id, timestamp, unique_id):
    """
    Generate PDF from HTML content using multiple methods
    
    Args:
        html_content: HTML content string
        technician_id: Technician ID
        timestamp: Timestamp string
        unique_id: Unique ID string
        
    Returns:
        str: Path to the generated PDF file, or None if generation failed
    """
    # Create reports directory if it doesn't exist
    reports_dir = os.path.join(settings.MEDIA_ROOT, 'reports')
    os.makedirs(reports_dir, exist_ok=True)
    
    # Path for the PDF file
    pdf_path = os.path.join(reports_dir, f"Technician_{technician_id}_Report_{timestamp}_{unique_id}.pdf")
    
    # Path for temporary HTML file
    html_path = os.path.join(reports_dir, f"temp_{technician_id}_Report_{timestamp}_{unique_id}.html")
    
    # Write HTML content to a temporary file
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    try:
        # Method 1: Try with pdfkit
        generate_pdf_with_pdfkit(html_path, pdf_path)
        if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
            return pdf_path
    except:
        pass
    
    try:
        # Method 2: Try with weasyprint
        generate_pdf_with_weasyprint(html_path, pdf_path)
        if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
            return pdf_path
    except:
        pass
    
    try:
        # Method 3: Try with reportlab
        generate_pdf_with_reportlab(html_path, pdf_path, technician_id)
        if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
            return pdf_path
    except:
        pass
    
    # Clean up temporary HTML file
    if os.path.exists(html_path):
        os.remove(html_path)
    
    return None


def generate_pdf_with_pdfkit(html_path, pdf_path):
    """Generate PDF using pdfkit"""
    import pdfkit
    
    options = {
        'page-size': 'A4',
        'margin-top': '1cm',
        'margin-right': '1cm',
        'margin-bottom': '1cm',
        'margin-left': '1cm',
        'encoding': 'UTF-8',
        'no-outline': None,
        'enable-local-file-access': None
    }
    
    # Try to find wkhtmltopdf in common locations
    wkhtmltopdf_path = os.environ.get('WKHTMLTOPDF_PATH')
    if wkhtmltopdf_path and os.path.exists(wkhtmltopdf_path):
        config = pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_path)
        pdfkit.from_file(html_path, pdf_path, options=options, configuration=config)
    else:
        pdfkit.from_file(html_path, pdf_path, options=options)


def generate_pdf_with_weasyprint(html_path, pdf_path):
    """Generate PDF using WeasyPrint"""
    from weasyprint import HTML
    HTML(filename=html_path).write_pdf(pdf_path)


def generate_pdf_with_reportlab(html_path, pdf_path, technician_id):
    """Generate PDF using ReportLab as a fallback"""
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    
    # Create PDF with basic info
    doc = SimpleDocTemplate(pdf_path, pagesize=letter)
    styles = getSampleStyleSheet()
    elements = []
    
    # Title
    title_style = ParagraphStyle(
        'Title',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.darkblue,
        alignment=1  # Center alignment
    )
    elements.append(Paragraph(f"TECHNICIAN {technician_id} REPORT", title_style))
    elements.append(Spacer(1, 0.25*inch))
    
    # Date
    elements.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
    elements.append(Spacer(1, 0.25*inch))
    
    # Note about HTML version
    elements.append(Spacer(1, 0.5*inch))
    note_style = ParagraphStyle(
        'Note',
        parent=styles['Normal'],
        textColor=colors.blue,
        fontSize=10
    )
    elements.append(Paragraph("Note: For a complete report, please view the HTML version:", note_style))
    elements.append(Paragraph(html_path, styles['Code']))
    
    # Build the PDF
    doc.build(elements)