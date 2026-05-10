from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import Trip


@receiver(post_delete, sender=Trip)
def delete_trip_cover_photo(sender, instance, **kwargs):
    """Remove cover image from disk when the trip row is deleted."""
    if instance.cover_photo:
        instance.cover_photo.delete(save=False)
