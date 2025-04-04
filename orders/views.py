from django.shortcuts import render,get_object_or_404,redirect
from cart.models import Cart,CartItem
from .models import ShippingAddress,Order,OrderItem,Address,Coupon,CouponUsage
from .forms import AddressForm,CouponForm
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

    # Get coupon details from session (fallback to checkout_data if needed)
    coupon_code = request.session.get('coupon_code', checkout_data.get('coupon_code'))
    try:
        coupon_discount = Decimal(request.session.get('coupon_discount', checkout_data.get('coupon_discount', '0.00')))
    except Exception as e:
        coupon_discount = Decimal('0.00')
    
    coupon_discount = min(coupon_discount, subtotal_after_discount)

    # Calculate shipping and final price
    shipping_cost = Decimal('0.00') if subtotal_after_discount - coupon_discount > Decimal('1000') else Decimal('50.00')
    final_price = max(subtotal_after_discount - coupon_discount + shipping_cost, Decimal('0.00'))

    # Update checkout data with calculated final_price
    checkout_data['final_price'] = str(final_price)
    
    # Save updated checkout data in session
    request.session['checkout_data'] = checkout_data
    request.session.modified = True

    if request.method == "POST":
        if 'coupon_code' in request.POST:
            coupon_code_input = request.POST.get('coupon_code', '').strip()
            if coupon_code_input:
                try:
                    coupon = Coupon.objects.get(code=coupon_code_input, active=True)
                    if not coupon.is_valid():
                        messages.error(request, "This coupon is not valid.")
                    elif CouponUsage.objects.filter(user=request.user, coupon=coupon).count() >= coupon.usage_limit:
                        messages.error(request, "Coupon usage limit reached.")
                    elif subtotal_after_discount < coupon.min_order_value:
                        messages.error(request, f"Minimum order of ₹{coupon.min_order_value} required.")
                    else:
                        # Calculate coupon discount
                        discount = (subtotal_after_discount * coupon.discount / 100) if coupon.is_percentage else coupon.discount
                        if coupon.is_percentage and coupon.max_discount:
                            discount = min(discount, coupon.max_discount)
                        # Update session with coupon details
                        request.session['coupon_code'] = coupon.code
                        request.session['coupon_discount'] = str(discount)
                        coupon_code = coupon.code
                        coupon_discount = Decimal(discount)
                        messages.success(request, "Coupon applied successfully!")
                except Coupon.DoesNotExist:
                    messages.error(request, "Invalid coupon code.")
                    request.session.pop('coupon_code', None)
                    request.session.pop('coupon_discount', None)
                    coupon_code = None
                    coupon_discount = Decimal('0.00')
            else:
                # Remove coupon if input is empty
                request.session.pop('coupon_code', None)
                request.session.pop('coupon_discount', None)
                coupon_code = None
                coupon_discount = Decimal('0.00')
                messages.success(request, "Coupon removed.")

            # Recalculate final price after coupon changes
            coupon_discount = min(coupon_discount, subtotal_after_discount)
            final_price = max(subtotal_after_discount - coupon_discount + shipping_cost, Decimal('0.00'))
            
            # Update checkout data with coupon details and final price
            checkout_data.update({
                'final_price': str(final_price),
                'coupon_code': coupon_code,
                'coupon_discount': str(coupon_discount)
            })
            request.session['checkout_data'] = checkout_data
            request.session.modified = True

            return redirect('checkout')

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
        'payment_method': checkout_data.get('payment_method', 'cod')
    }

    return render(request, 'checkout.html', context)


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
    except Exception as e:
        print(f"Error parsing coupon discount: {e}")
        coupon_discount = Decimal('0.00')

    shipping_cost = Decimal('0.00') if subtotal_after_discount - coupon_discount > Decimal('1000') else Decimal('50.00')
    final_price = max(subtotal_after_discount - coupon_discount + shipping_cost, Decimal('0.00'))

    # Update checkout data with corrected final price
    checkout_data['final_price'] = str(final_price)
    request.session['checkout_data'] = checkout_data
    request.session.modified = True

    context = {
        'cart_items': cart_items,
        'total_price': total_price,
        'product_discount': product_discount,
        'subtotal_after_discount': subtotal_after_discount,
        'coupon_discount': coupon_discount,
        'shipping_cost': shipping_cost,
        'final_price': final_price,
        'payment_method': checkout_data.get('payment_method', ''),
        'applied_coupon': checkout_data.get('coupon_code')
    }

    return render(request, 'payment.html', context)


