from django.shortcuts import render, redirect,get_object_or_404
from django.contrib.auth import authenticate, login,logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required,user_passes_test
from users.models import CustomUser
from django.core.paginator import Paginator
from users.models import CustomUser
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.db.models import Sum
from datetime import timedelta
from django.db.models.functions import ExtractHour, ExtractMonth
from orders.models import Order, OrderItem
from django.utils import timezone




def BariqadminLogin(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            if user.is_staff or user.is_superuser:
                # Log the user in
                login(request, user)
                messages.success(request, 'You have successfully logged in as an admin!')
                return redirect('admin_dashboard')  
            else:
                
                messages.error(request, 'You do not have permission to access the admin panel.')
                return redirect('adminlogin') 
        else:
    
            messages.error(request, 'Invalid username or password.')
            return redirect('adminlogin')  

   
    return render(request, 'adminlogin.html')

def admin_logout(request):
    logout(request)
    return redirect('admin_login')




def is_admin(User):
    return User.is_staff

#_______________________________________________________________________________________________________________________________#
def Admin_Dashboard(request):
    # Get time filter and date range from request
    filter_type = request.GET.get('filter', 'monthly')
    
    # Get custom date range if provided
    start_date_param = request.GET.get('start_date')
    end_date_param = request.GET.get('end_date')
    
    today = timezone.now()  # Use timezone-aware datetime
    
    # Set default dates based on filter type
    if start_date_param and end_date_param:
        # Convert string dates to datetime objects
        try:
            start_date = timezone.make_aware(datetime.strptime(start_date_param, '%Y-%m-%d'))
            end_date = timezone.make_aware(datetime.strptime(end_date_param, '%Y-%m-%d'))
            # Add time to include the entire end day
            end_date = end_date.replace(hour=23, minute=59, second=59)
        except ValueError:
            # Fallback to default dates if parsing fails
            start_date, end_date = get_default_dates(filter_type, today)
    else:
        # Use filter_type to determine date range
        if filter_type == 'daily':
            # Fixed: For daily view, show just today's data
            start_date = today.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = today.replace(hour=23, minute=59, second=59, microsecond=999999)
        elif filter_type == 'weekly':
            # Get start of the current week (Monday)
            start_date = today - timedelta(days=today.weekday())
            start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = today
        elif filter_type == 'yearly':
            start_date = today.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            end_date = today
        else:  # Monthly (default)
            start_date = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end_date = today
    
    # Filtered Orders with proper date range
    orders = Order.objects.filter(order_date__gte=start_date, order_date__lte=end_date)

    # Summary Stats (calculated from filtered orders)
    total_orders = orders.count()
    total_sales = orders.aggregate(total=Sum("total_amount"))["total"] or 0
    total_customers = orders.values("user").distinct().count()

    # Sales Chart Data with proper grouping based on filter type
    if filter_type == 'daily':
        # For daily view, group by hour
        sales_data = (
            orders.annotate(
                hour=ExtractHour('order_date')
            ).values('hour')
            .annotate(
                order_date__date=F('hour'),
                total_sales=Sum("total_amount")
            ).order_by("hour")
        )
    elif filter_type == 'yearly':
        # For yearly view, group by month
        sales_data = (
            orders.annotate(
                month=ExtractMonth('order_date')
            ).values('month')
            .annotate(
                order_date__date=F('month'),
                total_sales=Sum("total_amount")
            ).order_by("month")
        )
    else:
        # For weekly and monthly, group by date
        sales_data = (
            orders.values("order_date__date")
            .annotate(total_sales=Sum("total_amount"))
            .order_by("order_date__date")
        )

    # Best Selling Products
    best_products = (
        OrderItem.objects.filter(order__order_date__gte=start_date, order__order_date__lte=end_date)
        .values("product_variant__product__name")
        .annotate(total_quantity=Sum("quantity"))
        .order_by("-total_quantity")[:5]
    )

    # Best Selling Categories
    best_categories = (
        OrderItem.objects.filter(order__order_date__gte=start_date, order__order_date__lte=end_date)
        .values("product_variant__product__category__name")
        .annotate(total_quantity=Sum("quantity"))
        .order_by("-total_quantity")[:5]
    )

    # Best Selling Brands
    best_brands = (
        OrderItem.objects.filter(order__order_date__gte=start_date, order__order_date__lte=end_date)
        .values("product_variant__product__brand")
        .annotate(total_quantity=Sum("quantity"))
        .order_by("-total_quantity")[:5]
    )

    context = {
        "sales_data": sales_data,
        "best_products": best_products,
        "best_categories": best_categories,
        "best_brands": best_brands,
        "total_orders": total_orders,
        "total_sales": total_sales,
        "total_customers": total_customers,
        "filter_type": filter_type,
        "start_date": start_date,
        "end_date": end_date
    }
    return render(request, "admin-dashboard.html", context)

def get_default_dates(filter_type, today):
    """Helper function to get default date ranges based on filter type"""
    if filter_type == 'daily':
        start_date = today.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = today.replace(hour=23, minute=59, second=59, microsecond=999999)
    elif filter_type == 'weekly':
        start_date = today - timedelta(days=today.weekday())
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = today
    elif filter_type == 'yearly':
        start_date = today.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        end_date = today
    else:  # Monthly (default)
        start_date = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end_date = today
    
    return start_date, end_date         




@login_required
@user_passes_test(is_admin)
def edit_user(request,users_id):
    users=get_object_or_404(CustomUser,id=users_id)
    if request.method == 'POST':
        users.username=request.POST['username']
        users.email=request.POST['email']
        users.is_staff='is_staff' in request.POST
        users.save()
        return redirect('user_management.html')
    return render(request,'user_management.html',{'users':users})


@login_required
@user_passes_test(is_admin)
def block_user(request,users_id):
    users=get_object_or_404(CustomUser,id=users_id)
    users.is_blocked=True
    users.is_active=False
    users.save()
    return redirect('user_management.html')


@login_required
@user_passes_test(is_admin)
def unblock_user(request,users_id):
    users=get_object_or_404(CustomUser,users_id)
    users.is_blocked=False
    users.is_active=True
    users.save()

    return redirect('user_management.html')



@login_required
@user_passes_test(is_admin)
def user_management(request):
    print('Rendering user management view')
    users_list = CustomUser.objects.filter(is_superuser=False).order_by('-date_of_joining')
    paginator = Paginator(users_list, 10)
    page = request.GET.get('page')
    users = paginator.get_page(page)
    context = {
        'users': users,
        'total_users': users_list.count(),
    }
    return render(request, 'user_management.html', context)

@require_POST
def toggle_user_status(request):
    print('Toggling user status')
    user_id = request.POST.get('user_id')
    print(f'User ID: {user_id}')
    user = get_object_or_404(CustomUser, id=user_id)
    user.status = 'blocked' if user.status == 'active' else 'active'
    user.save()
    print(f'New status: {user.status}')
    return JsonResponse({'status': 'success', 'new_status': user.status})


def offers(request):
    return render(request,'offers.html')








#_________________________________________________________________________________________________________________________#


from django.db.models import Sum, Count, F
from django.utils.timezone import now, timedelta
from django.http import HttpResponse
from orders.models import Order
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.units import mm
from decimal import Decimal
import openpyxl
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.utils import get_column_letter

def sales_report(request):
    filter_type = request.GET.get('filter', 'daily')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    today = now().date()

    if filter_type == 'daily':
        start_date, end_date = today, today
    elif filter_type == 'weekly':
        start_date, end_date = today - timedelta(days=7), today
    elif filter_type == 'monthly':
        start_date, end_date = today.replace(day=1), today
    elif filter_type == 'custom' and start_date and end_date:
        pass
    else:
        start_date, end_date = today, today

    orders = Order.objects.filter(order_date__date__range=[start_date, end_date])

    total_sales_count = orders.count()
    total_sales_amount = orders.aggregate(total=Sum('subtotal'))['total'] or 0
    total_product_discount = orders.aggregate(total=Sum('product_discount'))['total'] or 0
    total_coupon_discount = orders.aggregate(total=Sum('coupon_discount'))['total'] or 0
    total_shipping = orders.aggregate(total=Sum('shipping_cost'))['total'] or 0
    net_sales = orders.aggregate(total=Sum('total_amount'))['total'] or 0

    context = {
        'orders': orders,
        'total_sales_count': total_sales_count,
        'total_sales_amount': total_sales_amount,
        'total_product_discount': total_product_discount,
        'total_coupon_discount': total_coupon_discount,
        'total_shipping': total_shipping,
        'net_sales': net_sales,
        'start_date': start_date,
        'end_date': end_date
    }
    return render(request, 'sales_report.html', context)

def download_pdf(request):
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    orders = Order.objects.filter(order_date__date__range=[start_date, end_date])

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Bariq_Fashions_Sales_Report_{start_date}_to_{end_date}.pdf"'
    
    p = canvas.Canvas(response, pagesize=A4)
    width, height = A4

    LEFT_MARGIN = 20 * mm
    TABLE_WIDTH = 170 * mm
    ROW_HEIGHT = 8 * mm
    HEADER_COLOR = colors.HexColor('#2E86C1')
    TOTAL_COLOR = colors.HexColor('#E5E7E9')

    # Header
    p.setFillColor(colors.black)
    p.setFont("Helvetica-Bold", 16)
    p.drawCentredString(width/2, height - 20 * mm, "Bariq Fashions")
    
    p.setFont("Helvetica", 12)
    p.drawCentredString(width/2, height - 28 * mm, f"Sales Report ({start_date} to {end_date})")
    
    p.setFillColor(HEADER_COLOR)
    p.rect(LEFT_MARGIN, height - 48 * mm, TABLE_WIDTH, 8 * mm, fill=1)
    
    # Table Headers
    y_position = height - 48 * mm
    p.setFillColor(colors.white)
    p.setFont("Helvetica-Bold", 10)
    headers = ["Order ID", "Date", "Subtotal (₹)", "Product Discount (₹)", 
              "Coupon Discount (₹)", "Shipping (₹)", "Total (₹)"]
    col_positions = [LEFT_MARGIN, LEFT_MARGIN + 25*mm, LEFT_MARGIN + 50*mm, 
                    LEFT_MARGIN + 75*mm, LEFT_MARGIN + 100*mm, LEFT_MARGIN + 125*mm, 
                    LEFT_MARGIN + 150*mm]
    
    for header, x_pos in zip(headers, col_positions):
        p.drawString(x_pos, y_position + 2*mm, header)

    # Table Data
    y_position = height - 56 * mm
    p.setFillColor(colors.black)
    p.setFont("Helvetica", 10)
    
    total_subtotal = Decimal('0.00')
    total_product_discount = Decimal('0.00')
    total_coupon_discount = Decimal('0.00')
    total_shipping = Decimal('0.00')
    total_amount = Decimal('0.00')

    for order in orders:
        subtotal = order.subtotal
        product_discount = order.product_discount
        coupon_discount = order.coupon_discount
        shipping = order.shipping_cost
        total = order.total_amount

        p.drawString(col_positions[0], y_position, str(order.order_id))
        p.drawString(col_positions[1], y_position, order.order_date.strftime('%Y-%m-%d'))
        p.drawRightString(col_positions[2] + 20*mm, y_position, f"₹{subtotal:,.2f}")
        p.drawRightString(col_positions[3] + 20*mm, y_position, f"₹{product_discount:,.2f}")
        p.drawRightString(col_positions[4] + 20*mm, y_position, f"₹{coupon_discount:,.2f}")
        p.drawRightString(col_positions[5] + 20*mm, y_position, f"₹{shipping:,.2f}")
        p.drawRightString(col_positions[6] + 15*mm, y_position, f"₹{total:,.2f}")

        total_subtotal += subtotal
        total_product_discount += product_discount
        total_coupon_discount += coupon_discount
        total_shipping += shipping
        total_amount += total

        y_position -= ROW_HEIGHT
        if y_position < 20 * mm:
            p.showPage()
            y_position = height - 20 * mm
            p.setFillColor(HEADER_COLOR)
            p.rect(LEFT_MARGIN, y_position, TABLE_WIDTH, 8 * mm, fill=1)
            p.setFillColor(colors.white)
            p.setFont("Helvetica-Bold", 10)
            for header, x_pos in zip(headers, col_positions):
                p.drawString(x_pos, y_position + 2*mm, header)
            y_position -= ROW_HEIGHT
            p.setFillColor(colors.black)
            p.setFont("Helvetica", 10)

    # Totals
    if orders:
        y_position -= 10 * mm
        p.setFillColor(TOTAL_COLOR)
        p.rect(LEFT_MARGIN, y_position, TABLE_WIDTH, 8 * mm, fill=1)
        
        p.setFillColor(colors.black)
        p.setFont("Helvetica-Bold", 10)
        p.drawString(col_positions[0], y_position + 2*mm, "TOTAL")
        p.drawRightString(col_positions[2] + 20*mm, y_position + 2*mm, f"₹{total_subtotal:,.2f}")
        p.drawRightString(col_positions[3] + 20*mm, y_position + 2*mm, f"₹{total_product_discount:,.2f}")
        p.drawRightString(col_positions[4] + 20*mm, y_position + 2*mm, f"₹{total_coupon_discount:,.2f}")
        p.drawRightString(col_positions[5] + 20*mm, y_position + 2*mm, f"₹{total_shipping:,.2f}")
        p.drawRightString(col_positions[6] + 15*mm, y_position + 2*mm, f"₹{total_amount:,.2f}")

    p.showPage()
    p.save()
    return response

def download_excel(request):
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    orders = Order.objects.filter(order_date__date__range=[start_date, end_date])

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sales Report"

    header_font = Font(name='Calibri', size=12, bold=True, color='FFFFFF')
    header_fill = PatternFill(start_color='2E86C1', end_color='2E86C1', fill_type='solid')
    cell_font = Font(name='Calibri', size=11)
    border = Border(left=Side(style='thin'), 
                    right=Side(style='thin'), 
                    top=Side(style='thin'), 
                    bottom=Side(style='thin'))
    center_alignment = Alignment(horizontal='center', vertical='center')
    currency_alignment = Alignment(horizontal='right', vertical='center')

    ws.merge_cells('A1:G1')
    ws['A1'] = f"Bariq Fashions - Sales Report ({start_date} to {end_date})"
    ws['A1'].font = Font(name='Calibri', size=14, bold=True)
    ws['A1'].alignment = center_alignment
    ws.row_dimensions[1].height = 30

    headers = ["Order ID", "Date", "Subtotal (₹)", "Product Discount (₹)", 
              "Coupon Discount (₹)", "Shipping (₹)", "Total (₹)"]
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=3, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.border = border
        cell.alignment = center_alignment

    row_num = 4
    for order in orders:
        ws.append([
            order.order_id,
            order.order_date.date(),
            float(order.subtotal),
            float(order.product_discount),
            float(order.coupon_discount),
            float(order.shipping_cost),
            float(order.total_amount)
        ])
        
        for col in range(1, 8):
            cell = ws.cell(row=row_num, column=col)
            cell.font = cell_font
            cell.border = border
            if col == 2:
                cell.number_format = 'YYYY-MM-DD'
                cell.alignment = center_alignment
            elif col > 2:
                cell.number_format = '#,##0.00'
                cell.alignment = currency_alignment
            else:
                cell.alignment = center_alignment
        row_num += 1

    if orders:
        ws.append(['TOTAL', '', 
                  f'=SUM(C4:C{row_num-1})',
                  f'=SUM(D4:D{row_num-1})',
                  f'=SUM(E4:E{row_num-1})',
                  f'=SUM(F4:F{row_num-1})',
                  f'=SUM(G4:G{row_num-1})'])
        
        total_row = row_num
        for col in range(1, 8):
            cell = ws.cell(row=total_row, column=col)
            cell.font = Font(name='Calibri', size=11, bold=True)
            cell.border = border
            cell.fill = PatternFill(start_color='E5E7E9', end_color='E5E7E9', fill_type='solid')
            if col == 1:
                cell.alignment = center_alignment
            elif col > 2:
                cell.number_format = '#,##0.00'
                cell.alignment = currency_alignment

    column_widths = [15, 12, 15, 15, 15, 15, 15]
    for i, width in enumerate(column_widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = width

    ws.freeze_panes = 'A4'
    ws.sheet_view.showGridLines = True

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="Bariq_Fashions_Sales_Report_{start_date}_to_{end_date}.xlsx"'
    
    wb.save(response)
    return response