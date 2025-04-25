from django.urls import path
from . import views

urlpatterns = [
    path('products/', views.product_management, name='product_list'),
    path('products_add/', views.add_product, name='add_product'),
    path('toggle_product_status/', views.toggle_product_status, name='toggle_product_status'),
    path('products_edit/<int:product_id>/', views.edit_product, name='edit_product'),
    # Variant Management
    path('products/<int:product_id>/variants/', views.variant_list, name='variant_list'),
    path('products/<int:product_id>/add_variant/', views.add_variant, name='add_variant'),
    path('product/<int:product_id>/variant/<int:variant_id>/edit/', views.edit_variant, name='edit_variant'),
    path('toggle_variant_status/', views.toggle_variant_status, name='toggle_variant_status'),

    #product offer
    path('offers/',views.product_offer_list, name='product_offer_list'),
    path('offers/add/',views.add_product_offer, name='add_product_offer'),
    path('offers/edit/<int:offer_id>/',views.edit_product_offer, name='edit_product_offer'),
    path('offer/<int:offer_id>/toggle/', views.toggle_product_offer_status, name='toggle_product_offer_status'),

]

