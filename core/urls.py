from django.contrib import admin
from django.urls import path, include
from calendar_app import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('calendar_app.urls')), # calendar_appのURLを読み込む
    path('privacy/', views.privacy, name='privacy'),

]