from django.http import HttpResponse
import random
from django.shortcuts import render, redirect,get_object_or_404
from django.core.mail import send_mail
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.models import User
from django.utils import timezone
from django.contrib.auth import authenticate, login, logout,login as auth_login
from django.contrib.auth.decorators import login_required
import datetime
from django.template.loader import render_to_string
import pdfkit
from django.utils.crypto import get_random_string
import os
from django.utils.timezone import now
import datetime
import pytz
import re
from django.utils.timezone import localtime
from django.utils import timezone
from datetime import datetime
from .utils import send_otp_to_email
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from decimal import ROUND_DOWN
from datetime import timedelta, date
from django.core.cache import cache
from django.views.decorators.cache import never_cache,cache_control
from products.models import Product,ProductVariant,Order,Cart,CartItem,ProductOffer, CategoryOffer, ReferralOffer,OrderItem, Coupon
from django.contrib.auth import update_session_auth_hash
from .models import Profile
from .forms import UserUpdateForm, ProfileUpdateForm
from django.views.decorators.cache import never_cache
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from .models import Address
from .forms import AddressForm
from django.contrib.auth.views import PasswordResetConfirmView
import json
from django.contrib.auth.models import User
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_decode
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth import views as auth_views
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.forms import SetPasswordForm
from .forms import CustomPasswordResetForm
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.contrib.auth import get_user_model
from .models import Wallet, Transaction
import razorpay
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.template.loader import get_template
from xhtml2pdf import pisa
import paypalrestsdk
from django.urls import reverse
from django.db import transaction
import logging
from django.contrib.auth import get_backends
from razorpay.errors import BadRequestError, ServerError
import uuid
from payment.views import set_delivery_date
from decimal import Decimal
from datetime import timedelta
from functools import wraps
from django.utils.cache import add_never_cache_headers





logger = logging.getLogger(__name__)

client = razorpay.Client(auth=("rzp_test_4MBYamMKeUifHI", "jCW28TZMPhifXUXSBo4CVB8I"))


