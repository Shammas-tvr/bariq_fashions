from django.urls import path 
from . import views

urlpatterns = [
    path('adminlogin/',views.BariqadminLogin,name='adminlogin'),
    path('admin_dashboard/',views.Admin_Dashboard,name='admin_dashboard'),
    path('add-user/',views.add_user, name='add_user'),
    path('edit-user/<int:users_id>/',views.edit_user, name='edit_user'),
    path('block-user/<int:users_id>/',views.block_user, name='block_user'),
    path('unblock-user/<int:users_id>/',views.unblock_user, name='unblock_user'),
    path('user_management/', views.user_management, name='user_management'),
    path('toggle_user_status/', views.toggle_user_status, name='toggle_user_status'),

    # offeres
    path('admin_offer/',views.offers,name='offers'),

    # sales report 
    path('sales-report/',views.sales_report,name='sales_report'),
    path('dowload-pdf/',views.download_pdf,name='download_pdf'),
    path('dowload-excel/',views.download_excel,name='download_excel'),
  

]