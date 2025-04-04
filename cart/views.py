from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from .models import Cart, CartItem, ProductVariant,WalletTransaction,Wallet
from django.contrib.admin.views.decorators import staff_member_required

user = get_user_model()

@login_required
def add_to_cart(request, variant_id):
    if request.method == 'POST':
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Authentication required'}, status=401)

        try:
            variant = ProductVariant.objects.select_related('product').get(id=variant_id)
            cart, _ = Cart.objects.get_or_create(user=request.user)

            if variant.stock < 1:
                return JsonResponse({
                    'error': 'Sorry, this product variant is currently out of stock'
                }, status=400)

            cart_item, created = CartItem.objects.get_or_create(
                cart=cart,
                product_variant=variant,
                defaults={'quantity': 1}
            )

            if not created:
                if cart_item.quantity >= variant.stock:
                    return JsonResponse({'error': 'Maximum quantity reached for this product variant'}, status=400)
                cart_item.quantity += 1

            cart_item.save()

            return JsonResponse({
                'success': True,
                'message': "Product added to cart successfully" if created else "Product quantity updated",
                'variant_id': variant_id,
                'new_quantity': cart_item.quantity
            })

        except ProductVariant.DoesNotExist:
            return JsonResponse({'error': 'Product variant not found'}, status=404)

    return JsonResponse({'error': 'Invalid request method'}, status=400)

@require_POST
@login_required
def update_cart_item(request, item_id):
    try:
        user_cart = get_object_or_404(Cart, user=request.user)
        cart_item = get_object_or_404(CartItem, id=item_id, cart=user_cart)

        action = request.POST.get('action')

        if action == 'increase':
            quantity = cart_item.quantity + 1
        elif action == 'decrease':
            quantity = cart_item.quantity - 1
        else:
            quantity = int(request.POST.get('quantity', cart_item.quantity))

        # Ensure quantity does not exceed 5 and is at least 1
        if quantity < 1:
            return JsonResponse({'success': False, 'message': 'Quantity must be at least 1.'})
        if quantity > min(cart_item.product_variant.stock, 5):  # Limit to 5 or available stock
            return JsonResponse({'success': False, 'message': 'Maximum quantity allowed is 5.'})

        cart_item.quantity = quantity
        cart_item.save()

        # Recalculate totals
        cart_items = CartItem.objects.filter(cart=user_cart)
        total_price = sum(item.product_variant.product.price * item.quantity for item in cart_items)
        total_discount = sum(
            (item.product_variant.product.price - item.product_variant.product.offer_price) * item.quantity
            for item in cart_items
        )
        subtotal = total_price - total_discount
        shipping_cost = 0 if subtotal > 1000 else 50  # Free shipping if subtotal > 1000, else 50
        grand_total = subtotal + shipping_cost

        return JsonResponse({
            'success': True,
            'message': 'Cart updated successfully.',
            'quantity': cart_item.quantity,
            'item_total': cart_item.product_variant.product.offer_price * cart_item.quantity,
            'cart_data': {
                'subtotal': float(subtotal),
                'discount': float(total_discount),
                'shipping_cost': float(shipping_cost),
                'grand_total': float(grand_total),
                'item_count': cart_items.count()
            }
        })

    except ValueError:
        return JsonResponse({'success': False, 'message': 'Invalid quantity.'})
    except CartItem.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Cart item not found.'})


@require_POST
@login_required
def remove_cart_item(request, item_id):
    try:
        cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
        cart_item.delete()
        
        # Recalculate totals after removal
        cart_items = CartItem.objects.filter(cart__user=request.user)
        total_price = sum(item.product_variant.product.price * item.quantity for item in cart_items)
        total_discount = sum(
            (item.product_variant.product.price - item.product_variant.product.offer_price) * item.quantity
            for item in cart_items
        )
        subtotal = total_price - total_discount
        shipping_cost = 0 if subtotal > 1000 else 50  # Free shipping if subtotal > 1000, else 50
        grand_total = subtotal + shipping_cost

        return JsonResponse({
            'success': True,
            'message': 'Item removed successfully',
            'cart_data': {
                'subtotal': float(subtotal),
                'discount': float(total_discount),
                'shipping_cost': float(shipping_cost),
                'grand_total': float(grand_total),
                'item_count': cart_items.count()
            }
        })
    except CartItem.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Cart item not found'}, status=404)


@login_required
def cart_view(request):
    user = request.user
    cart_items = CartItem.objects.filter(cart__user=user)

    total_price = sum(item.product_variant.product.price * item.quantity for item in cart_items)
    total_discount = sum(
        (item.product_variant.product.price - item.product_variant.product.offer_price) * item.quantity
        for item in cart_items
    )
    subtotal = total_price - total_discount
    shipping_cost = 0 if subtotal > 1000 else 50  # Free shipping if subtotal > 1000, else 50
    grand_total = subtotal + shipping_cost

    context = {
        'cart_items': cart_items,
        'total_price': subtotal,  # Using subtotal for clarity
        'total_discount': total_discount,
        'shipping_cost': shipping_cost,
        'grand_total': grand_total,
    }

    return render(request, 'cart.html', context)

#______________________________________________________________________________________________________________________________________#

  #wallet 


@login_required
def user_wallet_view(request):
   wallet,created = Wallet.objects.get_or_create(user=request.user)


   transactions = WalletTransaction.objects.filter(wallet=wallet).order_by('-created_at')

   context={
       'wallet': wallet,
       'transactions':transactions
   }

   return render(request,'user_wallet.html',context)



@staff_member_required
def wallet_transaction_list(request):
    transactions = WalletTransaction.objects.select_related('wallet__user', 'order').order_by('-created_at')
    context = {
        'transactions': transactions,
        'page_title': 'Wallet Transactions'
    }
    return render(request, 'admin_wallet_transaction_list.html', context)



@staff_member_required
def wallet_transaction_detail(request, transaction_id):
    transaction = get_object_or_404(WalletTransaction.objects.select_related('wallet__user', 'order'),transaction_id=transaction_id)
    context = {
        'transaction': transaction,
        'page_title': f'Transaction Details - {transaction.transaction_id}'
    }
    return render(request, 'admin_wallet_transaction_detail.html', context)