def no_cache(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        response = view_func(request, *args, **kwargs)
        add_never_cache_headers(response)
        return response
    return _wrapped_view


@never_cache
@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def index(request):
    return render(request,'user/index.html')


@login_required
def google_login_redirect(request):
    return render(request,'user/index.html')


logger = logging.getLogger(__name__)

User = get_user_model()
@never_cache
def user_login(request):
    if request.user.is_authenticated:
        return redirect('index')
    
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')

        # Log email and password for debugging (Do not use in production)
        logger.debug(f"Email: {email}, Password: {password}")

        try:
            users = User.objects.filter(email=email)
            if users.exists():
                user = None
                for user_obj in users:
                    user = authenticate(username=user_obj.username, password=password)
                    if user is not None:
                        break
            else:
                user = None
        except User.DoesNotExist:
            user = None

        if user is not None:
            if user.is_active:
                auth_login(request, user)   
                return redirect('index')
        else:
            messages.error(request, 'Invalid email address or password. Please try again.')
            return redirect('login')
    return render(request, 'user/login.html')
  

def signup(request):
    if request.method == "POST":
        username = request.POST['username']
        email = request.POST['email']
        password = request.POST['password']

        # ✅ Username must contain only alphabets
        if not username.isalpha():
            messages.error(request, "Username must contain only alphabets.")
            return redirect('signup')

        # ✅ Validate email format
        try:
            validate_email(email)
        except ValidationError:
            messages.error(request, "Invalid email format.")
            return redirect('signup')

        # ❌ Email already exists
        if User.objects.filter(email=email).exists():
            messages.error(request, "Email is already registered. Please login or use another email.")
            return redirect('signup')

        # ✅ Password validation: at least 8 chars, contains letter, number, and symbol
        if len(password) < 8:
            messages.error(request, "Password must be at least 8 characters long.")
            return redirect('signup')

        if not re.search(r'[A-Za-z]', password):
            messages.error(request, "Password must contain at least one letter.")
            return redirect('signup')

        if not re.search(r'\d', password):
            messages.error(request, "Password must contain at least one number.")
            return redirect('signup')

        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            messages.error(request, "Password must contain at least one symbol.")
            return redirect('signup')

        # ✅ All validations passed — create user
        myuser = User.objects.create_user(username=username, email=email, password=password)
        myuser.save()

        # 🔐 Generate OTP and store with 5-minute expiry
        otp = random.randint(1000, 9999)
        expiry_time = now() + timedelta(minutes=5)
        cache.set(email, {'otp': otp, 'expiry': expiry_time}, timeout=300)

        # ✅ Send OTP to email
        try:
            send_mail(
                'Your OTP for Verification',
                f'Your OTP is: {otp}. It will expire in 5 minutes.',
                'jayasreeidhunov@gmail.com',  # Must match your settings.py
                [email],
                fail_silently=False,
            )
        except Exception as e:
            messages.error(request, f"Failed to send OTP: {str(e)}")
            return redirect('signup')

        # ✅ Store email in session for verification page
        request.session['email'] = email
        messages.success(request, "OTP sent to your email. Please verify.")
        return redirect('otp_verification')

    return render(request, 'user/signup.html')

def otp_verification(request):
    if request.method == "POST":
        entered_otp = request.POST.get('otp')
        email = request.session.get('email')

        otp_data = cache.get(email)
        if not otp_data:
            messages.error(request, "OTP expired. Please request a new one.")
            return redirect('signup')  # Redirect to signup or OTP resend

        stored_otp = otp_data['otp']
        expiry = otp_data['expiry']

        if now() > expiry:
            messages.error(request, "OTP expired. Please request a new one.")
            return redirect('signup')

        if str(entered_otp) == str(stored_otp):
            cache.delete(email)  # Clear OTP from cache
            messages.success(request, "OTP verified successfully!")
            return redirect('login')
        else:
            messages.error(request, "Invalid OTP. Please try again.")

    return render(request, 'user/otp_verification.html')


def resend_otp(request):
    email = request.session.get('email')
    if not email:
        messages.error(request, "Session expired. Please sign up again.")
        return redirect('signup')

    otp = random.randint(1000, 9999)
    expiry_time = now() + datetime.timedelta(minutes=5)

    cache.set(email, {'otp': otp, 'expiry': expiry_time}, timeout=300)

    send_mail(
        'Your New OTP for Verification',
        f'Your new OTP is: {otp}. It will expire in 5 minutes.',
        'jayasreeidhunov@gmail.com',  
        [email],
        fail_silently=False,
    )

    messages.success(request, "A new OTP has been sent to your email.")
    return redirect('otp_verification')


@login_required
def logout_view(request):
    logout(request)
    return redirect('index')

@login_required
@never_cache
def profile(request):
    if request.user.is_superuser:
        return redirect("index") 
    
    if not hasattr(request.user, 'profile'):
        Profile.objects.create(user=request.user)

    if request.method == "POST":
        user_form = UserUpdateForm(request.POST, instance=request.user)
        profile_form = ProfileUpdateForm(request.POST, instance=request.user.profile)

        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, "Profile updated successfully!")
            return redirect("user_profile")  # Ensure this is the correct URL name
    else:
        user_form = UserUpdateForm(instance=request.user)
        profile_form = ProfileUpdateForm(instance=request.user.profile)

    return render(request, "user/user_profile.html", {
        "user_form": user_form,
        "profile_form": profile_form,
    })
# def profile(request):
#     if request.user.is_superuser:
#         return redirect("index")

#     if not hasattr(request.user, "profile"):
#         Profile.objects.create(user=request.user)

#     if request.method == "POST":
#         user_form = UserUpdateForm(request.POST, instance=request.user)
#         profile_form = ProfileUpdateForm(request.POST, instance=request.user.profile)
#         password_form = PasswordChangeForm(request.user, request.POST)

#         if user_form.is_valid() and profile_form.is_valid() and password_form.is_valid():
#             user_form.save()
#             profile_form.save()
#             password_form.save()
#             update_session_auth_hash(request, password_form.user)  # Keep user logged in after password change
#             messages.success(request, "Profile updated successfully!")
#             return redirect("user_profile")
#     else:
#         user_form = UserUpdateForm(instance=request.user)
#         profile_form = ProfileUpdateForm(instance=request.user.profile)
#         password_form = PasswordChangeForm(request.user)

#     return render(request, "user/user_profile.html", {
#         "user_form": user_form,
#         "profile_form": profile_form,
#         "password_form": password_form,
#     })
    

