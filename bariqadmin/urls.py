from django.urls import path 
from . import views

urlpatterns = [
    path('admin_dashboard/',views.Admin_Dashboard,name='admin_dashboard'),
    path('user_management/', views.user_management, name='user_management'),
    path('toggle_user_status/', views.toggle_user_status, name='toggle_user_status'),

    # offeres
    path('admin_offer/',views.offers,name='offers'),

    # sales report 
    path('sales-report/',views.sales_report,name='sales_report'),
    path('dowload-pdf/',views.download_pdf,name='download_pdf'),
    path('dowload-excel/',views.download_excel,name='download_excel'),

    #admin authendication
    path('adminlogin/',views.BariqadminLogin,name='admin_login'),
    path('admin_logout/',views.admin_logout,name='admin_logout'),
  

]