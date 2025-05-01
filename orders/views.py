from django.shortcuts import render, get_object_or_404, redirect
from cart.models import Cart, CartItem, Wallet, WalletTransaction
from .models import ShippingAddress, Order, OrderItem, Address, Coupon, CouponUsage
from .forms import AddressForm, CouponForm
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator
from django.db import transaction
from django.conf import settings
from django.contrib import messages
from django.urls import reverse
from datetime import date
from decimal import Decimal
from django.db.models import F
import razorpay
from razorpay.errors import SignatureVerificationError
import json
from django.utils.timezone import now
from django.db.models import Count,Q
from django.db.models.expressions import RawSQL

@login_required
def checkout(request):
    cart = get_object_or_404(Cart, user=request.user)
    cart_items = CartItem.objects.filter(cart=cart).select_related('product_variant__product')
    addresses = Address.objects.filter(user=request.user)

    # Validate addresses and cart
    if not addresses.exists():
        messages.error(request, "Please add an address before proceeding.")
        return redirect('add_address')

    if not cart_items.exists():
        messages.error(request, "Your cart is empty.")
        return redirect('cart_page')

    # Calculate totals
    total_price = sum(Decimal(item.product_variant.product.price) * item.quantity for item in cart_items)
    product_discount = sum(
        (Decimal(item.product_variant.product.price) -
         (Decimal(item.product_variant.product.offer_price) if item.product_variant.product.offer_price
          else Decimal(item.product_variant.product.price))) * item.quantity
        for item in cart_items
    )
    subtotal_after_discount = total_price - product_discount

    # Retrieve or initialize checkout data in session
    checkout_data = request.session.get('checkout_data', {})
    
    # Determine default address
    has_default_field = 'is_default' in [f.name for f in Address._meta.fields]
    if has_default_field:
        default_address = addresses.filter(is_default=True).first() or addresses.first()
    else:
        default_address = addresses.first()

    if default_address and 'address_id' not in checkout_data:
        checkout_data['address_id'] = default_address.id

    # Get coupon details from session
    coupon_code = request.session.get('coupon_code')
    try:
        coupon_discount = Decimal(request.session.get('coupon_discount', '0.00'))
    except (TypeError, ValueError):
        coupon_discount = Decimal('0.00')
    
    coupon_discount = min(coupon_discount, subtotal_after_discount)

    # Calculate shipping and final price
    shipping_cost = Decimal('0.00') if subtotal_after_discount - coupon_discount > Decimal('1000') else Decimal('50.00')
    final_price = max(subtotal_after_discount - coupon_discount + shipping_cost, Decimal('0.00'))

    # Fetch available coupons
    available_coupons = Coupon.objects.filter(
        active=True,
        start_date__lte=now(),
        end_date__gte=now(),
        min_order_value__lte=subtotal_after_discount
    ).annotate(
        usage_count=Count('couponusage', filter=Q(couponusage__user=request.user))
    ).filter(
        usage_count__lt=F('usage_limit')
    )

    # Update checkout data with calculated final_price
    checkout_data['final_price'] = str(final_price)
    request.session['checkout_data'] = checkout_data
    request.session.modified = True

    if request.method == "POST":
        action = request.POST.get('action')
        
        # Handle coupon actions
        if action in ['apply', 'remove']:
            if action == 'apply':
                coupon_code_input = request.POST.get('coupon_code', '').strip()
                if not coupon_code_input:
                    messages.error(request, "Please enter a coupon code.")
                    return redirect('checkout')

                if coupon_code_input == coupon_code:
                    messages.info(request, "This coupon is already applied.")
                    return redirect('checkout')

                try:
                    coupon = Coupon.objects.get(code=coupon_code_input, active=True)
                    if not coupon.is_valid():
                        if coupon.end_date < now():
                            messages.error(request, "This coupon has expired.")
                        else:
                            messages.error(request, "This coupon is not valid.")
                    elif CouponUsage.objects.filter(user=request.user, coupon=coupon).count() >= coupon.usage_limit:
                        messages.error(request, "Coupon usage limit reached.")
                    elif subtotal_after_discount < coupon.min_order_value:
                        messages.error(request, f"Minimum order of ₹{coupon.min_order_value} required.")
                    else:
                        discount = (subtotal_after_discount * coupon.discount / 100) if coupon.is_percentage else coupon.discount
                        if coupon.is_percentage and coupon.max_discount:
                            discount = min(discount, coupon.max_discount)
                        request.session['coupon_code'] = coupon.code
                        request.session['coupon_discount'] = str(discount)
                        coupon_code = coupon.code
                        coupon_discount = Decimal(discount)
                        messages.success(request, f"Coupon {coupon_code} applied successfully!")
                except Coupon.DoesNotExist:
                    messages.error(request, "Invalid coupon code.")
                    coupon_code = None
                    coupon_discount = Decimal('0.00')
                    request.session.pop('coupon_code', None)
                    request.session.pop('coupon_discount', None)

            elif action == 'remove':
                if coupon_code:
                    messages.success(request, f"Coupon {coupon_code} removed successfully.")
                    coupon_code = None
                    coupon_discount = Decimal('0.00')
                    request.session.pop('coupon_code', None)
                    request.session.pop('coupon_discount', None)
                else:
                    messages.info(request, "No coupon is currently applied.")

            # Recalculate prices after coupon action
            coupon_discount = min(coupon_discount, subtotal_after_discount)
            shipping_cost = Decimal('0.00') if subtotal_after_discount - coupon_discount > Decimal('1000') else Decimal('50.00')
            final_price = max(subtotal_after_discount - coupon_discount + shipping_cost, Decimal('0.00'))
            
            # Update session data
            checkout_data.update({
                'final_price': str(final_price),
                'coupon_code': coupon_code,
                'coupon_discount': str(coupon_discount),
                'shipping_cost': str(shipping_cost)
            })
            request.session['checkout_data'] = checkout_data
            request.session.modified = True
            return redirect('checkout')

        # Handle order submission
        elif 'proceed' in request.POST:
            address_id = request.POST.get('address', checkout_data.get('address_id'))
            try:
                address = Address.objects.get(id=address_id, user=request.user)
            except (Address.DoesNotExist, ValueError):
                messages.error(request, "Invalid address selected.")
                return redirect('checkout')

            payment_method = request.POST.get('payment_method')
            if not payment_method:
                messages.error(request, "Please select a payment method.")
                return redirect('checkout')

            # Update checkout data with all necessary details
            checkout_data.update({
                'address_id': address.id,
                'payment_method': payment_method,
                'final_price': str(final_price),
                'coupon_code': coupon_code,
                'coupon_discount': str(coupon_discount),
                'total_price': str(total_price),
                'product_discount': str(product_discount),
                'subtotal_after_discount': str(subtotal_after_discount),
                'shipping_cost': str(shipping_cost)
            })
            request.session['checkout_data'] = checkout_data
            request.session.modified = True
            return redirect('payment_page')

    context = {
        'cart_items': cart_items,
        'addresses': addresses,
        'default_address': default_address,
        'total_price': total_price,
        'product_discount': product_discount,
        'subtotal_after_discount': subtotal_after_discount,
        'coupon_discount': coupon_discount,
        'shipping_cost': shipping_cost,
        'final_price': final_price,
        'applied_coupon': coupon_code,
        'payment_method': checkout_data.get('payment_method', 'cod'),
        'available_coupons': available_coupons,
    }

    return render(request, 'checkout.html', context)