@login_required
def change_password(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # Important to keep the user logged in
            messages.success(request, 'Your password was successfully updated!')
            return redirect('index')
        else:
            messages.error(request, 'Please correct the error below.')
    else:
        form = PasswordChangeForm(request.user)
    return render(request, 'user/change_password.html', {
        'form': form
    })








@login_required
def add_address(request):
    next_url = request.GET.get('next', 'checkoutpage')  # Default to checkout page if no address exists

    if request.method == 'POST':	
        form = AddressForm(request.POST)
        if form.is_valid():
            address = form.save(commit=False)
            address.user = request.user
            address.save()
            return redirect(next_url)  # Redirect to checkout page 
    else:
        form = AddressForm()

    return render(request, 'user/add_Address.html', {'form': form})






@login_required
def edit_address(request, address_id):
    address = get_object_or_404(Address, id=address_id, user=request.user)

   
    next_url = request.GET.get('next') or request.POST.get('next')

    if request.method == 'POST':
        form = AddressForm(request.POST, instance=address)
        if form.is_valid():
            form.save()
            return redirect(next_url or 'user_profile')  # Redirect to 'next' or default to 'profile'
    else:
        form = AddressForm(instance=address)

    return render(request, 'user/edit_address.html', {
        'form': form,
        'next': next_url  
    })



@login_required
def delete_address(request, address_id):
    address = get_object_or_404(Address, id=address_id, user=request.user)
    address.delete()

    # Redirect back to the checkout page if the user came from there
    next_url = request.GET.get('next', 'user_profile')
    return redirect(next_url)


@login_required
def cart(request):
    return render(request,'user/cart_detail.html')





logger = logging.getLogger(__name__)



@login_required
def checkout(request):
    addresses = Address.objects.filter(user=request.user)
    cart, created = Cart.objects.get_or_create(user=request.user)
    cart_items = CartItem.objects.filter(cart=cart)

    valid_cart_items = []
    unavailable_items = []

    for item in cart_items:
        product = item.product
        category_active = product.category.is_active if product.category else True

        if product.is_deleted or not (product.is_active and category_active and product.stock > 0):
            unavailable_items.append(item)
        else:
            valid_cart_items.append(item)

    if not valid_cart_items:
        messages.error(request, "All items in your cart are unavailable. Please update your cart.")
        return redirect('cart')

    cart_items_with_total = []
    total_price = Decimal('0.0')

    for item in valid_cart_items:
        item_total = Decimal(str(item.price)) * item.quantity
        total_price += item_total
        cart_items_with_total.append({'item': item, 'item_total': item_total})

    # ---------- Handle Coupons ----------
    discount_amount = Decimal('0.0')
    coupon_code = cart.coupon_code

    if coupon_code:
        try:
            coupon = Coupon.objects.get(
                code=coupon_code,
                valid_from__lte=timezone.now(),
                valid_until__gte=timezone.now(),
                active=True,
                usage_limit__gt=0
            )
            if total_price >= 30000:
                discount_amount = (coupon.discount / 100) * total_price
            else:
                cart.coupon_code = ''
                cart.discount_amount = 0
                cart.coupon = None
                cart.save()
                request.session.pop('coupon_id', None)
                request.session.pop('applied_coupon', None)
        except Coupon.DoesNotExist:
            cart.coupon_code = ''
            cart.discount_amount = 0
            cart.coupon = None
            cart.save()
            request.session.pop('coupon_id', None)
            request.session.pop('applied_coupon', None)

    final_price = total_price - discount_amount
    delivery_charge = Decimal('60.0')
    final_price += delivery_charge
    final_price = final_price.quantize(Decimal('0.01'), rounding=ROUND_DOWN)

    if final_price < 0:
        messages.error(request, "Invalid total price. Please review your cart.")
        return redirect('cartpage')

    # ---------- Order Placement ----------
    if request.method == 'POST':
        selected_address_id = request.POST.get('address_id')
        payment_option = request.POST.get('payment_option')

        if not selected_address_id:
            messages.error(request, "Please select an address.")
            return redirect('checkoutpage')

        if not payment_option:
            messages.error(request, "Please select a payment option.")
            return redirect('checkoutpage')

        selected_address = get_object_or_404(Address, id=selected_address_id, user=request.user)

        # ✅ Validate stock AGAIN just before placing the order
        for item in valid_cart_items:
            product = item.product
            product.refresh_from_db()
            if item.quantity > product.stock:
                messages.error(request, f"Sorry, only {product.stock} units left for {product.name}. Please update your cart.")
                return redirect('cartpage')

        # ✅ Create Order only after passing stock validation
        order = Order.objects.create(
            user=request.user,
            address=selected_address,
            total_price=final_price,
            status='Pending',
            payment_method=payment_option.upper(),
            coupon=coupon if coupon_code else None,
            coupon_code=coupon_code,
            discount_amount=discount_amount,
            delivery_charge=delivery_charge,
        )

        # ✅ Reduce stock and create OrderItems
        for item in valid_cart_items:
            product = item.product
            product.stock -= item.quantity
            product.save()

            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=item.quantity,
                price=item.price
            )

        CartItem.objects.filter(cart=cart).delete()
        cart.coupon_code = ''
        cart.discount_amount = 0
        cart.save()
        request.session.pop('coupon_id', None)
        request.session.pop('applied_coupon', None)

        if payment_option == 'razorpay':
            client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
            payment = client.order.create({
                "amount": int(final_price * 100),
                "currency": "INR",
                "payment_capture": 1
            })

            order.razorpay_payment_id = payment['id']
            order.save()

            context = {
                'payment': payment,
                'order': order,
                'addresses': addresses,
                'cart_items': cart_items_with_total,
                'total_price': total_price,
                'discount_amount': discount_amount,
                'delivery_charge': delivery_charge,
                'final_price': final_price,
                'subtotal_after_discount': total_price - discount_amount
            }
            return render(request, 'user/razorpay_payment.html', context)

        elif payment_option == 'cod':
            order.status = 'Pending'
            order.payment_status = 'Pending'
            order.save()
            messages.success(request, "Order placed successfully with Cash on Delivery!")
            return redirect('my_orders')

    # ---------- Render checkout page ----------
    context = {
        'addresses': addresses,
        'cart_items': cart_items_with_total,
        'total_price': total_price,
        'discount_amount': discount_amount,
        'delivery_charge': delivery_charge,
        'final_price': final_price,
    }

    return render(request, 'user/checkoutpage.html', context)




