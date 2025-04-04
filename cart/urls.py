from django.urls import path
from . import views


urlpatterns = [
    path('cart/add/<int:variant_id>/',views.add_to_cart, name='add_to_cart'),
    path('cart_view/', views.cart_view, name='cart_view'),
    path('update-cart-item/<int:item_id>/',views.update_cart_item, name='update_cart_item'),
    path('cart/remove/<int:item_id>/',views.remove_cart_item, name='remove_cart_item'),

    # wallet
    path('user-wallet/',views.user_wallet_view,name='wallet_view'),


    # wallet admin side 
path('admin_wallet_transactions/', views.wallet_transaction_list, name='admin_transaction_list'),
path('admin_wallet_transaction/<str:transaction_id>/', views.wallet_transaction_detail, name='admin_transaction_detail'),
]
