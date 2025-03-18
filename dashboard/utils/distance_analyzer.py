from haversine import haversine
from django.db.models import F
from dashboard.models import Technician, TripRecord, DistanceData


def calculate_technician_distances(data_file, technician=None):
    """
    Calculate distances for all technicians in the data file
    or for a specific technician if provided.
    
    Args:
        data_file: DataFile model instance
        technician: Optional Technician model instance
    
    Returns:
        dict: Distance calculation results
    """
    if technician:
        technicians = [technician]
    else:
        technicians = Technician.objects.filter(data_file=data_file)
    
    results = []
    for tech in technicians:
        distance_data = calculate_distance_for_technician(tech)
        results.append({
            'technician_id': tech.technician_id,
            'total_distance': distance_data.total_distance,
            'trip_count': distance_data.trip_count
        })
    
    return results


def calculate_distance_for_technician(technician):
    """
    Calculate the total distance traveled by a technician
    
    Args:
        technician: Technician model instance
    
    Returns:
        DistanceData: DistanceData model instance
    """
    # Get trip records with coordinates, sorted by time
    trips = TripRecord.objects.filter(
        technician=technician, 
        duplicate=False
    ).exclude(
        latitude__isnull=True,
        longitude__isnull=True
    ).order_by('created_at')
    
    # Delete any existing distance data
    DistanceData.objects.filter(technician=technician).delete()
    
    # Create new distance data
    distance_data = DistanceData.objects.create(
        technician=technician,
        total_distance=0,
        trip_count=trips.count()
    )
    
    total_distance = 0
    locations = []
    
    # Calculate distance between consecutive points
    prev_point = None
    for trip in trips:
        curr_point = (trip.latitude, trip.longitude)
        
        # Store location information
        locations.append({
            'name': trip.location if trip.location else f"Point {len(locations) + 1}",
            'lat': trip.latitude,
            'long': trip.longitude,
            'time': trip.created_at,
            'trip_type': trip.trip_type
        })
        
        if prev_point:
            # Calculate distance in kilometers using haversine formula
            distance = haversine(prev_point, curr_point)
            total_distance += distance
        
        prev_point = curr_point
    
    # Update distance data
    distance_data.total_distance = round(total_distance, 2)
    distance_data.save()
    
    return distance_data


def get_trip_locations(technician):
    """
    Get location data for a technician's trips
    
    Args:
        technician: Technician model instance
    
    Returns:
        list: Location data for map visualization
    """
    # Get trip records with coordinates, sorted by time
    trips = TripRecord.objects.filter(
        technician=technician, 
        duplicate=False
    ).exclude(
        latitude__isnull=True,
        longitude__isnull=True
    ).order_by('created_at')
    
    locations = []
    for trip in trips:
        locations.append({
            'name': trip.location if trip.location else f"Point {len(locations) + 1}",
            'lat': trip.latitude,
            'long': trip.longitude,
            'time': trip.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'trip_type': trip.trip_type
        })
    
    return locations


def get_distance_summary(data_file, technician=None):
    """
    Get distance summary for one technician or all technicians
    
    Args:
        data_file: DataFile model instance
        technician: Optional Technician model instance
    
    Returns:
        dict: Distance summary data
    """
    if technician:
        # Get distance data for the specified technician
        try:
            distance_data = DistanceData.objects.get(technician=technician)
            return {
                'technician_id': technician.technician_id,
                'total_distance': distance_data.total_distance,
                'trip_count': distance_data.trip_count,
                'avg_distance': round(distance_data.total_distance / distance_data.trip_count, 2) if distance_data.trip_count > 0 else 0
            }
        except DistanceData.DoesNotExist:
            return {
                'technician_id': technician.technician_id,
                'total_distance': 0,
                'trip_count': 0,
                'avg_distance': 0
            }
    else:
        # Get distance data for all technicians
        distance_data = DistanceData.objects.filter(
            technician__data_file=data_file
        ).select_related('technician')
        
        if not distance_data.exists():
            return {
                'total_technicians': 0,
                'avg_distance': 0,
                'max_distance': 0,
                'min_distance': 0,
                'technicians': []
            }
        
        # Calculate summary stats
        all_distances = [d.total_distance for d in distance_data]
        
        return {
            'total_technicians': len(distance_data),
            'avg_distance': round(sum(all_distances) / len(all_distances), 2),
            'max_distance': round(max(all_distances), 2),
            'min_distance': round(min(all_distances), 2),
            'technicians': [{
                'technician_id': d.technician.technician_id, 
                'total_distance': d.total_distance,
                'trip_count': d.trip_count
            } for d in distance_data]
        }