def create_payment(request):
    return render(request, 'payment/create_payment.html') 

@login_required
def order_confirmation(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'user/order_confirmation.html', {'order': order}) 



@login_required
def place_order(request):
    if request.method == 'POST':
        address_id = request.POST.get('address_id')
        payment_option = request.POST.get('payment_option')

        if not address_id:
            messages.error(request, "Please select an address before placing the order.")
            return redirect('checkoutpage')

        if not payment_option:
            messages.error(request, "Please select a payment option.")
            return redirect('checkoutpage')

        selected_address = get_object_or_404(Address, id=address_id, user=request.user)
        cart, created = Cart.objects.get_or_create(user=request.user)
        cart_items = CartItem.objects.filter(cart=cart)

        if not cart_items:
            messages.error(request, "Your cart is empty. Add items before placing the order.")
            return redirect('checkoutpage')

        #  Separate valid and inactive products
        valid_cart_items = []
        unavailable_items = []

        for item in cart_items:
            product = item.product
            category_active = product.category.is_active if product.category else True

            if (
                product.is_deleted or
                not (product.is_active and category_active and product.stock > 0)
            ):
                unavailable_items.append(item)
            else:
                valid_cart_items.append(item)

 
        #  If ALL items in cart are inactive, prevent checkout
        if not valid_cart_items:
            messages.error(request, "All products in your cart are unavailable. Please update your cart.")
            return redirect('cartpage')

        #  Calculate total price only for valid items
        total_price = sum(item.price * item.quantity for item in valid_cart_items)

        # Apply discount if a coupon is used
        discount_amount = Decimal('0.0')
        coupon_instance = None
        coupon_data = request.session.get('applied_coupon')

        if coupon_data:
            try:
                coupon_instance = Coupon.objects.get(code=coupon_data['code'])
                if coupon_instance.discount_type == 'percentage':
                    discount_amount = (coupon_instance.discount / 100) * total_price
                else:
                    discount_amount = coupon_instance.discount
            except (Coupon.DoesNotExist, KeyError, ValueError):
                coupon_instance = None  
                discount_amount = Decimal('0.0')

        total_price -= discount_amount

        # Ensure final price not negative
        if total_price < 0:
            total_price = Decimal('0.0')

        # Add delivery charge
        delivery_charge = Decimal('60.00')
        total_price += delivery_charge

        # estimated_delivery = date.today() + timedelta(days=5)
        estimated_delivery_naive = datetime.now() + timedelta(days=5)
        estimated_delivery = timezone.make_aware(estimated_delivery_naive)

        #  Create order only for valid items
        order = Order.objects.create(
            user=request.user,
            address=selected_address,
            total_price=total_price,
            delivery_charge=delivery_charge,
            payment_method=payment_option,
            delivery_date=estimated_delivery,
            coupon=coupon_instance if coupon_instance else None,
            coupon_code=coupon_instance.code if coupon_instance else '',
            discount_amount=discount_amount,



            first_name=selected_address.first_name,
            last_name=selected_address.last_name,
            mobile=selected_address.mobile,
            street_address=selected_address.street_address,
            house_no=selected_address.house_no,
            postcode=selected_address.postcode,
        )
        order.save()

        # Add valid items to order
        for item in valid_cart_items:
            OrderItem.objects.create(order=order, product=item.product, quantity=item.quantity, price=item.price)

            # Reduce stock
            product = item.product
            if product.stock >= item.quantity:
                product.stock -= item.quantity
                product.save()
            else:
                messages.error(request, f"Not enough stock for {product.name}.")
                return redirect('checkoutpage')

        #  Remove valid items from cart but keep inactive ones

        CartItem.objects.filter(cart=cart, product__category__is_active=True).delete()
        
        #  Remove coupon from session
       

        #  Handle payment options
        if payment_option == "cash_on_delivery":
            order.cod_transaction_id = "COD-" + get_random_string(10).upper()
            order.status = "Pending"
            order.save()

            request.session.pop('coupon_id', None)
            request.session.pop('applied_coupon', None)

            messages.success(request, "Order placed successfully with Cash on Delivery!")
            return redirect('order_confirmation', order_id=order.id)

        elif payment_option == 'RAZORPAY':
            try:
                client = razorpay.Client(auth=("rzp_test_MAimzLa32DUYt6", "qbDDZBXaEQPNG72T9ZPVPytC"))
                amount_in_paise = int(total_price * 100)
                razorpay_order = client.order.create({'amount': amount_in_paise, 'currency': 'INR', 'payment_capture': '1'})
                order.razorpay_order_id = razorpay_order.get('id')
                order.save()

                request.session.pop('coupon_id', None)
                request.session.pop('applied_coupon', None)
                   
                return redirect('initiate_payment', order_id=order.id)
            
            except Exception as e:
                messages.error(request, "Error processing Razorpay payment: " + str(e))

                order.status = "Failed"
                order.save()
                # order.delete()
                return redirect('checkoutpage')

        #  Redirect to order confirmation
        return redirect('order_confirmation', order_id=order.id)

    return redirect('checkoutpage')