razorpay_client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

@login_required
def payment_page(request):
    checkout_data = request.session.get('checkout_data', {})

    if not checkout_data or 'final_price' not in checkout_data:
        messages.error(request, "Please complete checkout first")
        return redirect('checkout')
    
    if 'address_id' not in checkout_data:
        messages.error(request, "Please select an address")
        return redirect('checkout')

    cart_items = CartItem.objects.filter(cart__user=request.user).select_related('product_variant__product')

    if not cart_items.exists():
        messages.error(request, "Your cart is empty")
        return redirect('cart_page')

    total_price = sum(
        Decimal(item.product_variant.product.price) * item.quantity for item in cart_items
    )

    product_discount = sum(
        (Decimal(item.product_variant.product.price) -
         (Decimal(item.product_variant.product.offer_price) if item.product_variant.product.offer_price
          else Decimal(item.product_variant.product.price))) * item.quantity
        for item in cart_items
    )

    subtotal_after_discount = total_price - product_discount

    # Ensure coupon discount is properly converted to Decimal
    try:
        coupon_discount = Decimal(checkout_data.get('coupon_discount', '0.00'))
    except Exception:
        coupon_discount = Decimal('0.00')

    shipping_cost = Decimal('0.00') if subtotal_after_discount - coupon_discount > Decimal('1000') else Decimal('50.00')
    final_price = max(subtotal_after_discount - coupon_discount + shipping_cost, Decimal('0.00'))

    # Update checkout data with corrected final price
    checkout_data['final_price'] = str(final_price)
    request.session['checkout_data'] = checkout_data
    request.session.modified = True

    # Wallet balance check
    try:
        wallet = Wallet.objects.get(user=request.user)
        wallet_balance = wallet.balance
        has_sufficient_wallet_balance = wallet_balance >= final_price
    except Wallet.DoesNotExist:
        wallet_balance = Decimal('0.00')
        has_sufficient_wallet_balance = False

    context = {
        'cart_items': cart_items,
        'total_price': total_price,
        'product_discount': product_discount,
        'subtotal_after_discount': subtotal_after_discount,
        'coupon_discount': coupon_discount,
        'shipping_cost': shipping_cost,
        'final_price': final_price,
        'payment_method': checkout_data.get('payment_method', ''),
        'applied_coupon': checkout_data.get('coupon_code'),
        'wallet_balance': wallet_balance,
        'has_sufficient_wallet_balance': has_sufficient_wallet_balance,
    }

    return render(request, 'payment.html', context)

