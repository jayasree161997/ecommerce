import logging
import razorpay 
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from products.models import Order,OrderItem,Cart,CartItem, Coupon
from home.models import Address
from django.contrib import messages
import paypalrestsdk
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
import decimal
from decimal import Decimal,InvalidOperation,ROUND_HALF_UP
from datetime import datetime, timedelta
from django.utils.timezone import now
from datetime import timedelta, date
import os
from django.db import transaction



RAZORPAY_KEY_ID = "rzp_test_MAimzLa32DUYt6"
RAZORPAY_SECRET = "qbDDZBXaEQPNG72T9ZPVPytC"


razorpay_client = razorpay.Client(auth=("rzp_test_MAimzLa32DUYt6", "qbDDZBXaEQPNG72T9ZPVPytC"))




logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

@login_required
def initiate_payment(request):
    if request.method == "GET":
        try:
            # 1. Get Cart & Items
            cart, created = Cart.objects.get_or_create(user=request.user)
            cart_items = CartItem.objects.filter(cart=cart)

            if not cart_items.exists():
                messages.error(request, "Your cart is empty.")
                return redirect('cart_detail')

            valid_cart_items = []

            # 2. Validate all items
            for item in cart_items:
                product = item.product
                product.refresh_from_db()  # Get latest stock

                if not product.is_active or not product.category.is_active or product.stock == 0:
                    messages.error(request, f"{product.name} is currently unavailable.")
                    return redirect('cart_detail')
                elif item.quantity > product.stock:
                    messages.error(request, f"Only {product.stock} units available for {product.name}.")
                    return redirect('cart_detail')
                else:
                    valid_cart_items.append(item)

            if not valid_cart_items:
                messages.error(request, "All items in your cart are unavailable.")
                return redirect('cart_detail')

            # 3. Calculate Price
            total_cost = sum(Decimal(item.quantity or 0) * Decimal(item.price or 0) for item in valid_cart_items)
            discount_amount = Decimal(str(cart.discount_amount or "0.00"))

            coupon_instance = None
            if cart.coupon_applied:
                try:
                    coupon_instance = Coupon.objects.get(code=cart.coupon_code)
                except Coupon.DoesNotExist:
                    coupon_instance = None

            delivery_charge = Decimal("60.00")
            final_price = max(total_cost - discount_amount + delivery_charge, Decimal("0.00")).quantize(Decimal("1.00"))

            if final_price <= 0:
                return JsonResponse({"error": "Final amount must be greater than zero."}, status=400)

            amount_in_paise = int((final_price * 100).quantize(Decimal("1")))

            # 4. Razorpay Order Create
            client = razorpay.Client(auth=("rzp_test_MAimzLa32DUYt6", "qbDDZBXaEQPNG72T9ZPVPytC"))
            order_data = {"amount": amount_in_paise, "currency": "INR", "payment_capture": "1"}
            razorpay_order = client.order.create(order_data)

            # 5. Get User Address
            user_address = Address.objects.filter(user=request.user).first()
            if not user_address:
                messages.error(request, "No address found.")
                return redirect('cart_detail')

            # 6. Handle DB with transaction (rollback on failure)
            with transaction.atomic():
                # Create Order
                django_order = Order.objects.create(
                    user=request.user,
                    address=user_address,
                    first_name=user_address.first_name,
                    last_name=user_address.last_name,
                    postcode=user_address.postcode,
                    mobile=user_address.mobile,
                    house_no=user_address.house_no,
                    street_address=user_address.street_address,
                    total_price=final_price,
                    payment_method='RAZORPAY',
                    razorpay_order_id=razorpay_order["id"],
                    payment_status='Pending',
                    status='Pending',
                    coupon=coupon_instance,
                    coupon_code=coupon_instance.code if coupon_instance else None,
                    discount_amount=discount_amount,
                    delivery_charge=delivery_charge,
                )

                # Create Order Items & Update Stock
                for cart_item in valid_cart_items:
                    product = cart_item.product
                    product.refresh_from_db()
                    if cart_item.quantity > product.stock:
                        raise Exception(f"{product.name} stock changed. Only {product.stock} left.")

                    product.stock -= cart_item.quantity
                    product.save()

                    OrderItem.objects.create(
                        order=django_order,
                        product=product,
                        quantity=cart_item.quantity,
                        price=cart_item.price
                    )

                # Clear Cart
                CartItem.objects.filter(cart=cart).delete()
                cart.coupon_code = ''
                cart.discount_amount = 0
                cart.coupon_applied = False
                cart.save()
                request.session.pop('coupon_id', None)
                request.session.pop('applied_coupon', None)

            # 7. Render Razorpay Page
            context = {
                "amount": amount_in_paise,
                "order_id": razorpay_order["id"],
                "razorpay_key": 'rzp_test_MAimzLa32DUYt6',
                "callback_url": request.build_absolute_uri('/payment/payment-status/'),
            }
            return render(request, "user/payment.html", context)

        # Error Handlers
        except InvalidOperation:
            return JsonResponse({"error": "Invalid decimal operation."}, status=400)
        except razorpay.errors.BadRequestError as bad_request_error:
            return JsonResponse({"error": f"Payment initiation failed: {bad_request_error}"}, status=400)
        except Exception as e:
            messages.error(request, str(e))
            return redirect('cart_detail')

    return redirect('cart_detail')



