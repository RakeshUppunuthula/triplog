import pandas as pd
import numpy as np
from django.utils import timezone
from dashboard.models import DataFile, Technician, TripRecord


def process_excel_file(data_file):
    """
    Process the uploaded Excel file and save records to the database
    
    Args:
        data_file: DataFile model instance
    
    Returns:
        dict: Summary of processing results
    """
    try:
        # Read Excel file
        df = pd.read_excel(data_file.file.path)
        
        # Clean the data
        df_cleaned = clean_data(df)
        
        # Create record in database
        data_file.record_count = len(df_cleaned)
        data_file.processed = True
        data_file.save()
        
        # Save technicians and trip records
        save_to_database(df_cleaned, data_file)
        
        # Identify duplicates
        duplicate_count = identify_duplicates(data_file)
        
        return {
            'success': True,
            'record_count': data_file.record_count,
            'technician_count': Technician.objects.filter(data_file=data_file).count(),
            'duplicate_count': duplicate_count
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


def clean_data(df):
    """
    Clean the data from Excel file
    
    Args:
        df: Pandas DataFrame
    
    Returns:
        df_cleaned: Cleaned DataFrame
    """
    # Make a copy to avoid modifying the original
    df_cleaned = df.copy()
    
    # Handle missing values
    for col in df_cleaned.columns:
        if df_cleaned[col].dtype == 'object':
            df_cleaned[col] = df_cleaned[col].fillna('')
        else:
            df_cleaned[col] = df_cleaned[col].fillna(0)
    
    # Format date columns
    date_cols = ['created_at', 'updated_at']
    for col in date_cols:
        if col in df_cleaned.columns:
            df_cleaned[col] = pd.to_datetime(df_cleaned[col], errors='coerce')
    
    # Format trip_type values to be consistent
    if 'trip_type' in df_cleaned.columns:
        df_cleaned['trip_type'] = df_cleaned['trip_type'].str.lower().str.strip()
    
    # Rename lat/long columns if needed
    if 'lat' in df_cleaned.columns and 'latitude' not in df_cleaned.columns:
        df_cleaned.rename(columns={'lat': 'latitude'}, inplace=True)
        
    if 'long' in df_cleaned.columns and 'longitude' not in df_cleaned.columns:
        df_cleaned.rename(columns={'long': 'longitude'}, inplace=True)
    
    # Ensure lat and long are numeric
    for col in ['latitude', 'longitude']:
        if col in df_cleaned.columns:
            df_cleaned[col] = pd.to_numeric(df_cleaned[col], errors='coerce')
    
    return df_cleaned


def save_to_database(df, data_file):
    """
    Save the cleaned data to database
    
    Args:
        df: Cleaned DataFrame
        data_file: DataFile model instance
    """
    # Dictionary to store technician objects
    technicians = {}
    
    # Batch create trip records for better performance
    trip_records = []
    
    # Process each row
    for _, row in df.iterrows():
        # Get or create technician
        tech_id = row['technician_id']
        if tech_id not in technicians:
            technician, _ = Technician.objects.get_or_create(
                technician_id=tech_id,
                data_file=data_file
            )
            technicians[tech_id] = technician
        else:
            technician = technicians[tech_id]
        
        # Create trip record dict
        trip_record = TripRecord(
            technician=technician,
            trip_type=row['trip_type'],
            created_at=row['created_at'],
            updated_at=row.get('updated_at', None)
        )
        
        # Add location data if available
        if 'location' in row and row['location']:
            trip_record.location = row['location']
        
        # Add coordinates if available
        if 'latitude' in row and not pd.isna(row['latitude']):
            trip_record.latitude = row['latitude']
            
        if 'longitude' in row and not pd.isna(row['longitude']):
            trip_record.longitude = row['longitude']
            
        trip_records.append(trip_record)
        
        # Batch create every 1000 records
        if len(trip_records) >= 1000:
            TripRecord.objects.bulk_create(trip_records)
            trip_records = []
    
    # Create any remaining records
    if trip_records:
        TripRecord.objects.bulk_create(trip_records)


def identify_duplicates(data_file):
    """
    Identify duplicate records in the database
    
    Args:
        data_file: DataFile model instance
    
    Returns:
        int: Count of duplicate records
    """
    duplicate_count = 0
    
    # Get all technicians for this file
    technicians = Technician.objects.filter(data_file=data_file)
    
    for technician in technicians:
        # Get all trip records for this technician
        trip_records = TripRecord.objects.filter(technician=technician)
        
        # Group by everything except id and created_at/updated_at
        trips_by_props = {}
        
        for trip in trip_records:
            # Create a key based on trip properties (excluding time-based fields)
            key = (
                trip.trip_type,
                trip.location,
                trip.latitude,
                trip.longitude
            )
            
            if key in trips_by_props:
                trips_by_props[key].append(trip)
            else:
                trips_by_props[key] = [trip]
        
        # Mark duplicates
        for key, trips in trips_by_props.items():
            if len(trips) > 1:
                # Sort by created_at to keep the first one
                trips.sort(key=lambda x: x.created_at)
                
                # Mark all but the first one as duplicates
                for trip in trips[1:]:
                    trip.duplicate = True
                    trip.save()
                    duplicate_count += 1
    
    return duplicate_count


def get_trip_type_distribution(data_file, technician=None):
    """
    Get trip type distribution
    
    Args:
        data_file: DataFile model instance
        technician: Optional Technician model instance
    
    Returns:
        list: Trip type distribution data
    """
    query = TripRecord.objects.filter(technician__data_file=data_file, duplicate=False)
    
    if technician:
        query = query.filter(technician=technician)
    
    # Count by trip type
    trip_counts = query.values('trip_type').annotate(count=models.Count('id'))
    
    # Format for frontend chart
    total = query.count()
    return [{
        'trip_type': item['trip_type'],
        'count': item['count'],
        'percentage': round((item['count'] / total) * 100, 2) if total > 0 else 0
    } for item in trip_counts]


def get_punch_in_distribution(data_file, technician=None):
    """
    Get punch-in distribution by hour
    
    Args:
        data_file: DataFile model instance
        technician: Optional Technician model instance
    
    Returns:
        list: Punch-in hour distribution data
    """
    # Filter punch-in records
    query = TripRecord.objects.filter(
        technician__data_file=data_file, 
        trip_type='punch_in',
        duplicate=False
    )
    
    if technician:
        query = query.filter(technician=technician)
    
    hour_counts = {}
    
    # Extract hour from created_at
    for record in query:
        hour = record.created_at.hour
        hour_counts[hour] = hour_counts.get(hour, 0) + 1
    
    # Format for frontend chart
    result = []
    for hour in range(24):
        result.append({
            'hour': hour,
            'count': hour_counts.get(hour, 0),
            'label': f"{hour}:00"
        })
    
    return result