@login_required
def process_payment(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=400)

    try:
        data = json.loads(request.body)
        payment_method = data.get("payment_method")
        # Optional order_id for payment retry (only applicable for razorpay)
        order_id = data.get("order_id")

        if payment_method not in ["cod", "razorpay", "wallet"]:
            return JsonResponse({"error": f"Invalid payment method: {payment_method}"}, status=400)

        # COD and Wallet payments should never be retried – if an order_id is provided, raise an error.
        if payment_method in ["cod", "wallet"] and order_id:
            return JsonResponse({"error": f"{payment_method.capitalize()} payments cannot be retried"}, status=400)

        # For a Razorpay payment retry, fetch the existing order and recreate the Razorpay order.
        if payment_method == "razorpay" and order_id:
            order = Order.objects.filter(id=order_id, user=request.user, payment_method="Online").first()
            if not order:
                return JsonResponse({"error": "Invalid order for payment retry"}, status=400)
            # Create a new Razorpay order using the total_amount from the existing order.
            try:
                razorpay_order = razorpay_client.order.create({
                    'amount': int(order.total_amount * 100),
                    'currency': 'INR',
                    'receipt': order.order_id,
                    'payment_capture': '1'
                })
            except razorpay.errors.BadRequestError as e:
                return JsonResponse({"error": f"Razorpay error: {str(e)}"}, status=400)
            except Exception as e:
                return JsonResponse({"error": "Payment authentication failed"}, status=500)
            order.razorpay_order_id = razorpay_order['id']
            order.save(update_fields=['razorpay_order_id'])
            return JsonResponse({
                "success": True,
                "key": settings.RAZORPAY_KEY_ID,
                "amount": int(order.total_amount * 100),
                "currency": "INR",
                "razorpay_order_id": razorpay_order['id']
            })

        # Normal flow (new order creation)
        checkout_data = request.session.get('checkout_data', {})
        address_id = checkout_data.get('address_id')
        if not address_id:
            return JsonResponse({"error": "Address not selected"}, status=400)

        selected_address = Address.objects.filter(id=address_id, user=request.user).first()
        if not selected_address:
            return JsonResponse({"error": "Invalid address"}, status=400)

        # Create shipping address
        shipping_address = ShippingAddress.objects.create(
            full_name=selected_address.full_name,
            phone=selected_address.phone,
            address=selected_address.address,
            city=selected_address.city,
            state=selected_address.state,
            pin_code=selected_address.pin_code
        )

        cart_items = CartItem.objects.filter(cart__user=request.user).select_related('product_variant__product')
        if not cart_items.exists():
            return JsonResponse({"error": "Cart is empty"}, status=400)

        for item in cart_items:
            if item.product_variant.stock < item.quantity:
                return JsonResponse({"error": f"Insufficient stock for {item.product_variant.product.name}"}, status=400)

        total_price = sum(Decimal(item.product_variant.product.price) * item.quantity for item in cart_items)
        product_discount = sum(
            (Decimal(item.product_variant.product.price) -
             (Decimal(item.product_variant.product.offer_price) if item.product_variant.product.offer_price 
              else Decimal(item.product_variant.product.price))) * item.quantity
            for item in cart_items
        )
        subtotal_after_discount = total_price - product_discount
        coupon_discount = Decimal(checkout_data.get('coupon_discount', '0.00'))
        shipping_cost = Decimal('0.00') if subtotal_after_discount - coupon_discount > Decimal('1000') else Decimal('50.00')
        final_price = max(subtotal_after_discount - coupon_discount + shipping_cost, Decimal('0.00'))

        coupon = None
        coupon_code = checkout_data.get('coupon_code')
        if coupon_code:
            try:
                coupon = Coupon.objects.get(code=coupon_code)
            except Coupon.DoesNotExist:
                coupon = None
                coupon_discount = Decimal('0.00')

        if payment_method == "cod":
            with transaction.atomic():
                order = Order.objects.create(
                    user=request.user,
                    address=shipping_address,
                    payment_method="COD",
                    subtotal=total_price,
                    product_discount=product_discount,
                    coupon_discount=coupon_discount,
                    shipping_cost=shipping_cost,
                    total_amount=final_price,
                    coupon=coupon
                )
                for item in cart_items:
                    product = item.product_variant.product
                    offer_price = product.offer_price if product.offer_price else None
                    discount = product.price - offer_price if offer_price else Decimal('0.00')
                    final_price_item = offer_price if offer_price else product.price
                    OrderItem.objects.create(
                        order=order,
                        product_variant=item.product_variant,
                        quantity=item.quantity,
                        price=product.price,
                        offer_price=offer_price,
                        discount=discount,
                        final_price=final_price_item * item.quantity
                    )
                    item.product_variant.stock -= item.quantity
                    item.product_variant.save()
                cart_items.delete()
                request.session.pop('checkout_data', None)
                request.session.pop('coupon_code', None)
                request.session.pop('coupon_discount', None)
                request.session.modified = True
                if coupon:
                    CouponUsage.objects.create(user=request.user, coupon=coupon)
                return JsonResponse({"success": True, "redirect_url": reverse('order_success', kwargs={'order_id': order.id})})

        elif payment_method == "wallet":
            with transaction.atomic():
                try:
                    wallet = Wallet.objects.get(user=request.user)
                except Wallet.DoesNotExist:
                    return JsonResponse({"error": "Wallet not found"}, status=400)

                if wallet.balance < final_price:
                    return JsonResponse({"error": "Insufficient wallet balance"}, status=400)

                order = Order.objects.create(
                    user=request.user,
                    address=shipping_address,
                    payment_method="Wallet",
                    subtotal=total_price,
                    product_discount=product_discount,
                    coupon_discount=coupon_discount,
                    shipping_cost=shipping_cost,
                    total_amount=final_price,
                    coupon=coupon
                )
                for item in cart_items:
                    product = item.product_variant.product
                    offer_price = product.offer_price if product.offer_price else None
                    discount = product.price - offer_price if offer_price else Decimal('0.00')
                    final_price_item = offer_price if offer_price else product.price
                    OrderItem.objects.create(
                        order=order,
                        product_variant=item.product_variant,
                        quantity=item.quantity,
                        price=product.price,
                        offer_price=offer_price,
                        discount=discount,
                        final_price=final_price_item * item.quantity
                    )
                    item.product_variant.stock -= item.quantity
                    item.product_variant.save()

                # Deduct wallet balance and create transaction
                wallet.deduct_balance(final_price)
                WalletTransaction.objects.create(
                    wallet=wallet,
                    amount=final_price,
                    transaction_type='Debit',
                    order=order,
                    description=f"Payment for order {order.order_id}"
                )

                cart_items.delete()
                request.session.pop('checkout_data', None)
                request.session.pop('coupon_code', None)
                request.session.pop('coupon_discount', None)
                request.session.modified = True
                if coupon:
                    CouponUsage.objects.create(user=request.user, coupon=coupon)
                return JsonResponse({"success": True, "redirect_url": reverse('order_success', kwargs={'order_id': order.id})})

        elif payment_method == "razorpay":
            with transaction.atomic():
                order = Order.objects.create(
                    user=request.user,
                    address=shipping_address,
                    payment_method="Online",
                    subtotal=total_price,
                    product_discount=product_discount,
                    coupon_discount=coupon_discount,
                    shipping_cost=shipping_cost,
                    total_amount=final_price,
                    coupon=coupon
                )
                for item in cart_items:
                    product = item.product_variant.product
                    offer_price = product.offer_price if product.offer_price else None
                    discount = product.price - offer_price if offer_price else Decimal('0.00')
                    final_price_item = offer_price if offer_price else product.price
                    OrderItem.objects.create(
                        order=order,
                        product_variant=item.product_variant,
                        quantity=item.quantity,
                        price=product.price,
                        offer_price=offer_price,
                        discount=discount,
                        final_price=final_price_item * item.quantity
                    )
                request.session.pop('checkout_data', None)
                request.session.pop('coupon_code', None)
                request.session.pop('coupon_discount', None)
                request.session.modified = True

                try:
                    razorpay_order = razorpay_client.order.create({
                        'amount': int(final_price * 100),
                        'currency': 'INR',
                        'receipt': order.order_id,
                        'payment_capture': '1'
                    })
                except razorpay.errors.BadRequestError as e:
                    return JsonResponse({"error": f"Razorpay error: {str(e)}"}, status=400)
                except Exception as e:
                    return JsonResponse({"error": "Payment authentication failed"}, status=500)

                order.razorpay_order_id = razorpay_order['id']
                order.save(update_fields=['razorpay_order_id'])

                return JsonResponse({
                    "success": True,
                    "key": settings.RAZORPAY_KEY_ID,
                    "amount": int(final_price * 100),
                    "currency": "INR",
                    "razorpay_order_id": razorpay_order['id']
                })

    except json.JSONDecodeError as e:
        return JsonResponse({"error": "Invalid request data"}, status=400)
    except Exception as e:
        return JsonResponse({"error": f"Server error: {str(e)}"}, status=500)




