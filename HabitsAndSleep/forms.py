from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User


class MyUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    birthday = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
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
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)
    remember_me = forms.BooleanField(required=False)

class ProfileEditForm(forms.ModelForm):
    birthday = forms.DateField(widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}))
    class Meta:
        model = User
        fields = ("first_name", "birthday", "gender")

