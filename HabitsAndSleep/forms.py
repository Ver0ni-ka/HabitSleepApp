from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import PasswordChangeForm, UserCreationForm
from .models import User


class MyUserCreationForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-input', 'autocomplete': 'email'})
    )
    birthday = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-input', 'autocomplete': 'bday'})
    )
    first_name = forms.CharField(
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-input', 'autocomplete': 'given-name'})
    )
    gender = forms.ChoiceField(
        choices=User.GENDER_CHOICES,
        initial='PN',
        widget=forms.Select(attrs={'class': 'form-input'})
    )
    password1 = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={'class': 'form-input', 'autocomplete': 'new-password'})
    )
    password2 = forms.CharField(
        label="Password confirmation",
        widget=forms.PasswordInput(attrs={'class': 'form-input', 'autocomplete': 'new-password'})
    )
    # class for automatic form settings
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("first_name", "email", "birthday", "gender")

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Email already in use")
        return email
    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data["email"]
        if commit:
            user.save()
        return user

class LoginForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-input', 'autocomplete': 'email'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-input', 'autocomplete': 'current-password'})
    )
    remember_me = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'habit-quick-check'})
    )


class ProfileEditForm(forms.ModelForm):
    first_name = forms.CharField(
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-input', 'autocomplete': 'given-name'})
    )
    birthday = forms.DateField(
        required=False,
        widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-input', 'autocomplete': 'bday'})
    )
    gender = forms.ChoiceField(
        choices=User.GENDER_CHOICES,
        widget=forms.Select(attrs={'class': 'form-input'})
    )

    class Meta:
        model = User
        fields = ("first_name", "birthday", "gender")


class StyledPasswordChangeForm(PasswordChangeForm):
    old_password = forms.CharField(
        label="Old password",
        widget=forms.PasswordInput(attrs={'class': 'form-input', 'autocomplete': 'current-password'})
    )
    new_password1 = forms.CharField(
        label="New password",
        widget=forms.PasswordInput(attrs={'class': 'form-input', 'autocomplete': 'new-password'})
    )
    new_password2 = forms.CharField(
        label="New password confirmation",
        widget=forms.PasswordInput(attrs={'class': 'form-input', 'autocomplete': 'new-password'})
    )


class DeleteAccountForm(forms.Form):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-input', 'autocomplete': 'current-password'}),
        strip=False,
    )

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_password(self):
        password = self.cleaned_data.get('password')
        user = authenticate(username=self.user.username, password=password)
        if user is None:
            raise forms.ValidationError("Current password is incorrect.")
        return password
