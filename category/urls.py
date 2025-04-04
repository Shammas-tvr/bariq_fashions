from django.conf import settings
from django.conf.urls.static import static
from django.urls import path
from . import views

urlpatterns = [
    path('categories/', views.category_list, name='category_list'),
    path('categories/add/', views.category_add, name='category_add'),
    path('categories/edit/<int:category_id>/', views.category_edit, name='category_edit'),
    path('toggle_category_status/', views.toggle_category_status, name='toggle_category_status'),

    #category offer section 

    path('category-offer-list/',views.category_offer_list,name='category_offer_list'),
    path('category-offer-add/',views.add_category_offer,name='add_category_offer'),
    path('edit-offer/<int:offer_id>/',views.edit_category_offer,name='edit_category_offer'),
    path('offer/toggle/<int:offer_id>/',views.toggle_category_offer_status,name='toggle_category_offer_status')
    
]

# if settings.DEBUG:
#     urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
