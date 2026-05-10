from decimal import Decimal
import json
from datetime import timedelta

from django.contrib.auth.models import User
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Max, Prefetch, Sum, Value, DecimalField, Count
from django.db.models.functions import Coalesce

from .models import Trip, Stop, Activity, ChecklistItem, Note, Invoice, InvoiceItem
from .forms import TripForm, StopForm, ActivityForm, ChecklistItemForm, NoteForm
from .utils import calculate_trip_budget


# ── Helper ─────────────────────────────────────────────────────────────────────

def _auto_update_status(trip):
    """Set trip status based on today's date."""
    today = timezone.now().date()
    if trip.end_date < today:
        trip.status = 'completed'
    elif trip.start_date <= today <= trip.end_date:
        trip.status = 'ongoing'
    else:
        trip.status = 'upcoming'
    trip.save(update_fields=['status'])


def _next_stop_order(trip):
    """Next `order` value when appending a stop (after existing max)."""
    m = trip.stops.aggregate(m=Max('order'))['m']
    return (m + 1) if m is not None else 0


def _renumber_stops(trip):
    """Keep stop `order` dense (0..n-1) after delete or for consistency."""
    for index, stop in enumerate(trip.stops.order_by('order', 'start_date')):
        if stop.order != index:
            Stop.objects.filter(pk=stop.pk).update(order=index)


def _invoice_category_from_activity(activity_category):
    mapping = {
        'food': 'food',
        'transport': 'travel',
        'accommodation': 'hotel',
        'shopping': 'shopping',
    }
    return mapping.get(activity_category, 'activity')


def _ensure_trip_invoice(trip):
    """
    Create/update one working invoice for a trip.
    Invoice items are auto-generated from trip activities.
    """
    invoice = trip.invoices.order_by('-generated_date').first()
    if not invoice:
        invoice = Invoice.objects.create(
            trip=trip,
            invoice_id=f"INV-{trip.pk:04d}-{timezone.now().strftime('%Y%m%d%H%M%S')}",
        )

    # Rebuild item lines from latest activities unless invoice is paid.
    if invoice.status != 'paid':
        invoice.items.all().delete()
        activities = (
            Activity.objects
            .filter(stop__trip=trip)
            .select_related('stop')
            .order_by('stop__order', 'name', 'created_at')
        )
        for activity in activities:
            InvoiceItem.objects.create(
                invoice=invoice,
                category=_invoice_category_from_activity(activity.category),
                description=f"{activity.name} ({activity.stop.city_name})",
                quantity=1,
                unit_cost=activity.cost,
            )
    return invoice


def _normalized_budget_buckets():
    return {
        'transport': Decimal('0.00'),
        'stay': Decimal('0.00'),
        'food': Decimal('0.00'),
        'activities': Decimal('0.00'),
        'others': Decimal('0.00'),
    }


def _budget_bucket_for_activity(category):
    if category == 'transport':
        return 'transport'
    if category == 'accommodation':
        return 'stay'
    if category == 'food':
        return 'food'
    if category in {'sightseeing', 'adventure', 'culture'}:
        return 'activities'
    return 'others'