@csrf_exempt
def verify_payment(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=400)

    try:
        data = json.loads(request.body)
        razorpay_order_id = data.get("razorpay_order_id")
        razorpay_payment_id = data.get("razorpay_payment_id")
        razorpay_signature = data.get("razorpay_signature")

        if not all([razorpay_order_id, razorpay_payment_id, razorpay_signature]):
            return JsonResponse({"error": "Missing payment details"}, status=400)

        try:
            order = Order.objects.get(razorpay_order_id=razorpay_order_id)
        except Order.DoesNotExist:
            return JsonResponse({"error": "Order not found"}, status=404)

        try:
            razorpay_client.utility.verify_payment_signature({
                'razorpay_order_id': razorpay_order_id,
                'razorpay_payment_id': razorpay_payment_id,
                'razorpay_signature': razorpay_signature
            })
        except SignatureVerificationError:
            return JsonResponse({
                "success": False,
                "error": "Payment verification failed",
                "redirect_url": reverse('order_failure', kwargs={'order_id': order.id})
            }, status=400)

        with transaction.atomic():
            order = Order.objects.select_for_update().get(
                razorpay_order_id=razorpay_order_id,
                razorpay_payment_id__isnull=True
            )

            order.razorpay_payment_id = razorpay_payment_id
            order.razorpay_signature = razorpay_signature
            order.save()

            order_items = order.items.all()
            for item in order_items:
                product_variant = item.product_variant
                if product_variant.stock < item.quantity:
                    return JsonResponse({
                        "success": False,
                        "error": f"Insufficient stock for {product_variant.product.name}",
                        "redirect_url": reverse('order_failure', kwargs={'order_id': order.id})
                    }, status=400)
                product_variant.stock -= item.quantity
                product_variant.save()
                item.status = 'processing'
                item.save()

            # Clear the cart after successful payment
            CartItem.objects.filter(cart__user=order.user).delete()

            # Mark the coupon as used if applicable
            if order.coupon and not CouponUsage.objects.filter(user=order.user, coupon=order.coupon).exists():
                CouponUsage.objects.create(user=order.user, coupon=order.coupon)

            # Remove order ID from session
            request.session.pop('order_id', None)
            request.session.modified = True

            return JsonResponse({
                "success": True,
                "redirect_url": reverse('order_success', kwargs={'order_id': order.id})
            })

    except Exception as e:
        order_id = request.session.get('order_id')

        if order_id:
            try:
                order = Order.objects.get(id=order_id)
                return JsonResponse({
                    "success": False,
                    "error": f"Payment processing failed: {str(e)}",
                    "redirect_url": reverse('order_failure', kwargs={'order_id': order.id})
                }, status=500)
            except Order.DoesNotExist:
                pass

        return JsonResponse({"error": "Payment processing failed"}, status=500)