@login_required
def my_orders(request):
    orders = Order.objects.filter(user=request.user).prefetch_related('order_items__product').order_by('-created_at')
    return render(request, 'user/my_order.html', {'orders': orders})



@login_required
def cancel_order(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    
    if order.status not in ['Delivered', 'Cancelled']:  
        order.status = 'Cancelled'
        order.save()
    
    return redirect('my_orders') 







#forgot password

@csrf_exempt
def return_order(request, order_id):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            return_reason = data.get("return_reason", "")

            order = Order.objects.get(id=order_id)
            print(f"Order ID: {order.id}, Current Status: {order.status}") 

            # Prevent duplicate return processing
            if order.status in ["Return Completed", "Return Rejected"]:
                return JsonResponse({"success": False, "error": f"Return cannot be processed, current status: {order.status}."})

            # If order is eligible for return mark Return Requested instead of Return Completed
            if order.status == "Delivered":
                order.status = "Return Requested"
                order.save()
                return JsonResponse({"success": True, "message": "Return request submitted. Awaiting admin approval."})

            # Only process return if admin has already accepted it
            if order.status == "Return Accepted":
                order.status = "Return Completed"
                order.save()
            

                # Credit the amount to the user's wallet
                wallet, created = Wallet.objects.get_or_create(user=order.user)
                wallet.balance += order.total_price
                wallet.save()

                # Log the refund transaction
                Transaction.objects.create(
                    wallet=wallet,
                    amount=order.total_price, 
                    transaction_type="refund"
                )

                return JsonResponse({"success": True, "message": "Return completed. Amount credited to wallet."})

            return JsonResponse({"success": False, "error": "Invalid return request. Contact support."})
           

        except Order.DoesNotExist:
            return JsonResponse({"success": False, "error": "Order not found."})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})

    return JsonResponse({"success": False, "error": "Invalid request method."})

#close return order

User = get_user_model()

def custom_password_reset_request(request):
    form = CustomPasswordResetForm()
    if request.method == "POST":
        email = request.POST.get("email")
        users = User.objects.filter(email=email)

        if users.exists():
            user = users.first()
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            reset_url = f"http://127.0.0.1:8000//reset-password/{uid}/{token}/"

            send_mail(
                "Password Reset Request",
                f"Click the link to reset your password: {reset_url}",
                "noreply@yourdomain.com",
                [email],
                fail_silently=False,
            )

            messages.success(request, "A password reset link has been sent to your email.")
            return redirect("password_reset_done")
        else:
            messages.error(request, "No account found with this email.")
            return redirect("password_reset")

    return render(request, "user/custom_password_reset.html", {"form": form})


    
