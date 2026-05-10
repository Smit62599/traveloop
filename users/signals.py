from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import UserProfile


@receiver(post_delete, sender=UserProfile)
def delete_userprofile_photo(sender, instance, **kwargs):
    """Remove profile image from disk when the profile row is deleted."""
    if instance.photo:
        instance.photo.delete(save=False)