@login_required
def admin_dashboard(request):
    """
    Custom analytics dashboard for staff/superuser users.
    Uses only real DB aggregates.
    """
    if not request.user.is_staff:
        return redirect('users:login')

    base_users = User.objects.filter(is_staff=False)
    trips_scope = Trip.objects.filter(user__is_staff=False)
    stops_scope = Stop.objects.filter(trip__user__is_staff=False)
    activity_scope = Activity.objects.filter(stop__trip__user__is_staff=False)

    total_users = base_users.count()
    total_trips = trips_scope.count()
    avg_trips_per_user = Decimal('0.00')
    if total_users > 0:
        avg_trips_per_user = (Decimal(total_trips) / Decimal(total_users)).quantize(Decimal('0.01'))

    top_cities_qs = (
        stops_scope.values('city_name')
        .annotate(count=Count('id'))
        .order_by('-count', 'city_name')[:5]
    )
    top_activity_categories_qs = (
        activity_scope.values('category')
        .annotate(count=Count('id'))
        .order_by('-count', 'category')[:5]
    )

    trend_days = request.GET.get('days', '30')
    if trend_days not in {'7', '14', '30'}:
        trend_days = '30'
    days_window = int(trend_days)

    # Last N days (inclusive) trend by Trip.created_at date.
    start_date = timezone.now().date() - timedelta(days=days_window - 1)
    trips_by_day_qs = (
        trips_scope.filter(created_at__date__gte=start_date)
        .values('created_at__date')
        .annotate(count=Count('id'))
        .order_by('created_at__date')
    )
    by_day_map = {row['created_at__date']: row['count'] for row in trips_by_day_qs}
    trend_dates = [start_date + timedelta(days=i) for i in range(days_window)]
    trend_labels = [d.strftime('%b %d') for d in trend_dates]
    trend_values = [by_day_map.get(d, 0) for d in trend_dates]

    total_revenue = activity_scope.aggregate(total=Sum('cost'))['total'] or Decimal('0.00')
    avg_cost_per_trip = Decimal('0.00')
    if total_trips > 0:
        avg_cost_per_trip = (total_revenue / Decimal(total_trips)).quantize(Decimal('0.01'))

    context = {
        'total_users': total_users,
        'total_trips': total_trips,
        'avg_trips_per_user': avg_trips_per_user,
        'top_cities': top_cities_qs,
        'top_activity_categories': top_activity_categories_qs,
        'avg_cost_per_trip': avg_cost_per_trip,
        'total_revenue': total_revenue,
        'trend_days': trend_days,
        # Chart payloads
        'city_labels': json.dumps([row['city_name'] for row in top_cities_qs]),
        'city_values': json.dumps([row['count'] for row in top_cities_qs]),
        'activity_labels': json.dumps([row['category'].title() for row in top_activity_categories_qs]),
        'activity_values': json.dumps([row['count'] for row in top_activity_categories_qs]),
        'trend_labels': json.dumps(trend_labels),
        'trend_values': json.dumps(trend_values),
    }
    return render(request, 'admin/dashboard.html', context)


# ── Dashboard ──────────────────────────────────────────────────────────────────

@login_required
def dashboard(request):
    """
    Main landing page after login.
    Shows upcoming/ongoing trips, quick stats, and top regional picks.
    Matches wireframe Screen 3.
    """
    trips = request.user.trips.all()

    # Auto-update statuses
    for t in trips:
        _auto_update_status(t)

    upcoming  = trips.filter(status='upcoming').order_by('start_date')[:3]
    ongoing   = trips.filter(status='ongoing').order_by('start_date')[:3]
    completed = trips.filter(status='completed').order_by('-end_date')[:3]
    recent    = trips.order_by('-created_at')[:4]

    # Stats
    total_trips      = trips.count()
    total_cities     = Stop.objects.filter(trip__user=request.user).count()
    total_activities = Activity.objects.filter(stop__trip__user=request.user).count()
    total_budget     = sum(t.total_budget for t in trips)

    # Static "Top Regional Selections" mock data (no external API)
    regional_picks = [
        {'city': 'Paris',     'country': 'France',  'emoji': '🗼'},
        {'city': 'Tokyo',     'country': 'Japan',   'emoji': '⛩️'},
        {'city': 'New York',  'country': 'USA',     'emoji': '🗽'},
        {'city': 'Bali',      'country': 'Indonesia','emoji': '🌴'},
        {'city': 'Rome',      'country': 'Italy',   'emoji': '🏛️'},
    ]

    context = {
        'upcoming':       upcoming,
        'ongoing':        ongoing,
        'completed':      completed,
        'recent':         recent,
        'total_trips':    total_trips,
        'total_cities':   total_cities,
        'total_activities': total_activities,
        'total_budget':   total_budget,
        'regional_picks': regional_picks,
    }
    return render(request, 'trips/dashboard.html', context)


# ── Trip List ──────────────────────────────────────────────────────────────────