def custom_password_reset_sent(request):
    return render(request, "user/custom_password_reset_sent.html")


def custom_password_reset_confirm(request, uidb64, token):
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = User.objects.get(pk=uid)
    except (User.DoesNotExist, ValueError):
        user = None

    if user and default_token_generator.check_token(user, token):
        if request.method == "POST":
            form = SetPasswordForm(user, request.POST)
            if form.is_valid():
                form.save()

                messages.success(request, "Your password has been reset successfully. Please log in with your new password.")
                return redirect("login")  
            else:
                print(" Form errors:", form.errors)  
        else:
            form = SetPasswordForm(user)
        return render(request, "user/custom_password_reset_confirm.html", {"form": form})
    else:
        messages.error(request, "The password reset link is invalid.")
        return redirect("password_reset")






@login_required
def custom_password_reset_complete(request):
    if request.method == 'POST':
        new_password = request.POST['new_password']
        user = request.user
        user.set_password(new_password)
        user.save()
        update_session_auth_hash(request, user)
        return render(request, "user/custom_password_reset_complete.html", {'message': 'Password updated successfully.'})
    return render(request, "user/custom_password_reset_complete.html")

def reset_password(request, uidb64, token):
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user and default_token_generator.check_token(user, token):
        if request.method == "POST":
            new_password = request.POST["password"]
            user.set_password(new_password)
            user.save()
            user.refresh_from_db()
            logout(request)
            return redirect("index")
        return render(request, "user/reset_password.html", {"valid_link": True})
    else:
        return render(request, "user/reset_password.html", {"valid_link": False})
#end forgot password










@login_required
def wallet_view(request):
    try:
        wallet = Wallet.objects.get(user=request.user)
    except Wallet.DoesNotExist:
        wallet = Wallet.objects.create(user=request.user)


    transactions = Transaction.objects.filter(wallet=wallet).order_by('-timestamp')
    return render(request, 'user/wallet.html', {'wallet': wallet, 'transactions': transactions})






#new views.py

logger = logging.getLogger(__name__)


@login_required
def cancel_order(request, order_id):
    if request.method == "POST":
        order = get_object_or_404(Order, id=order_id)

        # Debugging: Print order details
        print(f"Order ID: {order.id}, Payment Method: {order.payment_method}, Razorpay Payment ID: {order.razorpay_payment_id}")

        # Normalize payment method for comparison
        payment_method = order.payment_method.lower().replace("_", " ").strip()

        # Check if the order is either a prepaid Razorpay order or a COD order
        if not order.razorpay_payment_id and payment_method not in ["cod", "cash on delivery"]:
            return JsonResponse({"error": "This order was not paid Razorpay or is not a Cash on Delivery order."}, status=400)

        try:
            with transaction.atomic():  # Ensures database consistency
                # Update order status to "Cancelled"
                order.status = "Cancelled"
                order.save()

                # Process refund for Razorpay orders only
                if order.razorpay_payment_id:
                    wallet, created = Wallet.objects.get_or_create(user=order.user)
                    refund_amount = order.total_price  
                    wallet.balance += refund_amount
                    wallet.save()

                    # Log transaction
                    Transaction.objects.create(
                        wallet=wallet,
                        amount=refund_amount,
                        transaction_type="credit"
                    )

                    return JsonResponse({
                        "success": True,
                        "order_id": order.id,
                        "new_status": order.status,
                        "wallet_balance": wallet.balance
                    })
                
                # COD Order Cancellation - No refund, just status update
                return JsonResponse({
                    "success": True,
                    "order_id": order.id,
                    "new_status": order.status,
                    "message": "COD order cancelled successfully"
                })

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Invalid request"}, status=400)


def product_offers(request):
    offers = ProductOffer.objects.filter(start_date__lte=now, end_date__gte=now)
    return render(request, 'offers/product_offers.html', {'offers': offers})

def category_offers(request):
    offers = CategoryOffer.objects.filter(start_date__lte=now, end_date__gte=now)
    return render(request, 'offers/category_offers.html', {'offers': offers})

def referral_offers(request):
    offers = ReferralOffer.objects.filter(status='active')
    return render(request, 'offers/referral_offers.html', {'offers': offers})

def available_offers(request):
    current_time = now()

    product_offers = ProductOffer.objects.filter(
        start_date__lte=current_time,
        end_date__gte=current_time
    )

    category_offers = CategoryOffer.objects.filter(
        start_date__lte=current_time,
        end_date__gte=current_time
    )

    context = {
        'product_offers': product_offers,
        'category_offers': category_offers,
    }
    return render(request, 'user/available_offers.html', context)


