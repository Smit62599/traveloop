from django import forms
from decimal import Decimal

from .models import Trip, Stop, Activity, ChecklistItem, Note


class TripForm(forms.ModelForm):
    """
    Form for creating and editing a Trip.
    Matches the Create a new Trip wireframe (Screen 4).
    """

    class Meta:
        model = Trip
        fields = [
            'name', 'start_date', 'end_date', 'description', 'cover_photo',
            'manual_hotel_cost', 'manual_food_cost', 'manual_transport_cost',
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Europe Summer 2025',
            }),
            'start_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
            }),
            'end_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'What is this trip about?',
            }),
            'cover_photo': forms.FileInput(attrs={
                'class': 'form-control',
            }),
            'manual_hotel_cost': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': 'Optional manual override',
            }),
            'manual_food_cost': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': 'Optional manual override',
            }),
            'manual_transport_cost': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': 'Optional manual override',
            }),
        }
        labels = {
            'name':        'Trip Name',
            'start_date':  'Start Date',
            'end_date':    'End Date',
            'description': 'Description',
            'cover_photo': 'Cover Photo (optional)',
            'manual_hotel_cost': 'Manual hotel cost (optional)',
            'manual_food_cost': 'Manual food cost (optional)',
            'manual_transport_cost': 'Manual transport cost (optional)',
        }

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get('start_date')
        end   = cleaned_data.get('end_date')
        if start and end and end < start:
            raise forms.ValidationError('End date cannot be before start date.')
        for field in ('manual_hotel_cost', 'manual_food_cost', 'manual_transport_cost'):
            value = cleaned_data.get(field)
            if value is not None and value < 0:
                raise forms.ValidationError('Manual cost overrides cannot be negative.')
        return cleaned_data


class StopForm(forms.ModelForm):
    """Create/edit a Stop (city) within a Trip."""

    class Meta:
        model = Stop
        fields = ['city_name', 'country', 'start_date', 'end_date', 'order', 'notes']
        widgets = {
            'city_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Barcelona',
            }),
            'country': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Country (optional)',
            }),
            'start_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
            }),
            'end_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
            }),
            'order': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0,
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Notes for this stop (optional)',
            }),
        }
        labels = {
            'city_name':  'City',
            'country':    'Country',
            'start_date': 'Start date',
            'end_date':   'End date',
            'order':      'Order',
            'notes':      'Notes',
        }

    def __init__(self, *args, trip=None, **kwargs):
        self.trip = trip
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get('start_date')
        end = cleaned_data.get('end_date')
        if start and end and end < start:
            raise forms.ValidationError('End date cannot be before start date.')

        trip = self.trip
        if trip and start and end:
            if start < trip.start_date or end > trip.end_date:
                raise forms.ValidationError(
                    'Stop dates must fall within the trip '
                    f'({trip.start_date} – {trip.end_date}).'
                )
        return cleaned_data


class ActivityForm(forms.ModelForm):
    """Create/edit an Activity under a Stop."""

    class Meta:
        model = Activity
        fields = ['name', 'description', 'cost', 'duration', 'category']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Louvre visit',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Details (optional)',
            }),
            'cost': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
            }),
            'duration': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'placeholder': 'Minutes',
            }),
            'category': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'name':        'Activity name',
            'description': 'Description',
            'cost':        'Cost (USD)',
            'duration':    'Duration (minutes)',
            'category':    'Category',
        }

    def clean_cost(self):
        cost = self.cleaned_data.get('cost')
        if cost is not None and cost < Decimal('0'):
            raise forms.ValidationError('Cost cannot be negative.')
        return cost


class ChecklistItemForm(forms.ModelForm):
    """Add a checklist row linked to a trip."""

    class Meta:
        model = ChecklistItem
        fields = ['name', 'category']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Passport, chargers, sunscreen',
            }),
            'category': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'name':     'Item',
            'category': 'Category',
        }


class NoteForm(forms.ModelForm):
    """Create or edit a trip note."""

    class Meta:
        model = Note
        fields = ['title', 'content']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Optional title',
            }),
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Hotel details, reminders, journal…',
            }),
        }
        labels = {
            'title':   'Title',
            'content': 'Note',
        }
