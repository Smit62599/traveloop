from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.db.models import Q

from trips.models import Trip
from .models import CommunityPost, Comment
from .forms import PostForm, CommentForm


@login_required
def community_feed(request):
    posts = CommunityPost.objects.select_related('user', 'trip').all()
    q = request.GET.get('q', '').strip()
    if q:
        posts = posts.filter(Q(title__icontains=q) | Q(content__icontains=q))

    sort = request.GET.get('sort', 'newest')
    if sort == 'popular':
        posts = posts.order_by('-likes', '-created_at')
    else:
        posts = posts.order_by('-created_at')

    return render(request, 'community/feed.html', {
        'posts': posts,
        'q': q,
        'sort': sort,
    })


@login_required
def create_post(request):
    trip = None
    trip_id = request.GET.get('trip')
    if trip_id:
        trip = get_object_or_404(Trip, pk=trip_id, user=request.user)

    initial = {}
    if trip:
        initial['title'] = f"My trip: {trip.name}"
        stops = trip.stops.order_by('order', 'start_date').values_list('city_name', flat=True)
        cities = ', '.join(stops) if stops else '—'
        initial['content'] = (
            f"Trip: {trip.name}\n"
            f"Dates: {trip.start_date} → {trip.end_date}\n"
            f"Stops: {cities}\n\n"
        )

    if request.method == 'POST':
        form = PostForm(request.POST)
        if form.is_valid():
            post = form.save(commit=False)
            post.user = request.user
            tid = request.POST.get('trip_id')
            if tid:
                linked = get_object_or_404(Trip, pk=tid, user=request.user)
                post.trip = linked
            post.save()
            messages.success(request, 'Your post is live on the community feed.')
            return redirect('community:post_detail', pk=post.pk)
        messages.error(request, 'Please fix the errors below.')
    else:
        form = PostForm(initial=initial)

    return render(request, 'community/create_post.html', {
        'form': form,
        'trip': trip,
    })


@login_required
def post_detail(request, pk):
    post = get_object_or_404(
        CommunityPost.objects.select_related('user', 'trip'),
        pk=pk,
    )
    comments = post.comments.select_related('user').all()
    comment_form = CommentForm()

    return render(request, 'community/post_detail.html', {
        'post': post,
        'comments': comments,
        'comment_form': comment_form,
    })


@login_required
@require_POST
def add_comment(request, post_pk):
    post = get_object_or_404(CommunityPost, pk=post_pk)
    form = CommentForm(request.POST)
    if form.is_valid():
        c = form.save(commit=False)
        c.post = post
        c.user = request.user
        c.save()
        messages.success(request, 'Comment added.')
    else:
        messages.error(request, 'Could not add comment.')
    return redirect('community:post_detail', pk=post.pk)


@login_required
@require_POST
def like_post(request, post_pk):
    post = get_object_or_404(CommunityPost, pk=post_pk)
    post.likes = (post.likes or 0) + 1
    post.save(update_fields=['likes'])
    messages.success(request, 'Thanks for the like!')
    return redirect('community:post_detail', pk=post.pk)
