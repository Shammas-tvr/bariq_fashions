from django.urls import path
from . import views

urlpatterns = [
    #user profile
    path('user_profile', views.user_profile, name='user_profile'),
    path('profile/update/', views.update_profile, name='update_profile'),
    path('profile/change-password/', views.change_password, name='change_password'),


    
    #logout
    path('logout/', views.logout_view, name='user_logout'),

    # address area
    path('addresses/', views.address_list, name='address_list'),
    path('addresses/add/', views.profile_add_address, name='profile_add_address'),
    path('addresses/edit/<int:address_id>/', views.profile_edit_address, name='profile_edit_address'),
    path('addresses/delete/<int:address_id>/', views.profile_delete_address, name='profile_delete_address'),

    #order area
    path('order/cancel-item/<str:order_id>/<int:item_id>/', views.cancel_order_item, name='cancel_order_item'),
    path('order-history/', views.order_history, name='order_history'),
    path("order/<str:order_id>/", views.order_detail, name="order_details"),
    path("orders/<str:order_id>/items/<int:item_id>/tracking/", views.order_item_tracking, name='track_item_order'),
        # order return
    path('order/<str:order_id>/return/<int:item_id>/',views.request_order_return, name='request_order_return'),
    path('order/<str:order_id>/submit-return/', views.submit_order_return, name='submit_order_return'),

      #order invoice 
    path('user_invoice/<str:order_id>/',views.user_invoice,name='user_invoice'), 
      
    
    # search area
    path('ajax-search/',views.ajax_search, name='ajax_search'),
]