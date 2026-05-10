from django.db import models
from django.contrib.auth.models import User
from django.db.models import Sum
from decimal import Decimal
import uuid


# ── Trip ──────────────────────────────────────────────────────────────────────

class Trip(models.Model):
    """
    A user's overall travel plan.
    One Trip → many Stops → many Activities.
    """
    STATUS_CHOICES = [
        ('upcoming', 'Upcoming'),
        ('ongoing', 'Ongoing'),
        ('completed', 'Completed'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='trips'
    )
    name = models.CharField(max_length=200)
    start_date = models.DateField()
    end_date = models.DateField()
    description = models.TextField(blank=True)
    cover_photo = models.ImageField(
        upload_to='trip_covers/',
        null=True,
        blank=True
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='upcoming'
    )
    manual_hotel_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    manual_food_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    manual_transport_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    is_public = models.BooleanField(default=False)
    share_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Trip'
        verbose_name_plural = 'Trips'
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.name} ({self.user.username})"

    @property
    def total_budget(self):
        """Sum of all activity costs across all stops in this trip."""
        return self.stops.aggregate(
            total=Sum('activities__cost')
        )['total'] or 0

    @property
    def stop_count(self):
        return self.stops.count()

    @property
    def duration_days(self):
        if self.start_date and self.end_date:
            return (self.end_date - self.start_date).days + 1
        return 0


# ── Stop ──────────────────────────────────────────────────────────────────────

class Stop(models.Model):
    """
    A single city/destination within a Trip.
    Ordered by the `order` field so stops can be reordered.
    """
    trip = models.ForeignKey(
        Trip,
        on_delete=models.CASCADE,
        related_name='stops'
    )
    city_name = models.CharField(max_length=200)
    country = models.CharField(max_length=100, blank=True)
    start_date = models.DateField()
    end_date = models.DateField()
    order = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Stop'
        verbose_name_plural = 'Stops'
        ordering = ['order', 'start_date']

    def __str__(self):
        return f"{self.city_name} — {self.trip.name}"

    @property
    def stop_budget(self):
        """Sum of all activity costs within this stop."""
        return self.activities.aggregate(
            total=Sum('cost')
        )['total'] or 0

    @property
    def duration_days(self):
        if self.start_date and self.end_date:
            return (self.end_date - self.start_date).days + 1
        return 0


# ── Activity ──────────────────────────────────────────────────────────────────

class Activity(models.Model):
    """
    A single activity (sightseeing, meal, transport, etc.) within a Stop.
    Cost field drives the budget calculation up the chain.
    """
    CATEGORY_CHOICES = [
        ('sightseeing', 'Sightseeing'),
        ('food',        'Food & Dining'),
        ('transport',   'Transport'),
        ('accommodation', 'Accommodation'),
        ('adventure',   'Adventure'),
        ('shopping',    'Shopping'),
        ('culture',     'Culture & Arts'),
        ('other',       'Other'),
    ]

    stop = models.ForeignKey(
        Stop,
        on_delete=models.CASCADE,
        related_name='activities'
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    duration = models.PositiveIntegerField(
        help_text='Duration in minutes',
        default=60
    )
    category = models.CharField(
        max_length=30,
        choices=CATEGORY_CHOICES,
        default='other'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Activity'
        verbose_name_plural = 'Activities'
        ordering = ['created_at']

    def __str__(self):
        return f"{self.name} @ {self.stop.city_name}"

    @property
    def duration_display(self):
        hours, minutes = divmod(self.duration, 60)
        if hours and minutes:
            return f"{hours}h {minutes}m"
        elif hours:
            return f"{hours}h"
        return f"{minutes}m"


# ── ChecklistItem ─────────────────────────────────────────────────────────────

class ChecklistItem(models.Model):
    """
    A packing or task checklist item linked to a Trip.
    Users can check items off as they prepare for their journey.
    """
    CATEGORY_CHOICES = [
        ('documents',    'Documents'),
        ('clothing',     'Clothing'),
        ('electronics',  'Electronics'),
        ('toiletries',   'Toiletries'),
        ('medications',  'Medications'),
        ('other',        'Other'),
    ]

    trip = models.ForeignKey(
        Trip,
        on_delete=models.CASCADE,
        related_name='checklist_items'
    )
    name = models.CharField(max_length=200)
    is_completed = models.BooleanField(default=False)
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        default='other'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Checklist Item'
        verbose_name_plural = 'Checklist Items'
        ordering = ['category', 'name']

    def __str__(self):
        status = '✓' if self.is_completed else '○'
        return f"[{status}] {self.name} — {self.trip.name}"


# ── Note ──────────────────────────────────────────────────────────────────────

class Note(models.Model):
    """
    A free-text note or journal entry tied to a Trip.
    Users can jot hotel check-in details, reminders, etc.
    """
    trip = models.ForeignKey(
        Trip,
        on_delete=models.CASCADE,
        related_name='notes'
    )
    title = models.CharField(max_length=200, blank=True)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Note'
        verbose_name_plural = 'Notes'
        ordering = ['-created_at']

    def __str__(self):
        label = self.title if self.title else self.content[:40]
        return f"{label} — {self.trip.name}"


# ── Invoice / Billing ─────────────────────────────────────────────────────────

class Invoice(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
    ]

    trip = models.ForeignKey(
        Trip,
        on_delete=models.CASCADE,
        related_name='invoices',
    )
    invoice_id = models.CharField(max_length=30, unique=True)
    generated_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
    )
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        ordering = ['-generated_date']

    def __str__(self):
        return f"{self.invoice_id} — {self.trip.name}"

    @property
    def subtotal(self):
        return self.items.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    @property
    def tax(self):
        return (self.subtotal * Decimal('0.05')).quantize(Decimal('0.01'))

    @property
    def total(self):
        amount = self.subtotal + self.tax - self.discount
        if amount < 0:
            return Decimal('0.00')
        return amount.quantize(Decimal('0.01'))


class InvoiceItem(models.Model):
    CATEGORY_CHOICES = [
        ('hotel', 'Hotel'),
        ('travel', 'Travel'),
        ('food', 'Food'),
        ('activity', 'Activity'),
        ('shopping', 'Shopping'),
        ('other', 'Other'),
    ]

    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name='items',
    )
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default='activity')
    description = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField(default=1)
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"{self.description} ({self.invoice.invoice_id})"

    def save(self, *args, **kwargs):
        self.amount = (self.quantity * self.unit_cost).quantize(Decimal('0.01'))
        super().save(*args, **kwargs)
