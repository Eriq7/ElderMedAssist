from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('api/generate/', views.generate_careplan, name='generate_careplan'),
    path('api/careplans/', views.list_careplans, name='list_careplans'),
]
