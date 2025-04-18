from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.core.paginator import Paginator
from .models import Product, ProductVariant,Image,ProductOffer
from category.models import Category
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from .forms import ProductOfferForm
from django.contrib.admin.views.decorators import staff_member_required
from django.urls import reverse 
from datetime import date



@staff_member_required
def add_product(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description')
        price = request.POST.get('price')
        offer_price = request.POST.get('offer_price')
        category_id = request.POST.get('category')
        brand = request.POST.get('brand')

        # Validate the data
        if not name or not price or not offer_price or not category_id:
            messages.error(request, 'Please fill in all required fields.')
            return redirect('add_product')

        try:
            price = float(price)
            offer_price = float(offer_price)
        except ValueError:
            messages.error(request, 'Price and offer price must be valid numbers.')
            return redirect('add_product')

        #Validate offer price logic
        if offer_price >= price:
            messages.error(request, 'Offer price must be less than the actual price.')
            return redirect('add_product')

        try:
            category = Category.objects.get(id=category_id)
        except Category.DoesNotExist:
            messages.error(request, 'Invalid category selected.')
            return redirect('add_product')

        # Create and save the product
        product = Product(
            name=name,
            description=description,
            price=price,
            offer_price=offer_price,
            category=category,
            brand=brand
        )
        product.save()

        messages.success(request, 'Product added successfully!')
        return redirect('product_list')

    categories = Category.objects.all()
    return render(request, 'add_product.html', {'categories': categories})




@staff_member_required
def edit_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    categories = Category.objects.all()
    errors = []

    if request.method == 'POST':
        # Get form data
        name = request.POST.get('name')
        description = request.POST.get('description')
        price = request.POST.get('price')
        offer_price = request.POST.get('offer_price')
        category_id = request.POST.get('category')
        brand = request.POST.get('brand')

        # Basic validation
        if not name:
            errors.append("Product name is required")
        if not price:
            errors.append("Price is required")
        if not category_id:
            errors.append("Category is required")

        # Convert numeric fields
        try:
            price = float(price) if price else None
        except ValueError:
            errors.append("Invalid price format")

        try:
            offer_price = float(offer_price) if offer_price else None
        except ValueError:
            errors.append("Invalid offer price format")

        # Offer price must be less than actual price
        if price is not None and offer_price is not None and offer_price >= price:
            errors.append("Offer price must be less than the actual price")

        # Check category existence
        try:
            category = Category.objects.get(id=category_id)
        except (Category.DoesNotExist, ValueError, TypeError):
            errors.append("Invalid category selected")
            category = None

        # If no errors, update the product
        if not errors:
            product.name = name
            product.description = description
            product.price = price
            product.offer_price = offer_price
            product.category = category
            product.brand = brand
            product.save()
            messages.success(request, 'Product updated successfully!')
            return redirect('product_list')

        # If errors, retain entered values (optional but helps with user experience)
        product.name = name
        product.description = description
        product.price = price
        product.offer_price = offer_price
        product.brand = brand

    context = {
        'product': product,
        'categories': categories,
        'errors': errors,
    }
    return render(request, 'edit_product.html', context)






@staff_member_required
def toggle_variant_status(request):
    if request.method == 'POST':
        variant_id = request.POST.get('variant_id')
        variant = get_object_or_404(ProductVariant, id=variant_id)
        variant.is_active = not variant.is_active
        variant.save()
        new_status = 'active' if variant.is_active else 'blocked'
        return JsonResponse({'status': 'success', 'new_status': new_status})
    return JsonResponse({'status': 'error'})


@staff_member_required
def toggle_product_status(request):
    if request.method == 'POST':
        product_id = request.POST.get('product_id')
        product = get_object_or_404(Product, id=product_id)
        product.is_active = not product.is_active
        product.save()
        return JsonResponse({
            'status': 'success',
            'new_status': 'active' if product.is_active else 'blocked'
        })
    return JsonResponse({'status': 'error'}, status=400)

@staff_member_required
def add_variant(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    
    # Size configuration
    shoe_categories = ['Shoes', 'Sandals', 'Slippers']
    shoe_sizes = ['6', '7', '8', '9', '10', '11', '12', '13']
    clothing_sizes = ['XS', 'S', 'M', 'L', 'XL', 'XXL']
    
    size_suggestions = shoe_sizes if product.category.name in shoe_categories else clothing_sizes

    if request.method == 'POST':
        errors = []
        color = request.POST.get('color', '').strip()
        stock = request.POST.get('stock', '').strip()
        size = request.POST.get('size', '').strip()
        images = request.FILES.getlist('images')

        # Validation
        if not color:
            errors.append('Color is required')
        if not stock.isdigit() or int(stock) < 0:
            errors.append('Valid stock quantity is required')
        if not size:
            errors.append('Size is required')
        if len(images) == 0:
            errors.append('At least one image is required')

        if errors:
            return JsonResponse({'errors': errors}, status=400)

        try:
            # Create variant
            variant = ProductVariant.objects.create(
                product=product,
                color=color,
                stock=int(stock),
                size=size
            )

            # Save images
            for image in images:
                Image.objects.create(variant=variant, image=image)

            return JsonResponse({
                'redirect_url': reverse('variant_list', kwargs={'product_id': product.id})
            })

        except Exception as e:
            print(f"Error creating variant: {str(e)}")
            return JsonResponse({
                'errors': ['An error occurred while saving the variant. Please try again.']
            }, status=500)

    return render(request, 'add_variant.html', {
        'product': product,
        'size_suggestions': size_suggestions
    })



@staff_member_required
@require_http_methods(["GET", "POST"])
def edit_variant(request, product_id, variant_id):
    product = get_object_or_404(Product, id=product_id)
    variant = get_object_or_404(ProductVariant, id=variant_id, product=product)
    existing_images = variant.images.all()

    # Size configuration
    shoe_categories = ['Shoes', 'Footwear', 'Slippers', 'Sandals', 'Sports Shoes']
    clothing_sizes = ['XS', 'S', 'M', 'L', 'XL', 'XXL']
    
    if product.category.name in shoe_categories:
        size_suggestions = ['6', '7', '8', '9', '10', '11', '12', '13']
    else:
        size_suggestions = clothing_sizes

    if request.method == 'POST':
        color = request.POST.get('color', '').strip()
        stock = request.POST.get('stock', '').strip()
        size = request.POST.get('size', '').strip()
        images = request.FILES.getlist('images')
        delete_images = request.POST.getlist('delete_images')

        # Validation
        errors = []
        if not color:
            errors.append('Color is required.')
        if not stock.isdigit() or int(stock) < 0:
            errors.append('Valid stock quantity is required.')
        if not size:
            errors.append('Size is required.')

        if errors:
            return JsonResponse({'errors': errors}, status=400)

        try:
            # Update variant
            variant.color = color
            variant.stock = int(stock)
            variant.size = size
            variant.save()


            if delete_images:
                Image.objects.filter(id__in=delete_images).delete()


            for image in images:
                Image.objects.create(variant=variant, image=image)

            return JsonResponse({
                'redirect_url': reverse('variant_list', kwargs={'product_id': product.id})
            })

        except Exception as e:
            print(f"Error updating variant: {str(e)}")
            return JsonResponse({
                'errors': ['An error occurred while updating the variant. Please try again.']
            }, status=500)

    return render(request, 'edit_variant.html', {
        'product': product,
        'variant': variant,
        'existing_images': existing_images,
        'size_suggestions': size_suggestions
    })

@staff_member_required
def variant_list(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    variants = ProductVariant.objects.prefetch_related("images").filter(product_id=product_id)

    paginator = Paginator(variants, 10)  # Show 10 variants per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'variant_list.html', {
        'product': product,
        'page_obj': page_obj
    })
@staff_member_required
def product_managment(request):
    products = Product.objects.all()
    paginator = Paginator(products, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'product_management.html', {'page_obj': page_obj})

@staff_member_required
def product_offer_list(request):
    offers=ProductOffer.objects.all()
    return render(request,'product_offer_list.html',{'offers':offers})

#------------------------------------------------------------------------------------------------------------------------------------#
#product offer section 

@staff_member_required
def add_product_offer(request):
    today = date.today().isoformat() 
    
    if request.method == 'POST':
        form = ProductOfferForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Product Offer added successfully!')
            return redirect('product_offer_list')
       
    else:
        form = ProductOfferForm()
    
    return render(request, 'add_product_offer.html', {
        'form': form,
        'today': today
    })





@staff_member_required
def edit_product_offer(request,offer_id):
    offer=get_object_or_404(ProductOffer,id=offer_id)
    today = date.today().isoformat() 

    if request.method =='POST':
        form=ProductOfferForm(request.POST,instance=offer)
        if form.is_valid():
            form.save()
            messages.success(request,'Product offer updated successfully')
            return redirect('product_offer_list')
    else:
        form=ProductOfferForm(instance=offer)    
    return render(request,'edit_product_offer.html',{'form':form,'today':today})   



@staff_member_required
def toggle_product_offer_status(request,offer_id):
    offer=get_object_or_404(ProductOffer,id=offer_id)    
    offer.is_active = not offer.is_active
    offer.save()
    status= 'unbocked' if offer.is_active else 'blocked'
    messages.success(request,f" category offer as been {status}")

    return redirect('product_offer_list')