@login_required
def retry_payment(request, order_id):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=400)

    try:
        order = Order.objects.get(order_id=order_id, user=request.user, razorpay_payment_id__isnull=True)
        
        if order.payment_method != "Online":
            return JsonResponse({"error": "Retry only available for online payments"}, status=400)

        try:
            razorpay_order = razorpay_client.order.create({
                'amount': int(order.total_amount * 100),
                'currency': 'INR',
                'receipt': str(order.order_id),
                'payment_capture': '1'
            })
        except razorpay.errors.BadRequestError as e:
            return JsonResponse({
                "success": False,
                "error": f"Razorpay error: {str(e)}",
                "redirect_url": reverse('order_failure', kwargs={'order_id': order.order_id})
            }, status=400)

        order.razorpay_order_id = razorpay_order['id']
        order.razorpay_payment_id = None
        order.razorpay_signature = None
        order.save()

        return JsonResponse({
            "success": True,
            "key": settings.RAZORPAY_KEY_ID,
            "amount": int(order.total_amount * 100),
            "currency": "INR",
            "razorpay_order_id": razorpay_order['id'],
            "order_id": order.order_id
        })

    except Order.DoesNotExist:
        return JsonResponse({"error": "Order not found"}, status=404)
    except Exception as e:
        return JsonResponse({"error": "Failed to initiate retry payment"}, status=500)