def set_delivery_date(order):
    """Set the delivery date dynamically based on order status."""
    
    if order.status == "Shipped" and not order.delivery_date:
        order.delivery_date = now() + timedelta(days=7)  
        order.save(update_fields=["delivery_date"])

    elif order.payment_method == "cash_on_delivery" and not order.delivery_date:
        order.delivery_date = now() + timedelta(days=10) 
        order.save(update_fields=["delivery_date"])

logger = logging.getLogger(__name__)






@csrf_exempt
@login_required
def payment_success(request):
    razorpay_payment_id = request.GET.get("razorpay_payment_id")
    razorpay_order_id = request.GET.get("razorpay_order_id")

    logger.info(f"Payment Success Called - Order ID: {razorpay_order_id}, Payment ID: {razorpay_payment_id}")

    if not (razorpay_order_id and razorpay_payment_id):
        logger.error("Missing Razorpay payment/order ID.")
        return render(request, "user/payment_success.html", {"error": "Missing payment details."})

    try:
        # ✅ Get the matching order
        order = get_object_or_404(Order, razorpay_order_id=razorpay_order_id)

        # ✅ Update payment status (do NOT reduce stock again)
        order.razorpay_payment_id = razorpay_payment_id
        order.payment_status = "Success"
        order.status = "Confirmed"
        order.delivery_date = now().date() + timedelta(days=7)
        order.save()

        # ✅ Clean up cart (if still exists)
        try:
            cart = Cart.objects.get(user=request.user)
            cart.cart_items.all().delete()
            cart.delete()
        except Cart.DoesNotExist:
            logger.info("Cart already deleted after payment.")

        # ✅ Clear coupon sessions
        request.session.pop('coupon_id', None)
        request.session.pop('applied_coupon', None)

        # ✅ Prepare order context
        order_items = order.order_items.all()
        context = {
            "order": order,
            "transaction_id": razorpay_payment_id,
            "total_amount": order.total_price,
            "payment_status": order.payment_status,
            "payment_method": "Razorpay",
            "payment_state": "Success",
            "shipping_address": order.address,
            "purchased_products": order_items,
            "coupon": order.coupon_code,
            "delivery_charge": order.delivery_charge,
        }

        return render(request, "user/payment_success.html", context)

    except Exception as e:
        logger.error(f"Error in payment success view: {e}")
        return render(request, "user/payment_success.html", {
            "error": "Something went wrong while confirming your payment. Please contact support.",
            "order": None
        })


#razorpay failure 
@login_required
def payment_failure(request):
    return render(request, "user/payment-failed.html", {"error": "Payment failed. Please try again "})








    



    




