from django.shortcuts import render, redirect
from django.contrib.auth.hashers import make_password, check_password
from django.conf import settings
from .db_connector import get_db
from bson import ObjectId
import os
import uuid


STREAMS = [
    'Computer Science',
    'Electronics and Communication',
    'Electrical',
    'Instrumentation',
]


def login_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.session.get('user_id'):
            return redirect('/login/')
        return view_func(request, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper


def get_current_user(request):
    uid = request.session.get('user_id')
    if not uid:
        return None
    db = get_db()
    user = db.sar_users.find_one({'_id': ObjectId(uid)})
    if user:
        user['id'] = str(user['_id'])
    return user


def home_view(request):
    user = get_current_user(request) if request.session.get('user_id') else None
    return render(request, 'home.html', {'user': user})


def signup_view(request):
    if request.session.get('user_id'):
        return redirect('/dashboard/')
    error = None
    if request.method == 'POST':
        db = get_db()
        email = request.POST.get('email', '').lower().strip()
        existing = db.sar_users.find_one({'email': email})
        if existing:
            error = 'An account with this email already exists.'
        else:
            status = request.POST.get('status', 'student')
            user_doc = {
                'name': request.POST.get('name', '').strip(),
                'email': email,
                'phone': request.POST.get('phone', '').strip(),
                'admission_year': request.POST.get('admission_year', '').strip(),
                'stream': request.POST.get('stream', ''),
                'status': status,
                'gender': request.POST.get('gender', ''),
                'password': make_password(request.POST.get('password', '')),
                'profile_pic': '',
            }
            if status == 'student':
                user_doc['current_year'] = request.POST.get('current_year', '')
            result = db.sar_users.insert_one(user_doc)
            request.session['user_id'] = str(result.inserted_id)
            return redirect('/')
    return render(request, 'signup.html', {'error': error, 'streams': STREAMS})


def login_view(request):
    if request.session.get('user_id'):
        return redirect('/dashboard/')
    error = None
    if request.method == 'POST':
        email = request.POST.get('email', '').lower().strip()
        password = request.POST.get('password', '')
        db = get_db()
        user = db.sar_users.find_one({'email': email})
        if user and check_password(password, user['password']):
            request.session['user_id'] = str(user['_id'])
            return redirect('/')
        error = 'Invalid email or password.'
    return render(request, 'login.html', {'error': error})


def logout_view(request):
    request.session.flush()
    return redirect('/login/')


@login_required
def dashboard_view(request):
    return redirect('/')


@login_required
def profile_view(request):
    user = get_current_user(request)
    success = None
    error = None

    if request.method == 'POST':
        action = request.POST.get('action')
        db = get_db()
        uid = ObjectId(request.session['user_id'])

        if action == 'update_profile':
            status = request.POST.get('status', user.get('status', 'student'))
            update_data = {
                'name': request.POST.get('name', '').strip(),
                'phone': request.POST.get('phone', '').strip(),
                'admission_year': request.POST.get('admission_year', '').strip(),
                'stream': request.POST.get('stream', ''),
                'status': status,
                'gender': request.POST.get('gender', ''),
            }
            if status == 'student':
                update_data['current_year'] = request.POST.get('current_year', '')

            if 'profile_pic' in request.FILES:
                pic = request.FILES['profile_pic']
                ext = os.path.splitext(pic.name)[1].lower()
                filename = f"{uuid.uuid4().hex}{ext}"
                save_dir = os.path.join(settings.MEDIA_ROOT, 'profile_pics')
                os.makedirs(save_dir, exist_ok=True)
                filepath = os.path.join(save_dir, filename)
                with open(filepath, 'wb+') as f:
                    for chunk in pic.chunks():
                        f.write(chunk)
                if user.get('profile_pic'):
                    old_path = os.path.join(settings.MEDIA_ROOT, user['profile_pic'])
                    if os.path.exists(old_path):
                        os.remove(old_path)
                update_data['profile_pic'] = f'profile_pics/{filename}'

            db.sar_users.update_one({'_id': uid}, {'$set': update_data})
            success = 'Profile updated successfully.'
            user = get_current_user(request)

        elif action == 'change_password':
            old_pw = request.POST.get('old_password', '')
            new_pw = request.POST.get('new_password', '')
            if check_password(old_pw, user['password']):
                db.sar_users.update_one({'_id': uid}, {'$set': {'password': make_password(new_pw)}})
                success = 'Password changed successfully.'
            else:
                error = 'Current password is incorrect.'

    return render(request, 'profile.html', {
        'user': user,
        'success': success,
        'error': error,
        'streams': STREAMS,
    })


@login_required
def job_portal_view(request):
    user = get_current_user(request)
    return render(request, 'job_portal.html', {'user': user})


@login_required
def internship_view(request):
    user = get_current_user(request)
    return render(request, 'internship.html', {'user': user})


@login_required
def mentorship_view(request):
    user = get_current_user(request)
    return render(request, 'mentorship.html', {'user': user})


@login_required
def chat_view(request):
    user = get_current_user(request)
    return render(request, 'chat.html', {'user': user})
