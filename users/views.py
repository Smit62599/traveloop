from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User

from .forms import LoginForm, RegisterForm, UserUpdateForm, ProfileUpdateForm
from .models import UserProfile


# ── Login ─────────────────────────────────────────────────────────────────────

def login_view(request):
    """Authenticate an existing user and redirect to dashboard."""
    if request.user.is_authenticated:
        return redirect('trips:dashboard')

    form = LoginForm(request, data=request.POST or None)

    if request.method == 'POST':
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f'Welcome back, {user.first_name or user.username}! ✈️')
            next_url = request.GET.get('next', 'trips:dashboard')
            return redirect(next_url)
        else:
            messages.error(request, 'Invalid username or password. Please try again.')

    return render(request, 'users/login.html', {'form': form})


# ── Register ──────────────────────────────────────────────────────────────────

def register_view(request):
    """Create a new user account and auto-create their UserProfile."""
    if request.user.is_authenticated:
        return redirect('trips:dashboard')

    form = RegisterForm(request.POST or None)

    if request.method == 'POST':
        if form.is_valid():
            user = form.save()
            # Auto-create an empty UserProfile for the new user
            UserProfile.objects.create(user=user)
            login(request, user)
            messages.success(request, f'Account created! Welcome to Traveloop, {user.first_name or user.username}! 🌍')
            return redirect('trips:dashboard')
        else:
            messages.error(request, 'Please fix the errors below and try again.')

    return render(request, 'users/register.html', {'form': form})


# ── Logout ────────────────────────────────────────────────────────────────────

def logout_view(request):
    """Log the current user out and redirect to login."""
    logout(request)
    messages.info(request, 'You have been logged out. Safe travels! 👋')
    return redirect('users:login')


# ── Profile ───────────────────────────────────────────────────────────────────

@login_required
def profile_view(request):
    """
    Display and update the user's profile.
    Uses two forms: one for User fields, one for UserProfile fields.
    """
    # Ensure UserProfile exists (safety net for users created via admin)
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    user_form    = UserUpdateForm(instance=request.user)
    profile_form = ProfileUpdateForm(instance=profile)

    if request.method == 'POST':
        user_form    = UserUpdateForm(request.POST, instance=request.user)
        profile_form = ProfileUpdateForm(request.POST, request.FILES, instance=profile)

        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('users:profile')
        else:
            messages.error(request, 'Please fix the errors below.')

    # Fetch trips for the profile page sidebar (recent 6)
    recent_trips = request.user.trips.order_by('-start_date')[:6]

    context = {
        'user_form':    user_form,
        'profile_form': profile_form,
        'profile':      profile,
        'recent_trips': recent_trips,
    }
    return render(request, 'users/profile.html', context)