@login_required
def trip_list(request):
    """
    Shows all of the user's trips grouped by status.
    Supports search by name.
    Matches wireframe Screen 6.
    """
    trips = request.user.trips.all()

    # Auto-update statuses
    for t in trips:
        _auto_update_status(t)

    query = request.GET.get('q', '').strip()
    if query:
        trips = trips.filter(
            Q(name__icontains=query) | Q(description__icontains=query)
        )

    sort = request.GET.get('sort', '-start_date')
    allowed_sorts = ['start_date', '-start_date', 'name', '-name', 'created_at', '-created_at']
    if sort not in allowed_sorts:
        sort = '-start_date'
    trips = trips.order_by(sort)

    ongoing   = [t for t in trips if t.status == 'ongoing']
    upcoming  = [t for t in trips if t.status == 'upcoming']
    completed = [t for t in trips if t.status == 'completed']

    context = {
        'ongoing':   ongoing,
        'upcoming':  upcoming,
        'completed': completed,
        'query':     query,
        'sort':      sort,
    }
    return render(request, 'trips/trip_list.html', context)


# ── Activity Search ────────────────────────────────────────────────────────────

@login_required
def activity_search(request):
    """
    Dedicated activity discovery/search screen with filters.
    Can optionally add a searched activity to a selected stop.
    """
    activities = Activity.objects.select_related('stop', 'stop__trip').filter(stop__trip__user=request.user)
    user_stops = Stop.objects.filter(trip__user=request.user).select_related('trip').order_by('trip__name', 'order', 'start_date')

    q = request.GET.get('q', '').strip()
    category = request.GET.get('category', '').strip()
    city = request.GET.get('city', '').strip()
    max_cost = request.GET.get('max_cost', '').strip()
    max_duration = request.GET.get('max_duration', '').strip()
    stop_id = request.GET.get('stop', '').strip()

    if q:
        activities = activities.filter(Q(name__icontains=q) | Q(description__icontains=q))
    if category:
        activities = activities.filter(category=category)
    if city:
        activities = activities.filter(stop__city_name__icontains=city)
    if max_cost:
        try:
            activities = activities.filter(cost__lte=Decimal(max_cost))
        except Exception:
            messages.warning(request, 'Max cost filter was invalid and has been ignored.')
    if max_duration:
        try:
            activities = activities.filter(duration__lte=int(max_duration))
        except Exception:
            messages.warning(request, 'Max duration filter was invalid and has been ignored.')

    activities = activities.order_by('-created_at')

    target_stop = None
    if stop_id:
        target_stop = get_object_or_404(Stop, pk=stop_id, trip__user=request.user)

    if request.method == 'POST':
        source_id = request.POST.get('source_activity_id')
        target_stop_id = request.POST.get('target_stop_id')
        if source_id and target_stop_id:
            source = get_object_or_404(Activity, pk=source_id, stop__trip__user=request.user)
            target = get_object_or_404(Stop, pk=target_stop_id, trip__user=request.user)
            Activity.objects.create(
                stop=target,
                name=source.name,
                description=source.description,
                cost=source.cost,
                duration=source.duration,
                category=source.category,
            )
            messages.success(request, f'Added "{source.name}" to {target.city_name}.')
            return redirect(f"{reverse('trips:activity_search')}?stop={target.pk}")
        messages.error(request, 'Could not add the selected activity to stop.')

    return render(request, 'trips/activity_search.html', {
        'activities': activities,
        'user_stops': user_stops,
        'target_stop': target_stop,
        'q': q,
        'category': category,
        'city': city,
        'max_cost': max_cost,
        'max_duration': max_duration,
        'category_choices': Activity.CATEGORY_CHOICES,
    })


# ── Trip Create ────────────────────────────────────────────────────────────────

