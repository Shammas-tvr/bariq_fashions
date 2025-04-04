from django.urls import path
from . import views 


urlpatterns = [
path('wishlist/toggle/', views.toggle_wishlist, name='toggle_wishlist'),
path("wishlist/",views.wishlist_page, name="wishlist_view"),

]