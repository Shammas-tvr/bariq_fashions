from django.urls import path
from . import views

urlpatterns = [
    # address area
    path('checkout/',views.checkout, name='checkout'),
    path('add-address/',views.add_address, name='add_address'),
    path('delete-address/<int:address_id>/',views.delete_address, name='delete_address'),
    path('address/edit/<int:address_id>/',views.edit_address, name='edit_address'),
    path('address/set-default/',views.set_default_address, name='set_default_address'), 

    #payment
    path('payment',views.payment_page,name='payment'),
    path('process-payment/',views.process_payment, name='process_payment'),
    path('verify-payment/',views.verify_payment, name='verify_payment'), 
    path('order-failure/<str:order_id>/', views.order_failure, name='order_failure'),

    #order confiramation
    path('order-success/<str:order_id>/', views.order_success, name='order_success'),
    path('retry-payment/<str:order_id>/', views.retry_payment, name='retry_payment'),

    # order detail in admin side
    path('admin-order/<str:order_id>/', views.admin_order_detail, name='admin_order_detail'),
    path('my-orders/', views.admin_order_list, name='order-list'),
    path('order/<str:order_id>/item/<int:item_id>/update-status/', views.admin_update_order_item_status, name='update_order_item_status'),

    # coupons
    path('coupon/edit/<int:coupon_id>/', views.coupon_edit, name='coupon_edit'),
    path('coupon/toggle/<int:coupon_id>/', views.toggle_coupon_status, name='toggle_coupon_status'),
    path('coupon/create/', views.create_coupon, name='create_coupon'),
    path('coupon-list/', views.coupon_list, name='coupon_list'),

    #invoice
    path('order-invoice/<str:order_id>/', views.admin_invoice, name='invoice'),



]
