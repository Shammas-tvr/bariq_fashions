from django.urls import path
from . import views 


urlpatterns = [
    path('signup/', views.user_signup, name='signup'),
    path('verify-otp/', views.User_otp_Vali, name='verify_otp'),
    path('resend-otp/', views.resend_otp, name='resend_otp'),
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path('verify-reset-otp/', views.verify_reset_otp, name='verify_reset_otp'),
    path('reset-password/<str:email>/', views.reset_password, name='reset_password'),
    path('userlogin/',views.Userlogin, name='userlogin'),
    path('google-auth-redirect/', views.google_auth_redirect, name='google_auth_redirect'),
    path('facebook-auth/', views.Facebook_Athen, name='facebook_auth'),
    #home page
    path('', views.bariq_homepage, name='homepage'),
    # product detail
    path('product_detail/<int:product_id>/',views. product_detail, name='product_detail'),
    # shop page
    path('shope_page/',views.Shop_page,name='shop_page')

]
