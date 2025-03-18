from dashboard.models import DataFile

def recent_data_files(request):
    """
    Context processor to add recent data files to the session for
    display in the navigation dropdown
    """
    # Get last 10 data files
    data_files = DataFile.objects.all().order_by('-upload_date')[:10]
    
    # Store in session for easy access
    request.session['data_files'] = [
        {'id': file.id, 'original_filename': file.original_filename}
        for file in data_files
    ]
    
    return {
        'recent_data_files': data_files
    }