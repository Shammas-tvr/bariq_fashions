from django.shortcuts import render,redirect,get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_protect
from orders.models import Order,OrderItem,Address,OrderReturn
from django.contrib.auth import update_session_auth_hash
from django.contrib import messages
from django.http import JsonResponse
from django.contrib.auth import logout
from django.contrib.auth.hashers import check_password
from orders.forms import AddressForm
from cart.models import WalletTransaction,Wallet
from products.models import Product
from decimal import Decimal


@login_required
def user_profile(request):

    # If user is not authenticated, redirect to login page
    if not request.user.is_authenticated:
        messages.warning(request, "You need to login to access your profile")
        return redirect('userlogin')
    
    # User is authenticated, render profile page
    return render(request, 'user_profile.html')

@login_required
def update_profile(request):

    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        
        # Basic validation
        if not username or not email:
            messages.error(request, 'Username and email are required fields.')
            return redirect('profile')
        
        # Check if username is taken (excluding current user)
        from django.contrib.auth import get_user_model
        User = get_user_model()
        if User.objects.filter(username=username).exclude(id=request.user.id).exists():
            messages.error(request, 'This username is already taken.')
            return redirect('profile')
        
        # Update user
        user = request.user
        user.username = username
        user.email = email
        user.save()
        
        messages.success(request, 'Your profile has been updated successfully.')
        return redirect('user_profile')
    
    return redirect('user_profile')

