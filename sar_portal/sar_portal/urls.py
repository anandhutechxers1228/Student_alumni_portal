from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from . import views

urlpatterns = [
    path('', views.home_view, name='home'),
    path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('profile/', views.profile_view, name='profile'),
    path('jobs/', views.job_portal_view, name='jobs'),
    path('internships/', views.internship_view, name='internships'),
    path('mentorship/', views.mentorship_view, name='mentorship'),
    path('chat/', views.chat_view, name='chat'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
