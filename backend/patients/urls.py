from django.urls import path
from .views import *

urlpatterns = [
    path('', patient_list, name='patient_list'),
    path('add/', patient_create, name='patient_add'),  # 🔥 IMPORTANT
    path('edit/<int:id>/', patient_update, name='patient_edit'),
    path('delete/<int:id>/', patient_delete, name='patient_delete'),
]