def create_order(request):
    if request.method == "POST":
        amount = 50000  
        currency = 'INR'
        receipt = 'order_rcptid_11'  

        try:
            payment = client.order.create({
                'amount': amount,
                'currency': currency,
                'receipt': receipt,
                'payment_capture': '1'
            })

            # Get user and address information
            user = request.user
            address = user.address_set.first()  
            items = user.cart_items.all()  
            total_price = sum(item.product.price for item in items)  # Calculate total price

            # Save order details to database
            order = Order(
                user=user,
                address=address,
                total_price=total_price,
                payment_method='RAZORPAY',
                status='Pending',
                razorpay_order_id=payment['id'],
                payment_status=payment['status']
            )
            order.save()
            order.items.set(items)  # items with the order

            return render(request, 'user/payment.html', {'payment': payment})
        except razorpay.errors.RazorpayError as e:
            print(f"Razorpay Error: {str(e)}")
            return render(request, 'user/error.html', {'error': str(e)})

    return





    


@csrf_exempt
def verify_payment(request):
    if request.method == "POST":
        data = request.POST
        try:
            razorpay.Client.utility.verify_payment_signature(data)
            # Update order status to 'paid'
            return JsonResponse({'status': 'success'})
        except:
            # Handle the error
            return JsonResponse({'status': 'failure'})
        

def order_success(request):
    return render(request, 'user/order_success.html')





WKHTMLTOPDF_PATH = r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"

# Ensure the executable exists
if not os.path.exists(WKHTMLTOPDF_PATH):
    raise FileNotFoundError(f"wkhtmltopdf not found at: {WKHTMLTOPDF_PATH}")

# Configure pdfkit
config = pdfkit.configuration(wkhtmltopdf=WKHTMLTOPDF_PATH)

def generate_invoice_data(order_id):
    try:
        order = Order.objects.get(id=order_id)
    except Order.DoesNotExist:
        return None
    
    india_tz = pytz.timezone("Asia/Kolkata")
    created_at_ist = localtime(order.created_at, india_tz)
    delivery_date_ist = localtime(order.delivery_date, india_tz)
    
    

    if order.address:
       
        shipping_address = f"{order.address.first_name} {order.address.last_name}, " \
                           f"{order.address.house_no}, {order.address.street_address}, " \
                           f"{order.address.city}, {order.address.region}, {order.address.postcode}"
    elif order.first_name and order.last_name:
      
        shipping_address = f"{order.first_name} {order.last_name}, " \
                           f"{order.house_no}, {order.street_address}, " \
                           f"{order.postcode}"
    else:
       
        shipping_address = "Address not available."

    order_items = order.order_items.all()
    grand_subtotal = 0
    for item in order_items:
        item.subtotal = item.quantity * item.product.price
        grand_subtotal += item.subtotal


    invoice_data = {
        'order_id': order.id,
        'customer_name': order.user.username,
        'payment_method': order.payment_method,
        'total_price': order.total_price,
        'shipping_address': shipping_address,
        'delivery_date': order.delivery_date,
        'created_at': order.created_at,
        'created_at': created_at_ist,              # ✅ Localized datetime
        'delivery_date': delivery_date_ist,
        'order_items': order_items,  
        'grand_subtotal': grand_subtotal, 
        'coupon': order.coupon,  
        'discount_amount': order.discount_amount,
         "delivery_charge": order.delivery_charge,
         

        
    }

    return invoice_data

def download_invoice(request, order_id):
    invoice_data = generate_invoice_data(order_id)
    if not invoice_data:
        return HttpResponse("Order not found", status=404)

    html = render_to_string('user/invoice_template.html', {'invoice_data': invoice_data})
    
    # Convert HTML to PDF (Fix: Pass `configuration=config`)
    pdf = pdfkit.from_string(html, False, configuration=config)

    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="invoice_{order_id}.pdf"'
    return response



def render_to_pdf(template_src, context_dict={}):
    template = get_template(template_src)
    html = template.render(context_dict)
    response = HttpResponse(content_type='application/pdf')
    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse('We had some errors <pre>' + html + '</pre>')
    return response









def calculate_delivery_charge(address):
    fixed_charge = 50  
    postal_code_based_charges = {
        '678621': 50,
        '682006': 60,
    }

   
    delivery_charge = postal_code_based_charges.get(address.postcode, fixed_charge)

    return delivery_charge



