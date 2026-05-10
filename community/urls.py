from django.urls import path
from . import views

app_name = 'community'

urlpatterns = [
    path('', views.community_feed, name='feed'),
    path('post/new/', views.create_post, name='create_post'),
    path('post/<int:pk>/', views.post_detail, name='post_detail'),
    path('post/<int:post_pk>/comment/', views.add_comment, name='add_comment'),
    path('post/<int:post_pk>/like/', views.like_post, name='like_post'),
]
