from django.urls import path
from dashboard import views

urlpatterns = [
    # Data views
    path('', views.index, name='index'),
    path('upload/', views.upload_file, name='upload_file'),
    path('data/<int:file_id>/', views.data_overview, name='data_overview'),
    path('data/<int:file_id>/delete/', views.delete_file, name='delete_file'),
    path('data/switch/', views.switch_file, name='switch_file'),
    
    # Duplicate analysis views
    path('data/<int:file_id>/duplicates/', views.duplicate_analysis, name='duplicate_analysis'),
    path('data/<int:file_id>/duplicates/summary/', views.get_duplicate_summary, name='get_duplicate_summary'),
    path('data/<int:file_id>/duplicates/records/', views.get_duplicate_records, name='get_duplicate_records'),
    
    # Trip analysis views
    path('data/<int:file_id>/trips/', views.trip_analysis, name='trip_analysis'),
    path('data/<int:file_id>/trips/chart/', views.get_trip_type_chart_data, name='get_trip_type_chart_data'),
    path('data/<int:file_id>/trips/punch-in-chart/', views.get_punch_in_chart_data, name='get_punch_in_chart_data'),
    path('data/<int:file_id>/trips/summary/', views.get_trip_type_summary, name='get_trip_type_summary'),
    
    # Technician logs views
    path('data/<int:file_id>/technicians/', views.technician_logs, name='technician_logs'),
    path('data/<int:file_id>/technicians/<int:technician_id>/summary/', views.get_technician_summary, name='get_technician_summary'),
    path('data/<int:file_id>/technicians/<int:technician_id>/punch-data/', views.get_punch_in_out_data, name='get_punch_in_out_data'),
    path('data/<int:file_id>/technicians/<int:technician_id>/timeline/', views.get_timeline_data, name='get_timeline_data'),
    
    # Distance analysis views
    path('data/<int:file_id>/distance/', views.distance_analysis, name='distance_analysis'),
    path('data/<int:file_id>/distance/calculate/', views.calculate_distances, name='calculate_distances'),
    path('data/<int:file_id>/distance/data/', views.get_distance_data, name='get_distance_data'),
    path('data/<int:file_id>/distance/chart/', views.get_distance_chart_data, name='get_distance_chart_data'),
    path('data/<int:file_id>/distance/map/<int:technician_id>/', views.get_location_map_data, name='get_location_map_data'),
    
    # Report generation views
    path('data/<int:file_id>/reports/', views.report_generation, name='report_generation'),
    path('data/<int:file_id>/reports/generate/', views.generate_report, name='generate_report'),
    path('data/<int:file_id>/reports/list/', views.get_reports_list, name='get_reports_list'),
    path('reports/<int:report_id>/view/', views.view_report, name='view_report'),
    path('reports/<int:report_id>/download/', views.download_report, name='download_report'),
    path('reports/<int:report_id>/delete/', views.delete_report, name='delete_report'),
]