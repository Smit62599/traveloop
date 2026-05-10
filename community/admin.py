from django.contrib import admin

from .models import CommunityPost, Comment


@admin.register(CommunityPost)
class CommunityPostAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'trip', 'likes', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('title', 'content')


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('post', 'user', 'created_at')