@login_required
def change_password(request):

    if request.method == 'POST':
        current_password = request.POST.get('current_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
        user = request.user
        
        # Verify current password
        if not check_password(current_password, user.password):
            messages.error(request, 'Your current password is incorrect.')
            return redirect('profile')
        
        # Check if new passwords match
        if new_password != confirm_password:
            messages.error(request, 'New passwords do not match.')
            return redirect('profile')
        
        # Set new password
        user.set_password(new_password)
        user.save()
        
        # Update session to prevent logout
        update_session_auth_hash(request, user)
        
        messages.success(request, 'Your password has been changed successfully.')
        return redirect('profile')
    
    return redirect('profile')

@login_required
def logout_view(request):

    logout(request)
    messages.success(request, 'You have successfully logged out.')
    return redirect('userlogin')

#----------------------------------------------------------------------------------------------------------------------------------------#

@login_required
def order_history(request):
    orders = Order.objects.filter(user=request.user).prefetch_related("items__product_variant__images").order_by('-order_date')
    
    return render(request, 'orders_history.html', {
        'orders': orders,
        'active_tab': 'order_history'
    })




@login_required
def order_detail(request, order_id):
    order = get_object_or_404(Order, order_id=order_id, user=request.user)
    order_items = OrderItem.objects.filter(order=order).select_related('product_variant__product')

    return render(request, "order_detail.html", {"order": order, "order_items": order_items,'shipping_address':order.address})




@login_required
@csrf_protect
def cancel_order_item(request, order_id, item_id):
    if request.method != "POST":
        return JsonResponse({
            'success': False,
            'message': 'Invalid request method'
        }, status=400)

    try:
        order_item = get_object_or_404(OrderItem, id=item_id, order__order_id=order_id)
        
        if order_item.status not in ["pending", "processing"]:
            return JsonResponse({
                'success': False,
                'message': 'Cannot cancel this item in its current status'
            })

        # Cancel the item
        order_item.status = "cancelled"
        order_item.save()
        
        # Restock product variant
        variant = order_item.product_variant
        variant.stock += order_item.quantity
        variant.save()
        
        order = order_item.order
        # Check if all items are cancelled
        remaining_items = order.items.exclude(id=item_id)
        all_items_cancelled = not remaining_items.exists() or all(item.status == "cancelled" for item in remaining_items)
        if all_items_cancelled:
            order.status = "cancelled"
            order.save()

        # Refund process
        refund_amount = Decimal('0.00')  # Use Decimal for precision
        refund_message = "Item canceled successfully!"
        
        if order.payment_method != "COD":
            item_total = Decimal(order_item.final_price) * Decimal(order_item.quantity)
            
            if order.coupon_discount > 0:
                order_items_total = sum(Decimal(item.final_price) * Decimal(item.quantity) for item in order.items.all())
                discount_share = (item_total / order_items_total) * Decimal(order.coupon_discount) if order_items_total > 0 else Decimal('0.00')
                refund_amount = item_total - discount_share
            else:
                refund_amount = item_total
            
            # Add shipping cost to refund if all items are cancelled
            if all_items_cancelled and order.shipping_cost > 0:
                refund_amount += Decimal(order.shipping_cost)
                refund_message = f"Item canceled successfully! ₹{refund_amount:.2f} (including shipping cost) has been refunded to your wallet."
            else:
                refund_message = f"Item canceled successfully! ₹{refund_amount:.2f} has been refunded to your wallet."
            
            # Refund to wallet
            wallet = request.user.wallet
            wallet.add_balance(refund_amount)
            WalletTransaction.objects.create(
                wallet=wallet,
                amount=refund_amount,
                transaction_type="Credit",
                order=order,
                description=f"Refund for cancelled order #{order.order_id}"
            )
        else:
            refund_message = "Item canceled successfully! (COD orders are not refunded)"

        return JsonResponse({
            'success': True,
            'message': refund_message
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error: {str(e)}'
        }, status=500)




#----------------------------------------------------------------------------------------------------------------------------------------#



@login_required
def request_order_return(request, order_id, item_id):
    order = get_object_or_404(Order, order_id=order_id, user=request.user)
    order_item = get_object_or_404(OrderItem, id=item_id, order=order)
    return render(request, 'order_return.html', {
        'order': order, 
        'item': order_item  
    })



@login_required
def submit_order_return(request, order_id):
    if request.method == 'POST':
        item_id = request.POST.get('item_id')
        reason = request.POST.get('reason', '').strip()
        
        if not reason:
            messages.error(request, "Please provide a return reason.")
            return redirect('order_detail', order_id=order_id)
            
        order = get_object_or_404(Order, order_id=order_id, user=request.user)
        order_item = get_object_or_404(OrderItem, id=item_id, order=order)

        # Create return request
        OrderReturn.objects.create(
            user=request.user,
            order=order,
            order_item=order_item,
            reason=reason
        )

        # Update order item status
        order_item.status = 'return_requested'
        order_item.save()

        messages.success(request, "Return request submitted successfully.")
        return redirect('order_details', order_id=order_id)  # Fixed URL name

    return redirect('order_history')




#----------------------------------------------------------------------------------------------------------------------------------------#

# keep one, canonical list of statuses
ITEM_STATUSES = [choice[0] for choice in OrderItem.STATUS_CHOICES]

@login_required
def order_item_tracking(request, order_id, item_id):
    """
    Show the progress of a single OrderItem that belongs to the
    current user’s order.
    """
    order = get_object_or_404(
        Order.objects.select_related("user"),
        order_id=order_id,
        user=request.user,
    )
    item = get_object_or_404(
        order.items.select_related("product_variant"),
        pk=item_id,
    )

    tracking_steps = [
        {
            "status": status,
            "label": dict(OrderItem.STATUS_CHOICES)[status],
            "completed": ITEM_STATUSES.index(item.status) >= ITEM_STATUSES.index(status),
            "current": item.status == status,
        }
        for status in ITEM_STATUSES
    ]

    context = {
        "order": order,
        "item": item,
        "tracking_steps": tracking_steps,
    }
    return render(request, "order_item_tracking.html", context)



#----------------------------------------------------------------------------------------------------------------------------------------#
                            #address section #

@login_required
def address_list(request):
    addresses = Address.objects.filter(user=request.user)
    return render(request, 'address_list.html', {'addresses': addresses})


@login_required
def profile_add_address(request):

    if request.method =='POST':
        form=AddressForm(request.POST)
        if form.is_valid():
            address=form.save(commit=False)
            address.user = request.user
            address.save()
            return redirect('address_list')
    else:
        form=AddressForm()
    return render(request,'profile_add_address.html',{'form':form})


    
@login_required
def profile_edit_address(request,address_id):

    address=get_object_or_404(Address,id=address_id,user=request.user)

    if request.method =='POST':
        form=AddressForm(request.POST,instance=address)
        if form.is_valid():
            form.save()
            return redirect('address_list')
        
    else:
        form=AddressForm(instance=address)
    return render(request,'profile_edit_address.html',{'form':form,'address':address})    


@login_required
def profile_delete_address(request,address_id):
    address=get_object_or_404(Address,id=address_id,user=request.user)

    if request.method =='POST':
        address.delete()
    return redirect('address_list')







def ajax_search(request):
    try:
        query = request.GET.get('q', '').strip()
        if not query:
            return JsonResponse({'results': []})

        products = Product.objects.filter(name__icontains=query)[:5]
        
        results = []
        for product in products:
            # Get the first variant (if any) to access its images
            variant = product.variants.first() if hasattr(product, 'variants') and product.variants.exists() else None
            image_url = None
            if variant:
                # Get the first image from the variant's images
                first_image = variant.images.first()
                image_url = first_image.image.url if first_image else None

            results.append({
                'id': product.id,
                'name': product.name,
               
                'category': product.category.name if hasattr(product, 'category') and product.category else '',
                'image_url': image_url or '/static/images/default-product.jpg',  # Fallback to default if no image
            })

        return JsonResponse({'results': results})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500) 



@login_required
def user_invoice(request,order_id):
    order=get_object_or_404(Order,order_id=order_id,user=request.user)
    return render(request,'user_invoice.html',{'order':order})