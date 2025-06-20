from django import forms

from django.contrib.auth import get_user_model
from .models import Profile
from .models import Address
from django.contrib.auth.forms import PasswordChangeForm

import re


User = get_user_model() 
class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["username",]


    def clean_username(self):
        username = self.cleaned_data.get('username')
        user_id = self.instance.id  # Current user ID

        # Check if the username exists for a different user
        if User.objects.exclude(pk=user_id).filter(username=username).exists():
            raise forms.ValidationError("This username is already taken.")

        # Only allow letters (no numbers, symbols, or spaces)
        if not re.match(r'^[A-Za-z]+$', username):
            raise forms.ValidationError("Username must contain only letters (no numbers, spaces, or symbols).")
        
        return username




class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ["mobile_number"]

    def clean_mobile_number(self):
        mobile = self.cleaned_data.get('mobile_number')
        if not re.fullmatch(r'\d{10}', mobile):
            raise forms.ValidationError("Enter a valid 10-digit mobile number without alphabets or spaces.")
        return mobile
 

class AddressForm(forms.ModelForm):
    class Meta:
        model = Address
        fields = ['first_name', 'last_name', 'postcode', 'mobile', 'house_no', 'street_address']


    def clean_postcode(self):
        postcode = self.cleaned_data.get('postcode')
        if not postcode.isdigit():
            raise forms.ValidationError("Postcode must contain only numbers.")
        return postcode


    def clean_mobile_number(self):
        mobile = self.cleaned_data.get('mobile_number')
        if not re.fullmatch(r'\d{10}', mobile):
            raise forms.ValidationError("Enter a valid 10-digit mobile number without alphabets or spaces.")
        return mobile  
    

    def clean_first_name(self):
        first_name = self.cleaned_data.get('first_name')
        if not first_name.isalpha():
            raise forms.ValidationError("First name should contain only letters.")
        return first_name

    def clean_last_name(self):
        last_name = self.cleaned_data.get('last_name')
        if not last_name.isalpha():
            raise forms.ValidationError("Last name should contain only letters.")
        return last_name

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if not username.isalpha():
            raise forms.ValidationError("Username should contain only letters.")
        return username


    def clean_mobile(self):
        mobile = self.cleaned_data.get('mobile')

        if not re.fullmatch(r'\d{10}', mobile):
            raise forms.ValidationError("Enter a valid 10-digit mobile number without alphabets.")

        return mobile  
    
    def clean_first_name(self):
        first_name = self.cleaned_data.get('first_name')
        if not first_name.isalpha():
            raise forms.ValidationError("First name should contain only letters.")
        return first_name

    def clean_last_name(self):
        last_name = self.cleaned_data.get('last_name')
        if not last_name.isalpha():
            raise forms.ValidationError("Last name should contain only letters.")
        return last_name


class CustomPasswordResetForm(forms.Form):
    email = forms.EmailField(
        label="Enter your email",
        widget=forms.EmailInput(attrs={"class": "form-control", "placeholder": "Enter your email"}),
    )

    def clean_email(self):
        email = self.cleaned_data["email"]
        if not User.objects.filter(email=email).exists():
            raise forms.ValidationError("No account is associated with this email.")
        return email
    



