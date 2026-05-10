from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import AuthenticationForm
from .models import UserProfile


# ── Login Form ────────────────────────────────────────────────────────────────

class LoginForm(AuthenticationForm):
    """Styled wrapper around Django's built-in AuthenticationForm."""

    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Username',
            'autofocus': True,
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Password',
        })
    )


# ── Registration Form ─────────────────────────────────────────────────────────

class RegisterForm(forms.ModelForm):
    """
    Collects first name, last name, email, username, and password.
    Matches the Registration Screen wireframe (Screen 2).
    """
    first_name = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'First Name',
        })
    )
    last_name = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Last Name',
        })
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Email Address',
        })
    )
    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Password',
        })
    )
    password2 = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm Password',
        })
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'username']
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Username',
            }),
        }

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('An account with this email already exists.')
        return email

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('password1')
        p2 = cleaned_data.get('password2')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError('Passwords do not match.')
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        if commit:
            user.save()
        return user


# ── Profile Update Forms ──────────────────────────────────────────────────────

class UserUpdateForm(forms.ModelForm):
    """Updates the core Django User fields."""
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'username']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name':  forms.TextInput(attrs={'class': 'form-control'}),
            'email':      forms.EmailInput(attrs={'class': 'form-control'}),
            'username':   forms.TextInput(attrs={'class': 'form-control'}),
        }


class ProfileUpdateForm(forms.ModelForm):
    """Updates the extended UserProfile fields."""
    class Meta:
        model = UserProfile
        fields = ['photo', 'phone_number', 'city', 'country', 'additional_info']
        widgets = {
            'phone_number':    forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone Number'}),
            'city':            forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'City'}),
            'country':         forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Country'}),
            'additional_info': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Additional Information...'}),
            'photo':           forms.FileInput(attrs={'class': 'form-control'}),
        }
