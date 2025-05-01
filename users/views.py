from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import get_user_model, authenticate, login
from django.contrib import messages
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
import random
import time
from django.utils.timezone import now
from products.models import Product,ProductVariant
from django.db.models import Exists, OuterRef
from wishlist.models import Wishlist
from category.models import Category

User = get_user_model()

def user_signup(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        pass1 = request.POST.get('password1')
        pass2 = request.POST.get('password2')

        errors = []

        if pass1 != pass2:
            errors.append('Password and Confirm Password do not match.')
        if User.objects.filter(username=username).exists():
            errors.append('Username is already taken.')
        if User.objects.filter(email=email).exists():
            errors.append('This email is already registered.')

        try:
            validate_password(pass1)
        except ValidationError as e:
            errors.extend(e.messages)

        if errors:
            return render(request, 'user_signup.html', {'errors': errors})

        # Store signup data in session
        request.session['signup_data'] = {
            'username': username,
            'email': email,
            'password': pass1
        }

        # Generate and store OTP
        otp = str(random.randint(100000, 999999))
        request.session['otp_data'] = {
            'otp': otp,
            'expiry_time': time.time() + 60  # 1 minute expiry
        }

        # Send OTP email
        send_mail(
            "Account Creation OTP",
            f"Your OTP for account registration is: {otp}",
            "bariqmensfashions@gmail.com",
            [email],
            fail_silently=False
        )

        # Redirect to OTP validation page
        return redirect('verify_otp')

    return render(request, 'user_signup.html')



#------------------------------------------------------------------------------------------------------------------------------#

def User_otp_Vali(request):
    if 'signup_data' not in request.session:
        messages.error(request, 'Please complete the signup form first.')
        return redirect('signup')

    if request.method == 'POST':
        user_otp = request.POST.get('otp')
        otp_data = request.session.get('otp_data', {})
        stored_otp = otp_data.get('otp')
        expiry_time = otp_data.get('expiry_time')

        if time.time() > expiry_time:
            messages.error(request, 'OTP has expired. Please request a new one.')
            return redirect('verify_otp')

        if user_otp == stored_otp:
            signup_data = request.session.get('signup_data', {})
            try:
                user = User.objects.create_user(
                    username=signup_data['username'],
                    email=signup_data['email'],
                    password=signup_data['password']
                )
                messages.success(request, 'Registration successful! You can now log in.')
                request.session.pop('otp_data', None)
                request.session.pop('signup_data', None)
                return redirect('userlogin')
            except Exception as e:
                messages.error(request, 'Error creating account.')
                return render(request, 'user_otp_vali.html')
        else:
            messages.error(request, 'Invalid OTP. Please try again.')
            return render(request, 'user_otp_vali.html')

    return render(request, 'user_otp_vali.html')

#___________________________________________________________________________________________________________________________________#

@require_POST
def resend_otp(request):
    if 'signup_data' not in request.session:
        return JsonResponse({
            'success': False,
            'error': 'No signup in progress.'
        }, status=200)

    signup_data = request.session.get('signup_data')
    email = signup_data.get('email')

    otp_data = request.session.get('otp_data', {})
    otp_expiry_time = otp_data.get('expiry_time')

    current_time = time.time()

    if otp_expiry_time and current_time < otp_expiry_time:
        remaining_time = int(otp_expiry_time - current_time)
        seconds = remaining_time % 60
        return JsonResponse({
            'success': False,
            'error': f'Please wait {seconds} seconds before resending the OTP.'
        }, status=200)

    try:
        otp = str(random.randint(100000, 999999))
        otp_expiry_time = time.time() + 60

        request.session['otp_data'] = {
            'email': email,
            'otp': otp,
            'expiry_time': otp_expiry_time
        }

        send_mail(
            "Account Creation",
            f"Your bariq Account Registration OTP is {otp}. It is valid for 1 minute!",
            "bariqmensfashions@gmail.com",
            [email],
            fail_silently=False
        )

        return JsonResponse({
            'success': True,
            'message': 'A new OTP has been sent to your email.'
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': 'Failed to send OTP. Please try again.'
        }, status=200)


#____________________________________________________________________________________________________________________________________#

def forgot_password(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        if User.objects.filter(email=email).exists():
            otp = str(random.randint(100000, 999999))
            otp_expiry_time = time.time() + 600  # 10 minutes validity

            request.session['reset_otp_data'] = {
                'email': email,
                'otp': otp,
                'expiry_time': otp_expiry_time
            }

            send_mail(
                "Password Reset",
                f"Your password reset OTP is {otp}. It is valid for 10 minutes!",
                "bariqmensfashions@gmail.com",
                [email],
                fail_silently=False
            )

            messages.success(request, 'OTP sent to your email.')
            return redirect('verify_reset_otp')
        else:
            messages.error(request, 'Email not found.')

    return render(request, 'forgot_password.html')


def reset_password(request, email):
    if request.method == 'POST':
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')

        if new_password == confirm_password:
            try:
                user = User.objects.get(email=email)
                user.set_password(new_password)
                user.save()
                messages.success(request, 'Password reset successfully.')
                return redirect('userlogin')
            except User.DoesNotExist:
                messages.error(request, 'User not found.')
                return redirect('forgot_password')
        else:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'reset_password.html', {'email': email})

    return render(request, 'reset_password.html', {'email': email})



#------------------------------------------------------------------------------------------------------------------------------------#

def verify_reset_otp(request):
    if 'reset_otp_data' not in request.session:
        messages.error(request, 'Please request an OTP first.')
        return redirect('forgot_password')

    if request.method == 'POST':
        user_otp = request.POST.get('otp')
        otp_data = request.session.get('reset_otp_data', {})
        stored_otp = otp_data.get('otp')
        expiry_time = otp_data.get('expiry_time')

        if time.time() > expiry_time:
            messages.error(request, 'OTP has expired. Please request a new one.')
            return redirect('verify_reset_otp')

        if user_otp == stored_otp:
            return redirect('reset_password', email=otp_data['email'])
        else:
            messages.error(request, 'Invalid OTP. Please try again.')
            return render(request, 'verify_reset_otp.html')

    return render(request, 'verify_reset_otp.html')



def google_auth_redirect(request):
    return redirect('homepage')



#-----------------------------------------------------------------------------------------------------------------------------------#

def Userlogin(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            messages.success(request, 'You are successfully logged in!')
            return redirect('homepage')
        else:
            messages.error(request, 'Invalid Username or Password')
            return redirect('userlogin')

    return render(request, 'userlogin.html')

def Facebook_Athen(request):
    return render(request, 'facebook.html')


def blocked_user_view(request):
    return render(request,'blocked.html')






#-----------------------------------------------------------------------------------------------------------------------------------#

def bariq_homepage(request):
    category = Category.objects.all()
    categories=category[:5]
    all_products = list(Product.objects.filter(is_active=True, variants__is_active=True).distinct().prefetch_related('variants__images'))

    random.shuffle(all_products)
    featured_products = all_products[:5]

    featured_product_data = []
    for product in featured_products:
        first_variant = product.variants.filter(is_active=True).first()
        first_image = first_variant.images.first() if first_variant else None

        featured_product_data.append({
            'product': product,
            'first_variant': first_variant,
            'first_image': first_image
        })

    context = {
        'categories': categories,  
        'featured_product_data': featured_product_data,  
    }

    return render(request, 'bariqhome.html', context)



 


def product_detail(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    variants = product.variants.filter(is_active=True)
    first_variant = variants.first() if variants.exists() else None

    # Filter related products that have at least one active variant
    related_variant_subquery = ProductVariant.objects.filter(
        product=OuterRef('pk'), is_active=True
    )
    related_products = Product.objects.annotate(
        has_active_variant=Exists(related_variant_subquery)
    ).filter(
        category=product.category,
        is_active=True,
        has_active_variant=True
    ).exclude(id=product_id).order_by('-created_at')[:4]


    active_offer = product.get_active_offer()

    # Debugging
    current_time = now()
    product_offer = product.offers.filter(
        is_active=True, 
        start_date__lte=current_time, 
        end_date__gte=current_time
    ).order_by('-discount_percentage').first()
    category_offer = product.category.offers.filter(
        is_active=True, 
        start_date__lte=current_time, 
        end_date__gte=current_time
    ).order_by('-discount_percentage').first()

    related_products_data = []
    for related_product in related_products:
        related_offer = related_product.get_active_offer()
        related_products_data.append({
            'product': related_product,
            'offer_name': related_offer['offer_name'] if related_offer else None,
            'offer_percentage': related_offer['offer_percentage'] if related_offer else None,
            'discounted_price': related_offer['offer_price'] if related_offer else related_product.price,
        })

    return render(request, 'product_detail.html', {
        'product': product,
        'variants': variants,
        'first_variant': first_variant,
        'related_products_data': related_products_data,
        'offer_name': active_offer['offer_name'] if active_offer else None,
        'offer_percentage': active_offer['offer_percentage'] if active_offer else None,
        'discounted_price': active_offer['offer_price'] if active_offer else product.price,
    })


def Shop_page(request):
    # Only active products with active variants from active categories
    products = Product.objects.filter(
        is_active=True,
        variants__is_active=True,
        category__status='active'
    ).distinct()

    # Filter by category name
    category = request.GET.get('category')
    if category:
        products = products.filter(category__name__iexact=category)

    # Filter by price range
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    try:
        if min_price and max_price:
            min_price = float(min_price)
            max_price = float(max_price)
            products = products.filter(price__gte=min_price, price__lte=max_price)
    except (ValueError, TypeError):
        pass

    # Sorting
    sort = request.GET.get('sort')
    if sort:
        if sort == 'price_asc':
            products = products.order_by('price')
        elif sort == 'price_desc':
            products = products.order_by('-price')
        elif sort == 'name_asc':
            products = products.order_by('name')
        elif sort == 'name_desc':
            products = products.order_by('-name')
        else:
            products = products.order_by('-id')
    else:
        products = products.order_by('-id')

    # Pagination
    paginator = Paginator(products, 10)
    page_number = request.GET.get('page')
    products = paginator.get_page(page_number)

    # Wishlist for authenticated users
    user_wishlist = []
    if request.user.is_authenticated:
        user_wishlist = Wishlist.objects.filter(user=request.user).values_list('product_id', flat=True)

    # 👇 Only active categories shown in filter suggestions
    active_categories = Category.objects.filter(status='active')

    context = {
        'products': products,
        'categories': active_categories,
        'user_wishlist': user_wishlist,
    }

    return render(request, 'shop_page.html', context)

#____________________________________________________________________________________________________________#

def contact(request):
    return render(request,'contact.html')
