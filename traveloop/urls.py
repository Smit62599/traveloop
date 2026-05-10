from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from trips.views import admin_dashboard

urlpatterns = [
    path('admin/', admin.site.urls),

    # Redirect root to login
    path('', RedirectView.as_view(url='/users/login/', permanent=False)),
    path('admin-dashboard/', admin_dashboard, name='admin_dashboard'),

    # App URL includes
    path('users/', include('users.urls', namespace='users')),
    path('trips/', include('trips.urls', namespace='trips')),
    path('community/', include('community.urls', namespace='community')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
