from django.shortcuts import render , redirect , get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from .models import Category,CategoryOffer
from .forms import CategoryOfferForm
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.contrib import messages
from datetime import date

@staff_member_required
def category_list(request):
    categories = Category.objects.all().order_by("name")   # or "-id", etc.

    paginator   = Paginator(categories, 5)
    page_number = request.GET.get("page")
    page_obj    = paginator.get_page(page_number)

    return render(
        request,
        "category_list.html",
        {
            "categories": page_obj,        # paginated slice
            "total_categories": paginator.count,  # uses cached count
        },
    )


staff_member_required
def category_add(request):
    if request.method=='POST':
        category_name=request.POST.get('category_name')
        description=request.POST.get('description')
        category_image=request.FILES.get('category_image')

        if category_name and description:
            category=Category(name=category_name,description=description,image=category_image)
            category.save()
            return redirect('category_list')
        
    return render(request,'category_add.html')  

staff_member_required
def category_edit(request,category_id):
    category=get_object_or_404(Category,id=category_id)
    if request.method == 'POST':
        category_name=request.POST.get('category_name')
        description=request.POST.get('description')
        category_image=request.FILES.get('category_image')
        remove_image=request.POST.get('remove_image')



        if category_name and description :
            category.name = category_name
            category.description = description

            if category_image :
                category.image = category_image

            elif remove_image:
                category.image= None
            category.save()
            return redirect('category_list')
        
    return render(request,'category_edit.html',{'category':category})    
        


staff_member_required
@require_POST
def toggle_category_status(request):
    category_id = request.POST.get('category_id')
    category = get_object_or_404(Category, id=category_id)
    category.status = 'blocked' if category.status == 'active' else 'active'
    category.save()
    return JsonResponse({'status': 'success', 'new_status': category.status})


#////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////#


#category offer section
staff_member_required
def category_offer_list(request):
    offers=CategoryOffer.objects.all()
    return render(request,'category_offer_list.html',{'offers':offers})


@staff_member_required
def add_category_offer(request):
    if request.method == 'POST':
        form = CategoryOfferForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('category_offer_list')
    else:
        form = CategoryOfferForm()
        # Show only active/unblocked categories
        form.fields['category'].queryset = Category.objects.filter(status='active')

    context = {
        'form': form,
        'today': date.today().isoformat()
    }
    return render(request, 'add_category_offer.html', context)

@staff_member_required
def edit_category_offer(request, offer_id):
    offer = get_object_or_404(CategoryOffer, id=offer_id)
    if request.method == 'POST':
        form = CategoryOfferForm(request.POST, instance=offer)
        if form.is_valid():
            form.save()
            return redirect('category_offer_list')
    else:
        form = CategoryOfferForm(instance=offer)
        # Filter only active/unblocked categories
        form.fields['category'].queryset = Category.objects.filter(status='active')

    context = {
        'form': form,
        'today': date.today().isoformat(),
    }
    return render(request, 'edit_category_offer.html', context)
    
staff_member_required
def toggle_category_offer_status(request,offer_id):
    offer=get_object_or_404(CategoryOffer,id=offer_id)    
    offer.is_active = not offer.is_active
    offer.save()
    status= 'unbocked' if offer.is_active else 'blocked'
    messages.success(request,f" category offer as been {status}")

    return redirect('category_offer_list')