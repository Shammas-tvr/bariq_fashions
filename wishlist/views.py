from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from .models import Wishlist, Product, ProductVariant
from django.db import IntegrityError
import json

@login_required
def wishlist_page(request):
    wishlist_items = Wishlist.objects.filter(user=request.user).select_related(
        'product', 'variant'
    ).prefetch_related('product__offers')
    
    # Prepare user_wishlist for template
    user_wishlist = [item.product.id for item in wishlist_items]
    
    return render(request, "wishlist.html", {
        "wishlist_items": wishlist_items,
        "user_wishlist": user_wishlist
    })

# The toggle_wishlist view can remain unchanged as it already handles removal correctly
@login_required
@require_POST
def toggle_wishlist(request):
    try:
        data = json.loads(request.body)
        product_id = data.get('product_id')
        variant_id = data.get('variant_id')

        if not variant_id:
            return JsonResponse({'success': False, 'message': 'Variant is required'})

        product = Product.objects.get(id=product_id)
        variant = ProductVariant.objects.get(id=variant_id)
        
        if variant.product != product:
            return JsonResponse({'success': False, 'message': 'Invalid variant for this product'})

        wishlist_item = Wishlist.objects.filter(
            user=request.user,
            product=product,
            variant=variant
        ).first()
        
        if wishlist_item:
            wishlist_item.delete()
            return JsonResponse({'success': True, 'action': 'removed'})
        else:
            Wishlist.objects.create(
                user=request.user,
                product=product,
                variant=variant
            )
            return JsonResponse({'success': True, 'action': 'added'})
            
    except Product.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Product not found'})
    except ProductVariant.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Variant not found'})
    except IntegrityError:
        return JsonResponse({'success': False, 'message': 'Wishlist item already exists'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})
