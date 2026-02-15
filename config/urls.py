from django.urls import path, include

urlpatterns = [
    path('', include('careplan.urls')),
]
