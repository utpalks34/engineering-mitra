from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', views.home, name='home'),
    path('list/', views.college_list, name='college_list'),
    path('list/partial/', views.college_list, name='college_list_partial'),  # For HTMX
    
    path('<int:college_id>/', views.college_detail, name='college_detail'),
    path('ai-recommendation/', views.ai_recommendation, name='ai_recommendation'),

    path('about/', views.about_view, name='about'),

    
    path('register/', views.register, name='register'),
    path('profile/', views.profile_view, name='profile'),
    
    # Password Change Flow
    path('password_change/', auth_views.PasswordChangeView.as_view(
        template_name='colleges/registration/password_change_form.html'), name='password_change'),
    
    path('password_change/done/', auth_views.PasswordChangeDoneView.as_view(
        template_name='colleges/registration/password_change_done.html'), name='password_change_done'),
]