@login_required
def order_failure(request, order_id):
    try:
        order = get_object_or_404(Order, order_id=order_id, user=request.user)
        if order.razorpay_payment_id and order.razorpay_signature:
            return redirect('order_success', order_id=order_id)
            
        context = {
            'order': order,
            'retry_url': reverse('retry_payment', kwargs={'order_id': order_id}),
            'razorpay_key': settings.RAZORPAY_KEY_ID,
            'amount': int(order.total_amount * 100),
            'currency': 'INR'
        }
        return render(request, 'order_failure.html', context)
    except Order.DoesNotExist:
        return redirect('shop_page')
       


@login_required
def order_success(request, order_id):
    order = get_object_or_404(Order, order_id=order_id, user=request.user)
    order_items = order.items.all().select_related('product_variant__product')

    if order.payment_method == "Online" and not (order.razorpay_payment_id and order.razorpay_signature):
        return redirect('order_failure', order_id=order_id)
        
    context = {
        'order': order,
        'order_items': order_items
    }
    
    return render(request, 'order_success.html', context)   
    
    

@login_required
def order_success(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    order_items = order.items.all().select_related('product_variant__product')
    
    context = {
        'order': order,
        'order_items': order_items
    }
    
    return render(request, 'order_success.html', context)





@login_required
def add_address(request):
    if request.method == 'POST':
        form = AddressForm(request.POST)
        if form.is_valid():
            address = form.save(commit=False)
            address.user = request.user
            address.save()
            return redirect('checkout')
    else:
        form = AddressForm()

    return render(request, 'add_address.html', {'form': form})


@login_required
def edit_address(request, address_id):
    address = get_object_or_404(Address, id=address_id, user=request.user)

    if request.method == "POST":
        form = AddressForm(request.POST, instance=address)
        if form.is_valid():
            form.save()
            return redirect('checkout') 
    else:
        form = AddressForm(instance=address)

    return render(request, 'edit_address.html', {'form': form})


@login_required
def set_default_address(request):
    if request.method == "POST":
        data = json.loads(request.body)
        address_id = data.get("address_id")

        address = get_object_or_404(Address, id=address_id, user=request.user)

        # Remove default from all addresses
        Address.objects.filter(user=request.user, is_default=True).update(is_default=False)

        # Set the new default address
        address.is_default = True
        address.save()

        return JsonResponse({"success": True, "message": "Default address updated."})

    return JsonResponse({"success": False, "message": "Invalid request."}, status=400)


# Delete Address
@login_required
def delete_address(request, address_id):
    address = get_object_or_404(Address, id=address_id, user=request.user)
    address.delete()
    return redirect('checkout')





#--------------------------------------------------------------------------------------------------------------------------------------#

@staff_member_required
def admin_order_list(request):
    orders_list = Order.objects.all().order_by('-order_date')
    paginator = Paginator(orders_list, 10)
    page_number = request.GET.get('page')
    orders = paginator.get_page(page_number)
    return render(request, 'admin_order_list.html', {
        'orders': orders,
        'total_orders': orders_list.count()
    })




@staff_member_required
def admin_order_detail(request, order_id):
    order = get_object_or_404(Order, order_id=order_id)
    return render(request, 'admin_order_detail.html', {'order': order})




@staff_member_required
def admin_update_order_item_status(request, order_id, item_id):
    order = get_object_or_404(Order, order_id=order_id)
    order_item = get_object_or_404(OrderItem, id=item_id)

    if request.method == "POST":
        new_status = request.POST.get("status")

        if not new_status:
            messages.error(request, "No status provided.")
            return redirect('admin_order_detail', order_id=order.order_id)

        all_items = order.items.all()
        all_cancelled = all(item.status == 'cancelled' for item in all_items)

        if all_cancelled:
            messages.error(request, "This order is fully cancelled. You cannot update item statuses.")
            return redirect('admin_order_detail', order_id=order.order_id)

        current_status = order_item.status

        # ❌ Prevent changing status of refunded item (except keeping it as refunded)
        if current_status == 'refunded' and new_status != 'refunded':
            messages.error(request, "Cannot change status of an already refunded item.")
            return redirect('admin_order_detail', order_id=order.order_id)

        # ❌ Refund only allowed from return_processed
        if current_status != 'return_processed' and new_status == 'refunded':
            messages.error(request, "Refunds can only be issued after return is processed.")
            return redirect('admin_order_detail', order_id=order.order_id)

        # ❌ Only delivered products can be cancelled
        if new_status == 'cancelled' and current_status != 'delivered':
            messages.error(request, "Only delivered items can be cancelled.")
            return redirect('admin_order_detail', order_id=order.order_id)

        # ❌ Cannot mark cancelled product as delivered
        if current_status == 'cancelled' and new_status == 'delivered':
            messages.error(request, "Cannot deliver an item that has already been cancelled.")
            return redirect('admin_order_detail', order_id=order.order_id)

        # ✅ Process refund
        if new_status == 'refunded':
            try:
                user = order.user
                item_subtotal = order_item.price * order_item.quantity
                item_with_discount = item_subtotal - order_item.discount

                # Calculate coupon impact
                coupon_discount_for_item = 0
                if order.coupon and order.coupon_discount > 0:
                    if order.coupon.is_percentage:
                        coupon_discount_for_item = item_with_discount * (order.coupon.discount / 100)
                        if order.coupon.max_discount:
                            coupon_discount_for_item = min(coupon_discount_for_item, order.coupon.max_discount)
                    else:
                        total_order_value = sum((item.price * item.quantity) - item.discount for item in all_items)
                        if total_order_value > 0:
                            item_proportion = item_with_discount / total_order_value
                            coupon_discount_for_item = order.coupon_discount * item_proportion

                refund_amount = item_with_discount - coupon_discount_for_item
                refund_amount = max(refund_amount, 0)

                # Credit wallet
                wallet, _ = Wallet.objects.get_or_create(user=user)
                wallet.balance += refund_amount
                wallet.save()

                WalletTransaction.objects.create(
                    wallet=wallet,
                    amount=refund_amount,
                    transaction_type='credit',
                    order=order,
                    description=f'Refund for order item #{order_item.id} in order #{order.order_id}'
                )

                messages.success(request, f"Item refunded and ₹{refund_amount:.2f} added to customer's wallet.")
            except Exception as e:
                messages.error(request, f"Error processing refund: {str(e)}")
                return redirect('admin_order_detail', order_id=order.order_id)

        # Save updated status
        order_item.status = new_status
        order_item.save()

        if new_status != 'refunded':
            messages.success(request, f"Item status updated to {new_status.capitalize()}.")

        return redirect('admin_order_detail', order_id=order.order_id)



#--------------------------------------------------------------------------------------------------------------------------------#

# coupon making


@staff_member_required
def create_coupon(request):
    if request.method == 'POST':

        form = CouponForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request,'coupon created successfully')
            return redirect('coupon_list')
    else:
        form = CouponForm()
        context = {
        'form': form,
        'today': date.today().isoformat(),
    }   
    return render(request,'create_coupon.html',context) 