@login_required
def trip_create(request):
    """
    Create a new Trip.
    Matches wireframe Screen 4.
    """
    form = TripForm(request.POST or None, request.FILES or None)

    if request.method == 'POST':
        if form.is_valid():
            trip = form.save(commit=False)
            trip.user = request.user
            trip.save()
            _auto_update_status(trip)
            messages.success(request, f'Trip "{trip.name}" created! Now add your stops. 🗺️')
            return redirect('trips:trip_detail', pk=trip.pk)
        else:
            messages.error(request, 'Please fix the errors below.')

    return render(request, 'trips/trip_form.html', {
        'form':       form,
        'form_title': 'Plan a New Trip',
        'btn_label':  'Create Trip',
    })


# ── Trip Detail ────────────────────────────────────────────────────────────────

@login_required
def trip_detail(request, pk):
    """
    Overview hub for a single trip: stops list, budget summary, quick links
    to checklist and notes.
    """
    trip = get_object_or_404(Trip, pk=pk, user=request.user)
    _auto_update_status(trip)

    budget_data = calculate_trip_budget(trip)
    trip_budget_total = budget_data['total']

    stops = (
        trip.stops
        .annotate(
            budget_subtotal=Coalesce(
                Sum('activities__cost'),
                Value(0),
                output_field=DecimalField(max_digits=10, decimal_places=2),
            ),
        )
        .prefetch_related(
            Prefetch(
                'activities',
                queryset=Activity.objects.order_by('category', 'name', 'created_at'),
            ),
        )
        .order_by('order', 'start_date')
    )

    category_totals = [
        {'category': 'hotel', 'total': budget_data['hotel']},
        {'category': 'food', 'total': budget_data['food']},
        {'category': 'transport', 'total': budget_data['transport']},
        {'category': 'activities', 'total': budget_data['activities']},
    ]

    avg_cost_per_day = budget_data['avg_per_day']
    over_budget_days = [
        {'date': row['start_date'], 'total': row['day_cost']}
        for row in budget_data['over_budget_stops']
    ]
    high_cost_stop_ids = [row['stop_id'] for row in budget_data['over_budget_stops']]

    notes = trip.notes.all()
    invoice = trip.invoices.order_by('-generated_date').first()

    context = {
        'trip':               trip,
        'stops':              stops,
        'budget_data':        budget_data,
        'trip_budget_total':  trip_budget_total,
        'category_totals':    category_totals,
        'high_cost_stop_ids': high_cost_stop_ids,
        'avg_cost_per_day':   avg_cost_per_day,
        'over_budget_days':   over_budget_days,
        'chart_labels':       json.dumps(['Hotel', 'Food', 'Transport', 'Activities']),
        'chart_values':       json.dumps([
            float(budget_data['hotel']),
            float(budget_data['food']),
            float(budget_data['transport']),
            float(budget_data['activities']),
        ]),
        'notes':              notes,
        'invoice':            invoice,
    }
    return render(request, 'trips/trip_detail.html', context)


# ── Trip Edit ──────────────────────────────────────────────────────────────────

@login_required
def trip_edit(request, pk):
    """Edit an existing trip's core details."""
    trip = get_object_or_404(Trip, pk=pk, user=request.user)
    form = TripForm(
        request.POST  or None,
        request.FILES or None,
        instance=trip
    )

    if request.method == 'POST':
        if form.is_valid():
            form.save()
            _auto_update_status(trip)
            messages.success(request, f'Trip "{trip.name}" updated!')
            return redirect('trips:trip_detail', pk=trip.pk)
        else:
            messages.error(request, 'Please fix the errors below.')

    return render(request, 'trips/trip_form.html', {
        'form':       form,
        'trip':       trip,
        'form_title': f'Edit — {trip.name}',
        'btn_label':  'Save Changes',
    })


# ── Trip Delete ────────────────────────────────────────────────────────────────

@login_required
def trip_delete(request, pk):
    """Confirm and delete a trip (cascades to stops, activities, etc.)."""
    trip = get_object_or_404(Trip, pk=pk, user=request.user)

    if request.method == 'POST':
        name = trip.name
        trip.delete()
        messages.success(request, f'Trip "{name}" deleted.')
        return redirect('trips:trip_list')

    return render(request, 'trips/trip_confirm_delete.html', {'trip': trip})


# ── Stop CRUD ──────────────────────────────────────────────────────────────────

