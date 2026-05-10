from decimal import Decimal

from django.db.models import Sum


CITY_COST_DATA = {
    "Goa": {
        "hotel_per_day": 3000,
        "food_per_day": 800,
        "transport_base": 2000,
    },
    "Mumbai": {
        "hotel_per_day": 4000,
        "food_per_day": 1000,
        "transport_base": 2500,
    },
    "Ahmedabad": {
        "hotel_per_day": 2000,
        "food_per_day": 600,
        "transport_base": 1500,
    },
}

DEFAULT_CITY_COST = {
    "hotel_per_day": 2500,
    "food_per_day": 700,
    "transport_base": 1800,
}


def _city_cost(city_name):
    if not city_name:
        return DEFAULT_CITY_COST
    key = city_name.strip().title()
    return CITY_COST_DATA.get(key, DEFAULT_CITY_COST)


def calculate_trip_budget(trip):
    """
    Dynamic budget estimator using stop city static costs + activity costs.
    Supports manual category-level overrides on Trip.
    """
    total_hotel = Decimal("0.00")
    total_food = Decimal("0.00")
    total_transport = Decimal("0.00")
    total_activity = Decimal("0.00")
    stop_rows = []

    stops = trip.stops.prefetch_related('activities').order_by('order', 'start_date')
    for stop in stops:
        days = max((stop.end_date - stop.start_date).days + 1, 1)
        city_cost = _city_cost(stop.city_name)

        hotel_cost = Decimal(days) * Decimal(city_cost["hotel_per_day"])
        food_cost = Decimal(days) * Decimal(city_cost["food_per_day"])
        transport_cost = Decimal(city_cost["transport_base"])
        activity_cost = stop.activities.aggregate(total=Sum('cost'))['total'] or Decimal("0.00")

        total_hotel += hotel_cost
        total_food += food_cost
        total_transport += transport_cost
        total_activity += activity_cost

        stop_total = hotel_cost + food_cost + transport_cost + activity_cost
        stop_rows.append({
            'stop_id': stop.id,
            'city_name': stop.city_name,
            'start_date': stop.start_date,
            'days': days,
            'total': stop_total,
            'day_cost': (stop_total / Decimal(days)).quantize(Decimal("0.01")),
        })

    # Manual overrides on trip (if present)
    hotel_value = trip.manual_hotel_cost if trip.manual_hotel_cost is not None else total_hotel
    food_value = trip.manual_food_cost if trip.manual_food_cost is not None else total_food
    transport_value = trip.manual_transport_cost if trip.manual_transport_cost is not None else total_transport

    grand_total = hotel_value + food_value + transport_value + total_activity
    trip_days = max(trip.duration_days, 1)
    avg_per_day = (grand_total / Decimal(trip_days)).quantize(Decimal("0.01"))

    over_budget_stops = [
        s for s in stop_rows
        if s['day_cost'] > avg_per_day
    ]

    return {
        "hotel": hotel_value.quantize(Decimal("0.01")),
        "food": food_value.quantize(Decimal("0.01")),
        "transport": transport_value.quantize(Decimal("0.01")),
        "activities": total_activity.quantize(Decimal("0.01")),
        "total": grand_total.quantize(Decimal("0.01")),
        "avg_per_day": avg_per_day,
        "over_budget_stops": over_budget_stops,
        "warning": bool(over_budget_stops),
    }
