# calendar_app/urls.py

from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('authorize/', views.authorize, name='authorize'),
    path('oauth2callback/', views.oauth2callback, name='oauth2callback'),
    path('logout/', views.logout_view, name='logout'),
    path('upload/', views.upload_file, name='upload_file'),
    path('register-events/', views.register_events, name='register_events'),
    path('privacy/', views.privacy, name='privacy'), 
]