def payment_failed(request):
    if request.method == 'POST':
        order_id = request.POST.get('order_id')
        order = get_object_or_404(Order, id=order_id)
        order.payment_status = 'Payment Pending'
        order.save()
        return JsonResponse({'message': 'Order payment status updated to Payment Pending.'})
    else:
        return JsonResponse({'message': 'Invalid request method.'}, status=400)
    








@csrf_exempt
@login_required
def payment_callback(request):
    if request.method == "POST":
        payment_data = request.POST
        try:
            client = razorpay.Client(auth=("rzp_test_MAimzLa32DUYt6", "qbDDZBXaEQPNG72T9ZPVPytC"))

            # Verify payment signature
            params_dict = {
                'razorpay_order_id': payment_data['razorpay_order_id'],
                'razorpay_payment_id': payment_data['razorpay_payment_id'],
                'razorpay_signature': payment_data['razorpay_signature']
            }
            client.utility.verify_payment_signature(params_dict)

            # Update order status and payment details
            order = Order.objects.get(razorpay_order_id=payment_data['razorpay_order_id'])
            order.razorpay_payment_id = payment_data['razorpay_payment_id']
            order.payment_status = 'Paid'
            order.status = 'Processing'
            order.save()

            messages.success(request, "Payment successful!")
            return redirect('order_confirmation', order_id=order.id)

        except (razorpay.errors.SignatureVerificationError, Order.DoesNotExist) as e:
            messages.error(request, "Payment verification failed or order not found.")
            return redirect('checkoutpage')

    return redirect('checkoutpage')



def payment_cancel(request):
    return render(request, 'user/payment_cancel.html')


def payment_failure(request):
    return render(request, 'user/payment_failure.html')


@login_required
def retry_payment(request, order_id):
    order = get_object_or_404(Order, id=order_id)

    # Use the original order items to calculate the total cost
    order_items = OrderItem.objects.filter(order=order)
    if not order_items.exists():
        messages.error(request, "No items found for this order.")
        return redirect('my_orders')

    # Calculate total cost based on the original order items
    total_cost = sum(item.quantity * item.price for item in order_items)
    discount_amount = order.discount_amount or 0
    final_price = total_cost - discount_amount

    # Convert final price to paise for razorpay
    amount_in_paise = int(float(final_price) * 100)

    try:
        
        client = razorpay.Client(auth=("rzp_test_MAimzLa32DUYt6", "qbDDZBXaEQPNG72T9ZPVPytC"))

        
        order_data = {
            "amount": amount_in_paise,
            "currency": "INR",
            "payment_capture": "1", 
        }
        razorpay_order = client.order.create(order_data)
        logger.debug(f"Order created successfully for retry: {razorpay_order}")

        # Update Order with new razorpay order ID
        order.razorpay_order_id = razorpay_order["id"]
        order.payment_status = 'Pending'
        order.save()

        context = {
            "amount": amount_in_paise,
            "order_id": razorpay_order["id"],
            "razorpay_key": 'rzp_test_MAimzLa32DUYt6',
            "callback_url": request.build_absolute_uri('/payment/payment-status/'),
        }
        return render(request, "user/payment.html", context)

    except razorpay.errors.BadRequestError as bad_request_error:
        logger.error(f"Bad request error (possibly authentication): {bad_request_error}")
        messages.error(request, "Payment initiation failed: " + str(bad_request_error))
        return redirect('my_orders')
    except AttributeError as attr_error:
        logger.error(f"AttributeError in Razorpay client: {attr_error}")
        messages.error(request, "Razorpay configuration error: " + str(attr_error))
        return redirect('my_orders')
    except Exception as e:
        logger.error(f"Error occurred during payment retry: {e}")
        messages.error(request, "An error occurred during payment retry: " + str(e))
        return redirect('my_orders')



def view_order_details(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    return render(request, 'user/order_details.html', {'order': order})

def track_order(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    return render(request, 'user/track_order.html', {'order': order})




# class CustomPasswordResetConfirmView(PasswordResetConfirmView):
#     template_name = 'reset_password1.html'
#     success_url = reverse_lazy('login')  # Redirect to login 

#     def form_valid(self, form):
#         messages.success(self.request, 'Your password has been reset successfully. Please log in.')
#         return super().form_valid(form)




@login_required
def change_password(request):
    if request.method == 'POST':
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')

        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
        elif len(password) < 8:
            messages.error(request, "Password must be at least 8 characters long.")
        else:
            user = request.user
            user.set_password(password)
            user.save()
            update_session_auth_hash(request, user)  # Keep user logged in
            messages.success(request, "Your password has been updated successfully.")
            return redirect('user_profile')
    
    return redirect('user_profile')




