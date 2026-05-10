from django.urls import path
from . import views

app_name = 'trips'

urlpatterns = [
    path('dashboard/',          views.dashboard,    name='dashboard'),
    path('activities/search/',  views.activity_search, name='activity_search'),
    path('',                    views.trip_list,    name='trip_list'),
    path('create/',             views.trip_create,  name='trip_create'),
    path('<int:pk>/',           views.trip_detail,  name='trip_detail'),
    path('<int:pk>/edit/',      views.trip_edit,    name='trip_edit'),
    path('<int:pk>/delete/',    views.trip_delete,  name='trip_delete'),
    path('<int:trip_pk>/stops/add/', views.stop_create, name='stop_create'),
    path(
        '<int:trip_pk>/stops/<int:stop_pk>/edit/',
        views.stop_edit,
        name='stop_edit',
    ),
    path(
        '<int:trip_pk>/stops/<int:stop_pk>/delete/',
        views.stop_delete,
        name='stop_delete',
    ),
    path(
        '<int:trip_pk>/stops/<int:stop_pk>/activities/add/',
        views.activity_create,
        name='activity_create',
    ),
    path(
        '<int:trip_pk>/stops/<int:stop_pk>/activities/<int:activity_pk>/edit/',
        views.activity_edit,
        name='activity_edit',
    ),
    path(
        '<int:trip_pk>/stops/<int:stop_pk>/activities/<int:activity_pk>/delete/',
        views.activity_delete,
        name='activity_delete',
    ),
    path('<int:trip_pk>/checklist/', views.trip_checklist, name='checklist'),
    path(
        '<int:trip_pk>/checklist/<int:item_pk>/toggle/',
        views.checklist_item_toggle,
        name='checklist_item_toggle',
    ),
    path(
        '<int:trip_pk>/checklist/<int:item_pk>/delete/',
        views.checklist_item_delete,
        name='checklist_item_delete',
    ),
    path('<int:trip_pk>/notes/add/', views.note_create, name='note_create'),
    path(
        '<int:trip_pk>/notes/<int:note_pk>/edit/',
        views.note_edit,
        name='note_edit',
    ),
    path(
        '<int:trip_pk>/notes/<int:note_pk>/delete/',
        views.note_delete,
        name='note_delete',
    ),
    path('<int:trip_pk>/invoice/', views.invoice_detail, name='invoice_detail'),
    path(
        'invoice/<str:invoice_id>/mark-paid/',
        views.mark_invoice_paid,
        name='mark_invoice_paid',
    ),
    path('<int:pk>/toggle-public/', views.toggle_trip_public, name='toggle_trip_public'),
    path('public/<str:token>/', views.public_trip_view, name='public_trip_view'),
    path('<int:id>/copy/', views.copy_trip, name='copy_trip'),
]

