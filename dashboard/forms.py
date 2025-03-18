from django import forms
from .models import DataFile, Technician, Report


class FileUploadForm(forms.ModelForm):
    """Form for uploading Excel files"""
    class Meta:
        model = DataFile
        fields = ['file']
        
    def clean_file(self):
        file = self.cleaned_data.get('file')
        if file:
            if not file.name.endswith('.xlsx'):
                raise forms.ValidationError("Only Excel files (.xlsx) are allowed.")
            
            # Store original filename
            self.instance.original_filename = file.name
            
        return file


class TechnicianFilterForm(forms.Form):
    """Form for filtering by technician"""
    technician = forms.ModelChoiceField(
        queryset=Technician.objects.all(), 
        required=False,
        empty_label="All Technicians"
    )
    
    def __init__(self, *args, data_file=None, **kwargs):
        super(TechnicianFilterForm, self).__init__(*args, **kwargs)
        
        # If a data file is provided, filter technicians by that file
        if data_file:
            self.fields['technician'].queryset = Technician.objects.filter(data_file=data_file)


class ReportGenerationForm(forms.ModelForm):
    """Form for generating reports"""
    REPORT_FORMAT_CHOICES = [
        ('pdf', 'PDF'),
        ('html', 'HTML'),
    ]
    
    report_format = forms.ChoiceField(
        choices=REPORT_FORMAT_CHOICES,
        initial='pdf',
        widget=forms.RadioSelect
    )
    
    class Meta:
        model = Report
        fields = ['technician', 'report_type']
        
    def __init__(self, *args, data_file=None, **kwargs):
        super(ReportGenerationForm, self).__init__(*args, **kwargs)
        
        # Rename field for clarity
        self.fields['report_type'] = self.fields.pop('report_format')
        
        # If a data file is provided, filter technicians by that file
        if data_file:
            self.fields['technician'].queryset = Technician.objects.filter(data_file=data_file)


class DateRangeFilterForm(forms.Form):
    """Form for filtering data by date range"""
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'})
    )