@login_required
def stop_create(request, trip_pk):
    """Add a city/stop to a trip (owner only)."""
    trip = get_object_or_404(Trip, pk=trip_pk, user=request.user)
    form = StopForm(
        request.POST or None,
        trip=trip,
        initial={'order': _next_stop_order(trip)},
    )

    if request.method == 'POST':
        if form.is_valid():
            stop = form.save(commit=False)
            stop.trip = trip
            stop.save()
            messages.success(
                request,
                f'Stop "{stop.city_name}" added to your trip.',
            )
            return redirect('trips:trip_detail', pk=trip.pk)
        messages.error(request, 'Please fix the errors below.')

    return render(request, 'trips/stop_form.html', {
        'form':       form,
        'trip':       trip,
        'form_title': f'Add Stop — {trip.name}',
        'btn_label':  'Add Stop',
    })


@login_required
def stop_edit(request, trip_pk, stop_pk):
    """Edit a stop (owner only)."""
    trip = get_object_or_404(Trip, pk=trip_pk, user=request.user)
    stop = get_object_or_404(Stop, pk=stop_pk, trip=trip)
    form = StopForm(
        request.POST or None,
        instance=stop,
        trip=trip,
    )

    if request.method == 'POST':
        if form.is_valid():
            form.save()
            messages.success(request, f'Stop "{stop.city_name}" updated.')
            return redirect('trips:trip_detail', pk=trip.pk)
        messages.error(request, 'Please fix the errors below.')

    return render(request, 'trips/stop_form.html', {
        'form':       form,
        'trip':       trip,
        'stop':       stop,
        'form_title': f'Edit Stop — {stop.city_name}',
        'btn_label':  'Save Changes',
    })


@login_required
def stop_delete(request, trip_pk, stop_pk):
    """Delete a stop (owner only); renumbers remaining stops."""
    trip = get_object_or_404(Trip, pk=trip_pk, user=request.user)
    stop = get_object_or_404(Stop, pk=stop_pk, trip=trip)

    if request.method == 'POST':
        label = stop.city_name
        stop.delete()
        _renumber_stops(trip)
        messages.success(request, f'Stop "{label}" removed.')
        return redirect('trips:trip_detail', pk=trip.pk)

    return render(request, 'trips/stop_confirm_delete.html', {
        'trip': trip,
        'stop': stop,
    })


# ── Activity CRUD ──────────────────────────────────────────────────────────────

@login_required
def activity_create(request, trip_pk, stop_pk):
    """Add an activity to a stop (trip owner only)."""
    trip = get_object_or_404(Trip, pk=trip_pk, user=request.user)
    stop = get_object_or_404(Stop, pk=stop_pk, trip=trip)
    form = ActivityForm(request.POST or None)

    if request.method == 'POST':
        if form.is_valid():
            activity = form.save(commit=False)
            activity.stop = stop
            activity.save()
            messages.success(
                request,
                f'Activity "{activity.name}" added to {stop.city_name}.',
            )
            return redirect('trips:trip_detail', pk=trip.pk)
        messages.error(request, 'Please fix the errors below.')

    return render(request, 'trips/activity_form.html', {
        'form':       form,
        'trip':       trip,
        'stop':       stop,
        'form_title': f'Add Activity — {stop.city_name}',
        'btn_label':  'Add Activity',
    })


@login_required
def activity_edit(request, trip_pk, stop_pk, activity_pk):
    """Edit an activity (trip owner only)."""
    trip = get_object_or_404(Trip, pk=trip_pk, user=request.user)
    stop = get_object_or_404(Stop, pk=stop_pk, trip=trip)
    activity = get_object_or_404(Activity, pk=activity_pk, stop=stop)
    form = ActivityForm(request.POST or None, instance=activity)

    if request.method == 'POST':
        if form.is_valid():
            form.save()
            messages.success(request, f'Activity "{activity.name}" updated.')
            return redirect('trips:trip_detail', pk=trip.pk)
        messages.error(request, 'Please fix the errors below.')

    return render(request, 'trips/activity_form.html', {
        'form':       form,
        'trip':       trip,
        'stop':       stop,
        'activity':   activity,
        'form_title': f'Edit Activity — {activity.name}',
        'btn_label':  'Save Changes',
    })


