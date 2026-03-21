from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('calendar_app.urls')), # calendar_appのURLを読み込む
]