razorpay_client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))


@login_required
def process_payment(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=400)

    try:
        data = json.loads(request.body)
        payment_method = data.get("payment_method")
        # Optional order_id for payment retry (only applicable for razorpay)
        order_id = data.get("order_id")
        print(f"Received payment method: {payment_method}")

        if payment_method not in ["cod", "razorpay"]:
            return JsonResponse({"error": f"Invalid payment method: {payment_method}"}, status=400)

        # COD payments should never be retried – if an order_id is provided, raise an error.
        if payment_method == "cod" and order_id:
            return JsonResponse({"error": "COD payments cannot be retried"}, status=400)

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
                print(f"Razorpay BadRequestError (retry): {str(e)}")
                return JsonResponse({"error": f"Razorpay error: {str(e)}"}, status=400)
            except Exception as e:
                print(f"Razorpay Authentication Error (retry): {str(e)}")
                return JsonResponse({"error": "Payment authentication failed"}, status=500)
            order.razorpay_order_id = razorpay_order['id']
            order.save(update_fields=['razorpay_order_id'])
            return JsonResponse({
                "success": True,
                "key": settings.RAZORPAY_KEY_ID,  # Use the public key from settings
                "amount": int(order.total_amount * 100),
                "currency": "INR",
                "razorpay_order_id": razorpay_order['id']
            })

        # Normal flow (new order creation)
        checkout_data = request.session.get('checkout_data', {})
        print(f"Checkout data: {checkout_data}")
        address_id = checkout_data.get('address_id')
        if not address_id:
            print("Error: Address ID missing from checkout_data")
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
                # Remove checkout session data
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
                # Remove checkout session data
                request.session.pop('checkout_data', None)
                request.session.pop('coupon_code', None)
                request.session.pop('coupon_discount', None)
                request.session.modified = True

                # Create Razorpay order (amount in paisa)
                try:
                    razorpay_order = razorpay_client.order.create({
                        'amount': int(final_price * 100),
                        'currency': 'INR',
                        'receipt': order.order_id,
                        'payment_capture': '1'
                    })
                except razorpay.errors.BadRequestError as e:
                    print(f"Razorpay BadRequestError: {str(e)}")
                    return JsonResponse({"error": f"Razorpay error: {str(e)}"}, status=400)
                except Exception as e:
                    print(f"Razorpay Authentication Error: {str(e)}")
                    return JsonResponse({"error": "Payment authentication failed"}, status=500)

                order.razorpay_order_id = razorpay_order['id']
                order.save(update_fields=['razorpay_order_id'])

                return JsonResponse({
                    "success": True,
                    "key": settings.RAZORPAY_KEY_ID,  # Use the public key from settings
                    "amount": int(final_price * 100),
                    "currency": "INR",
                    "razorpay_order_id": razorpay_order['id']
                })

    except json.JSONDecodeError as e:
        print(f"JSON Decode Error: {str(e)}")
        return JsonResponse({"error": "Invalid request data"}, status=400)
    except Exception as e:
        print(f"Error in process_payment: {str(e)}")
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
        print(f"Verification Error: {str(e)}")
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
        print(f"Retry Payment Error: {str(e)}")
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
def update_order_status(request, order_id): 
    if request.method == "POST":
        new_status = request.POST.get("status")

        order = get_object_or_404(Order, order_id=order_id)
        
        if new_status in dict(Order.STATUS_CHOICES):
            order.status = new_status
            order.save()
            return JsonResponse({"success": True, "message": "Order status updated!", "new_status": order.get_status_display()})
        else:
            return JsonResponse({"success": False, "message": "Invalid status!"})
    
    return JsonResponse({"success": False, "message": "Invalid request method!"})


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
        if new_status:
            order_item.status = new_status
            order_item.save()

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