@login_required
def activity_delete(request, trip_pk, stop_pk, activity_pk):
    """Delete an activity (trip owner only)."""
    trip = get_object_or_404(Trip, pk=trip_pk, user=request.user)
    stop = get_object_or_404(Stop, pk=stop_pk, trip=trip)
    activity = get_object_or_404(Activity, pk=activity_pk, stop=stop)

    if request.method == 'POST':
        label = activity.name
        activity.delete()
        messages.success(request, f'Activity "{label}" removed.')
        return redirect('trips:trip_detail', pk=trip.pk)

    return render(request, 'trips/activity_confirm_delete.html', {
        'trip':     trip,
        'stop':     stop,
        'activity': activity,
    })


# ── Trip checklist ─────────────────────────────────────────────────────────────

@login_required
def trip_checklist(request, trip_pk):
    """Packing / task checklist for a trip (owner only)."""
    trip = get_object_or_404(Trip, pk=trip_pk, user=request.user)
    items = trip.checklist_items.all()

    if request.method == 'POST':
        form = ChecklistItemForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.trip = trip
            item.save()
            messages.success(request, f'Added checklist item “{item.name}”.')
            return redirect('trips:checklist', trip_pk=trip.pk)
        messages.error(request, 'Please fix the errors below.')
    else:
        form = ChecklistItemForm()

    done = items.filter(is_completed=True).count()
    total = items.count()

    return render(request, 'trips/trip_checklist.html', {
        'trip':   trip,
        'items':  items,
        'form':   form,
        'done':   done,
        'total':  total,
    })


@login_required
@require_POST
def checklist_item_toggle(request, trip_pk, item_pk):
    """Flip completed flag (owner only)."""
    trip = get_object_or_404(Trip, pk=trip_pk, user=request.user)
    item = get_object_or_404(ChecklistItem, pk=item_pk, trip=trip)
    item.is_completed = not item.is_completed
    item.save(update_fields=['is_completed'])
    return redirect('trips:checklist', trip_pk=trip.pk)


@login_required
def checklist_item_delete(request, trip_pk, item_pk):
    """Remove a checklist item (owner only)."""
    trip = get_object_or_404(Trip, pk=trip_pk, user=request.user)
    item = get_object_or_404(ChecklistItem, pk=item_pk, trip=trip)

    if request.method == 'POST':
        label = item.name
        item.delete()
        messages.success(request, f'Removed “{label}” from the checklist.')
        return redirect('trips:checklist', trip_pk=trip.pk)

    return render(request, 'trips/checklist_item_confirm_delete.html', {
        'trip': trip,
        'item': item,
    })


# ── Trip notes ───────────────────────────────────────────────────────────────

@login_required
def note_create(request, trip_pk):
    """Add a note to a trip (owner only)."""
    trip = get_object_or_404(Trip, pk=trip_pk, user=request.user)
    form = NoteForm(request.POST or None)

    if request.method == 'POST':
        if form.is_valid():
            note = form.save(commit=False)
            note.trip = trip
            note.save()
            messages.success(request, 'Note added.')
            return redirect(reverse('trips:trip_detail', args=[trip.pk]) + '#trip-notes')
        messages.error(request, 'Please fix the errors below.')

    return render(request, 'trips/note_form.html', {
        'form':       form,
        'trip':       trip,
        'form_title': f'Add note — {trip.name}',
        'btn_label':  'Save note',
    })


@login_required
def note_edit(request, trip_pk, note_pk):
    """Edit a note (owner only)."""
    trip = get_object_or_404(Trip, pk=trip_pk, user=request.user)
    note = get_object_or_404(Note, pk=note_pk, trip=trip)
    form = NoteForm(request.POST or None, instance=note)

    if request.method == 'POST':
        if form.is_valid():
            form.save()
            messages.success(request, 'Note updated.')
            return redirect(reverse('trips:trip_detail', args=[trip.pk]) + '#trip-notes')
        messages.error(request, 'Please fix the errors below.')

    return render(request, 'trips/note_form.html', {
        'form':       form,
        'trip':       trip,
        'note':       note,
        'form_title': 'Edit note',
        'btn_label':  'Save changes',
    })