@staff_member_required
def coupon_edit(request,coupon_id):
    coupon=get_object_or_404(Coupon,id=coupon_id)

    if request.method == 'POST':
        form=CouponForm(request.POST,instance=coupon)

        if form.is_valid():
            form.save()
            return redirect('coupon_list')
    else:
        form=CouponForm(instance=coupon)   
        context={
            'form':form,
            'today':date.today().isoformat()
        }
        return render(request,'edit_coupon.html',context)
    
@staff_member_required
def toggle_coupon_status(request,coupon_id):
    offer=get_object_or_404(Coupon,id=coupon_id)    
    offer.active = not offer.active
    offer.save()
    status= 'unbocked' if offer.active else 'blocked'
    messages.success(request,f" coupon has been {status}")

    return redirect('coupon_list')

@staff_member_required
def coupon_list(request):
    coupons=Coupon.objects.all()
    return render(request,'coupon_list.html',{'coupons':coupons})

def apply_coupon(request):
    if request.method == 'POST':
        coupon_code=request.POST.get('coupon_code').strip()
        order=request.session.get("order_id")


#__________________________________________________________________________________________________________________________#
# print invoice 

@staff_member_required
def admin_invoice(request, order_id):
    order = get_object_or_404(Order, order_id=order_id)
    context = {
        'order': order,
    }
    return render(request, 'admin_invoice.html', context)





