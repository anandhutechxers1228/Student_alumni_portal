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
    path('search/', views.search_view, name='search'),
    path('users/<str:user_id>/', views.user_profile_view, name='user_profile'),
    path('profile/', views.profile_view, name='profile'),
    path('jobs/', views.job_portal_view, name='jobs'),
    path('jobs/add/', views.job_add_view, name='job_add'),
    path('jobs/mine/', views.job_mine_view, name='job_mine'),
    path('jobs/edit/<str:job_id>/', views.job_edit_view, name='job_edit'),
    path('jobs/<str:job_id>/', views.job_detail_view, name='job_detail'),
    path('internships/', views.internship_view, name='internships'),
    path('internships/add/', views.internship_add_view, name='internship_add'),
    path('internships/edit/<str:internship_id>/', views.internship_edit_view, name='internship_edit'),
    path('internships/delete/<str:internship_id>/', views.internship_delete_view, name='internship_delete'),
    path('internships/mine/', views.internship_mine_view, name='internship_mine'),
    path('internships/<str:internship_id>/', views.internship_detail_view, name='internship_detail'),
    path('mentorship/', views.mentorship_view, name='mentorship'),
    path('mentorship/vote/', views.mentorship_vote_view, name='mentorship_vote'),
    path('mentorship/<str:question_id>/', views.mentorship_question_view, name='mentorship_question'),
    path('chat/', views.chat_view, name='chat'),
    path('chat/api/unread/', views.chat_unread_api, name='chat_unread_api'),
    path('chat/api/messages/<str:room_id>/', views.chat_messages_api, name='chat_messages_api'),
    path('chat/<str:other_user_id>/', views.chat_room_view, name='chat_room'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