@login_required
def note_delete(request, trip_pk, note_pk):
    """Delete a note (owner only)."""
    trip = get_object_or_404(Trip, pk=trip_pk, user=request.user)
    note = get_object_or_404(Note, pk=note_pk, trip=trip)

    if request.method == 'POST':
        note.delete()
        messages.success(request, 'Note deleted.')
        return redirect(reverse('trips:trip_detail', args=[trip.pk]) + '#trip-notes')

    return render(request, 'trips/note_confirm_delete.html', {
        'trip': trip,
        'note': note,
    })


# ── Trip invoice / billing ────────────────────────────────────────────────────

@login_required
def invoice_detail(request, trip_pk):
    trip = get_object_or_404(Trip, pk=trip_pk, user=request.user)
    invoice = _ensure_trip_invoice(trip)

    context = {
        'trip': trip,
        'invoice': invoice,
        'items': invoice.items.all(),
        'traveler_name': request.user.get_full_name() or request.user.username,
    }
    return render(request, 'trips/invoice.html', context)


@login_required
@require_POST
def mark_invoice_paid(request, invoice_id):
    invoice = get_object_or_404(Invoice, invoice_id=invoice_id, trip__user=request.user)
    invoice.status = 'paid'
    invoice.save(update_fields=['status'])
    messages.success(request, f'Invoice {invoice.invoice_id} marked as paid.')
    return redirect('trips:invoice_detail', trip_pk=invoice.trip.pk)


# ── Public trip sharing ───────────────────────────────────────────────────────

@login_required
@require_POST
def toggle_trip_public(request, pk):
    trip = get_object_or_404(Trip, pk=pk, user=request.user)
    trip.is_public = not trip.is_public
    trip.save(update_fields=['is_public'])
    state = 'public' if trip.is_public else 'private'
    messages.success(request, f'"{trip.name}" is now {state}.')
    return redirect('trips:trip_detail', pk=trip.pk)


def public_trip_view(request, token):
    trip = get_object_or_404(
        Trip.objects.filter(is_public=True).prefetch_related(
            Prefetch(
                'stops',
                queryset=Stop.objects.prefetch_related(
                    Prefetch(
                        'activities',
                        queryset=Activity.objects.order_by('category', 'name', 'created_at'),
                    )
                ).order_by('order', 'start_date'),
            ),
        ),
        share_token=token,
    )
    stops = trip.stops.all()
    total_cost = Activity.objects.filter(stop__trip=trip).aggregate(total=Sum('cost'))['total'] or Decimal('0.00')
    public_url = request.build_absolute_uri()
    return render(request, 'trips/public_trip.html', {
        'trip': trip,
        'stops': stops,
        'total_cost': total_cost,
        'public_url': public_url,
    })


@login_required
@require_POST
def copy_trip(request, id):
    source = get_object_or_404(Trip, pk=id)
    copied = Trip.objects.create(
        user=request.user,
        name=f"{source.name} (Copy)",
        start_date=source.start_date,
        end_date=source.end_date,
        description=source.description,
        status='upcoming',
    )

    for stop in source.stops.order_by('order', 'start_date'):
        new_stop = Stop.objects.create(
            trip=copied,
            city_name=stop.city_name,
            country=stop.country,
            start_date=stop.start_date,
            end_date=stop.end_date,
            order=stop.order,
            notes=stop.notes,
        )
        for activity in stop.activities.all():
            Activity.objects.create(
                stop=new_stop,
                name=activity.name,
                description=activity.description,
                cost=activity.cost,
                duration=activity.duration,
                category=activity.category,
            )

    messages.success(request, f'Copied trip to "{copied.name}".')
    return redirect('trips:trip_detail', pk=copied.pk)

