from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib.auth.hashers import make_password, check_password
from django.conf import settings
from .db_connector import get_db
from bson import ObjectId
import os
import uuid
from datetime import datetime, timezone, timedelta
import json


STREAMS = [
    'Computer Science',
    'Electronics and Communication',
    'Electrical',
    'Instrumentation',
]

IST = timezone(timedelta(hours=5, minutes=30))


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
                'skills': [],
            }
            if status == 'student':
                user_doc['current_year'] = request.POST.get('current_year', '')
                user_doc['achievements'] = []
                user_doc['startup'] = None
            else:
                user_doc['current_status'] = ''
                user_doc['current_company_name'] = ''
                user_doc['current_company_year'] = ''
                user_doc['previously_owned'] = []
                user_doc['experience'] = []
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
def search_view(request):
    q = request.GET.get('q', '').strip()
    if len(q) < 4:
        return JsonResponse({'users': []})
    db = get_db()
    users = list(db.sar_users.find(
        {'name': {'$regex': q, '$options': 'i'}},
        {'name': 1, 'stream': 1, 'status': 1, 'profile_pic': 1, 'admission_year': 1}
    ).limit(12))
    result = []
    for u in users:
        result.append({
            'id': str(u['_id']),
            'name': u.get('name', ''),
            'stream': u.get('stream', ''),
            'status': u.get('status', ''),
            'profile_pic': u.get('profile_pic', ''),
            'admission_year': u.get('admission_year', ''),
        })
    return JsonResponse({'users': result})


@login_required
def user_profile_view(request, user_id):
    current_user = get_current_user(request)
    if user_id == current_user['id']:
        return redirect('/profile/')
    db = get_db()
    try:
        profile_user = db.sar_users.find_one({'_id': ObjectId(user_id)})
    except Exception:
        return redirect('/dashboard/')
    if not profile_user:
        return redirect('/dashboard/')
    profile_user['id'] = str(profile_user['_id'])
    return render(request, 'user_profile.html', {'user': current_user, 'profile_user': profile_user})


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
                db.sar_notifications.insert_one({
                    'user_id': user['id'],
                    'type': 'password_changed',
                    'title': 'Password Changed',
                    'message': 'Your account password was changed successfully.',
                    'link': '/profile/',
                    'reference_id': '',
                    'read': False,
                    'created_at': datetime.utcnow(),
                })
                success = 'Password changed successfully.'
            else:
                error = 'Current password is incorrect.'

        elif action == 'update_full_profile':
            try:
                skills = json.loads(request.POST.get('skills_json', '[]'))
            except Exception:
                skills = []

            update_data = {'skills': skills}

            if user.get('status') == 'alumni':
                update_data['current_status'] = request.POST.get('current_status', '')
                update_data['current_company_name'] = request.POST.get('current_company_name', '').strip()
                update_data['current_company_year'] = request.POST.get('current_company_year', '').strip()
                try:
                    previously_owned = json.loads(request.POST.get('previously_owned_json', '[]'))
                except Exception:
                    previously_owned = []
                update_data['previously_owned'] = previously_owned
                try:
                    experience = json.loads(request.POST.get('experience_json', '[]'))
                except Exception:
                    experience = []
                update_data['experience'] = experience

            elif user.get('status') == 'student':
                try:
                    achievements = json.loads(request.POST.get('achievements_json', '[]'))
                except Exception:
                    achievements = []
                update_data['achievements'] = achievements
                has_startup = request.POST.get('has_startup', 'no')
                if has_startup == 'yes':
                    update_data['startup'] = {
                        'name': request.POST.get('startup_name', '').strip(),
                        'started_year': request.POST.get('startup_started_year', '').strip(),
                        'description': request.POST.get('startup_description', '').strip(),
                    }
                else:
                    update_data['startup'] = None

            db.sar_users.update_one({'_id': uid}, {'$set': update_data})
            success = 'Full profile updated successfully.'
            user = get_current_user(request)

    user['previously_owned_json_str'] = json.dumps(user.get('previously_owned', []))
    user['experience_json_str'] = json.dumps(user.get('experience', []))
    user['skills_json_str'] = json.dumps(user.get('skills', []))
    user['achievements_json_str'] = json.dumps(user.get('achievements', []))

    return render(request, 'profile.html', {
        'user': user,
        'success': success,
        'error': error,
        'streams': STREAMS,
    })


@login_required
def job_portal_view(request):
    user = get_current_user(request)
    db = get_db()
    if user.get('status') == 'alumni':
        jobs = list(db.sar_jobs.find({'posted_by': {'$ne': user['id']}}).sort('posted_at', -1))
    else:
        jobs = list(db.sar_jobs.find({}).sort('posted_at', -1))
    user_applied = set(a['job_id'] for a in db.sar_job_applications.find({'applicant_id': user['id']}, {'job_id': 1}))
    for j in jobs:
        j['id'] = str(j['_id'])
        if 'posted_at' in j and j['posted_at']:
            j['posted_at_str'] = j['posted_at'].strftime('%b %d, %Y')
        else:
            j['posted_at_str'] = ''
        j['has_applied'] = j['id'] in user_applied
        j['closed'] = j.get('closed', False)
    return render(request, 'job_portal.html', {'user': user, 'jobs': jobs})


@login_required
def job_detail_view(request, job_id):
    user = get_current_user(request)
    db = get_db()
    try:
        job = db.sar_jobs.find_one({'_id': ObjectId(job_id)})
    except Exception:
        return redirect('/jobs/')
    if not job:
        return redirect('/jobs/')
    job['id'] = str(job['_id'])
    if 'posted_at' in job and job['posted_at']:
        job['posted_at_str'] = job['posted_at'].strftime('%b %d, %Y')
    else:
        job['posted_at_str'] = ''
    job['closed'] = job.get('closed', False)
    job['applicant_count'] = db.sar_job_applications.count_documents({'job_id': job['id']})
    if user['id'] != job.get('posted_by'):
        existing_app = db.sar_job_applications.find_one({'job_id': job['id'], 'applicant_id': user['id']})
        job['has_applied'] = existing_app is not None
    else:
        job['has_applied'] = False
    return render(request, 'job_detail.html', {'user': user, 'job': job})


@login_required
def job_apply_view(request, job_id):
    if request.method != 'POST':
        return redirect('/jobs/')
    user = get_current_user(request)
    db = get_db()
    try:
        job = db.sar_jobs.find_one({'_id': ObjectId(job_id)})
    except Exception:
        return redirect('/jobs/')
    if not job:
        return redirect('/jobs/')
    job_id_str = str(job['_id'])
    if job.get('posted_by') == user['id'] or job.get('closed'):
        return redirect(f'/jobs/{job_id_str}/')
    existing = db.sar_job_applications.find_one({'job_id': job_id_str, 'applicant_id': user['id']})
    if existing:
        db.sar_job_applications.delete_one({'_id': existing['_id']})
    else:
        now = datetime.utcnow()
        db.sar_job_applications.insert_one({
            'job_id': job_id_str,
            'job_title': job.get('title', ''),
            'applicant_id': user['id'],
            'applicant_name': user['name'],
            'applicant_pic': user.get('profile_pic', ''),
            'applied_at': now,
        })
        db.sar_notifications.insert_one({
            'user_id': job.get('posted_by', ''),
            'type': 'job_application',
            'title': 'New Job Application',
            'message': f"{user['name']} applied to your job: {job.get('title', '')}",
            'link': f'/jobs/applicants/{job_id_str}/',
            'job_title': job.get('title', ''),
            'reference_id': job_id_str,
            'read': False,
            'created_at': now,
        })
    return redirect(f'/jobs/{job_id_str}/')


@login_required
def job_applied_view(request):
    user = get_current_user(request)
    db = get_db()
    applications = list(db.sar_job_applications.find({'applicant_id': user['id']}).sort('applied_at', -1))
    jobs = []
    for app in applications:
        try:
            job = db.sar_jobs.find_one({'_id': ObjectId(app['job_id'])})
        except Exception:
            continue
        if not job:
            continue
        job['id'] = str(job['_id'])
        if 'posted_at' in job and job['posted_at']:
            job['posted_at_str'] = job['posted_at'].strftime('%b %d, %Y')
        else:
            job['posted_at_str'] = ''
        job['applied_at_str'] = app['applied_at'].strftime('%b %d, %Y') if app.get('applied_at') else ''
        job['closed'] = job.get('closed', False)
        jobs.append(job)
    return render(request, 'job_applied.html', {'user': user, 'jobs': jobs})


@login_required
def job_applicants_view(request, job_id):
    user = get_current_user(request)
    db = get_db()
    try:
        job = db.sar_jobs.find_one({'_id': ObjectId(job_id), 'posted_by': user['id']})
    except Exception:
        return redirect('/jobs/')
    if not job:
        return redirect('/jobs/')
    job['id'] = str(job['_id'])
    applications = list(db.sar_job_applications.find({'job_id': job['id']}).sort('applied_at', -1))
    for app in applications:
        app['id'] = str(app['_id'])
        app['applied_at_str'] = app['applied_at'].strftime('%b %d, %Y') if app.get('applied_at') else ''
    return render(request, 'job_applicants.html', {'user': user, 'job': job, 'applications': applications})


@login_required
def job_toggle_close_view(request, job_id):
    if request.method != 'POST':
        return redirect('/jobs/')
    user = get_current_user(request)
    db = get_db()
    try:
        job = db.sar_jobs.find_one({'_id': ObjectId(job_id), 'posted_by': user['id']})
    except Exception:
        return redirect('/jobs/')
    if not job:
        return redirect('/jobs/')
    db.sar_jobs.update_one({'_id': ObjectId(job_id)}, {'$set': {'closed': not job.get('closed', False)}})
    return redirect(f'/jobs/{job_id}/')


@login_required
def job_add_view(request):
    user = get_current_user(request)
    if user.get('status') != 'alumni':
        return redirect('/jobs/')
    error = None
    if request.method == 'POST':
        db = get_db()
        try:
            eligibility = json.loads(request.POST.get('eligibility_json', '[]'))
        except Exception:
            eligibility = []
        try:
            locations = json.loads(request.POST.get('locations_json', '[]'))
        except Exception:
            locations = []

        job_doc = {
            'title': request.POST.get('title', '').strip(),
            'description': request.POST.get('description', '').strip(),
            'company_name': request.POST.get('company_name', '').strip(),
            'company_description': request.POST.get('company_description', '').strip(),
            'eligibility': eligibility,
            'locations': locations,
            'experience_required': request.POST.get('experience_required', '').strip(),
            'salary': request.POST.get('salary', '').strip(),
            'image': '',
            'posted_by': user['id'],
            'posted_by_name': user['name'],
            'posted_at': datetime.utcnow(),
            'closed': False,
        }

        if 'job_image' in request.FILES:
            img = request.FILES['job_image']
            ext = os.path.splitext(img.name)[1].lower()
            filename = f"{uuid.uuid4().hex}{ext}"
            save_dir = os.path.join(settings.MEDIA_ROOT, 'job_images')
            os.makedirs(save_dir, exist_ok=True)
            with open(os.path.join(save_dir, filename), 'wb+') as f:
                for chunk in img.chunks():
                    f.write(chunk)
            job_doc['image'] = f'job_images/{filename}'

        inserted = db.sar_jobs.insert_one(job_doc)
        job_id_str = str(inserted.inserted_id)
        now = datetime.utcnow()
        all_users = list(db.sar_users.find({'_id': {'$ne': ObjectId(user['id'])}}, {'_id': 1}))
        notif_docs = [{
            'user_id': str(u['_id']),
            'type': 'new_job',
            'title': 'New Job Posted',
            'message': f"A new job '{job_doc['title']}' has been posted by {user['name']}",
            'link': f'/jobs/{job_id_str}/',
            'reference_id': job_id_str,
            'read': False,
            'created_at': now,
        } for u in all_users]
        if notif_docs:
            db.sar_notifications.insert_many(notif_docs)
        return redirect('/jobs/mine/')
    return render(request, 'job_add.html', {'user': user, 'error': error})


@login_required
def job_mine_view(request):
    user = get_current_user(request)
    if user.get('status') != 'alumni':
        return redirect('/jobs/')
    db = get_db()
    jobs = list(db.sar_jobs.find({'posted_by': user['id']}).sort('posted_at', -1))
    for j in jobs:
        j['id'] = str(j['_id'])
        if 'posted_at' in j and j['posted_at']:
            j['posted_at_str'] = j['posted_at'].strftime('%b %d, %Y')
        else:
            j['posted_at_str'] = ''
        j['closed'] = j.get('closed', False)
        j['applicant_count'] = db.sar_job_applications.count_documents({'job_id': j['id']})
    return render(request, 'job_mine.html', {'user': user, 'jobs': jobs})


@login_required
def job_edit_view(request, job_id):
    user = get_current_user(request)
    if user.get('status') != 'alumni':
        return redirect('/jobs/')
    db = get_db()
    try:
        job = db.sar_jobs.find_one({'_id': ObjectId(job_id), 'posted_by': user['id']})
    except Exception:
        return redirect('/jobs/mine/')
    if not job:
        return redirect('/jobs/mine/')
    job['id'] = str(job['_id'])
    error = None

    if request.method == 'POST':
        try:
            eligibility = json.loads(request.POST.get('eligibility_json', '[]'))
        except Exception:
            eligibility = []
        try:
            locations = json.loads(request.POST.get('locations_json', '[]'))
        except Exception:
            locations = []

        update_data = {
            'title': request.POST.get('title', '').strip(),
            'description': request.POST.get('description', '').strip(),
            'company_name': request.POST.get('company_name', '').strip(),
            'company_description': request.POST.get('company_description', '').strip(),
            'eligibility': eligibility,
            'locations': locations,
            'experience_required': request.POST.get('experience_required', '').strip(),
            'salary': request.POST.get('salary', '').strip(),
        }

        if 'job_image' in request.FILES:
            img = request.FILES['job_image']
            ext = os.path.splitext(img.name)[1].lower()
            filename = f"{uuid.uuid4().hex}{ext}"
            save_dir = os.path.join(settings.MEDIA_ROOT, 'job_images')
            os.makedirs(save_dir, exist_ok=True)
            with open(os.path.join(save_dir, filename), 'wb+') as f:
                for chunk in img.chunks():
                    f.write(chunk)
            if job.get('image'):
                old_path = os.path.join(settings.MEDIA_ROOT, job['image'])
                if os.path.exists(old_path):
                    os.remove(old_path)
            update_data['image'] = f'job_images/{filename}'

        db.sar_jobs.update_one({'_id': ObjectId(job_id)}, {'$set': update_data})
        return redirect('/jobs/mine/')

    job['eligibility_json'] = json.dumps(job.get('eligibility', []))
    job['locations_json'] = json.dumps(job.get('locations', []))
    return render(request, 'job_edit.html', {'user': user, 'job': job, 'error': error})


@login_required
def internship_view(request):
    user = get_current_user(request)
    db = get_db()
    profiles = list(db.sar_internship_profiles.find({'student_id': {'$ne': user['id']}}).sort('created_at', -1))
    for p in profiles:
        p['id'] = str(p['_id'])
        if 'created_at' in p and p['created_at']:
            p['created_at_str'] = p['created_at'].strftime('%b %d, %Y')
        else:
            p['created_at_str'] = ''
        try:
            poster = db.sar_users.find_one({'_id': ObjectId(p['student_id'])}, {'name': 1, 'profile_pic': 1})
            p['poster_pic'] = poster.get('profile_pic', '') if poster else ''
        except Exception:
            p['poster_pic'] = ''
    return render(request, 'internship.html', {'user': user, 'profiles': profiles})


@login_required
def internship_detail_view(request, internship_id):
    user = get_current_user(request)
    db = get_db()
    try:
        profile = db.sar_internship_profiles.find_one({'_id': ObjectId(internship_id)})
    except Exception:
        return redirect('/internships/')
    if not profile:
        return redirect('/internships/')
    profile['id'] = str(profile['_id'])
    if 'created_at' in profile and profile['created_at']:
        profile['created_at_str'] = profile['created_at'].strftime('%b %d, %Y')
    else:
        profile['created_at_str'] = ''
    if 'updated_at' in profile and profile['updated_at']:
        profile['updated_at_str'] = profile['updated_at'].strftime('%b %d, %Y')
    else:
        profile['updated_at_str'] = ''
    try:
        poster = db.sar_users.find_one({'_id': ObjectId(profile['student_id'])}, {'name': 1, 'profile_pic': 1})
        if poster:
            profile['poster_name'] = poster.get('name', profile.get('student_name', ''))
            profile['poster_pic'] = poster.get('profile_pic', '')
            profile['poster_id'] = str(poster['_id'])
        else:
            profile['poster_name'] = profile.get('student_name', '')
            profile['poster_pic'] = ''
            profile['poster_id'] = profile.get('student_id', '')
    except Exception:
        profile['poster_name'] = profile.get('student_name', '')
        profile['poster_pic'] = ''
        profile['poster_id'] = profile.get('student_id', '')
    has_interested = False
    if user.get('status') == 'alumni' and user['id'] != profile.get('student_id'):
        has_interested = db.sar_internship_interests.find_one({
            'internship_id': profile['id'],
            'alumni_id': user['id'],
        }) is not None
    return render(request, 'internship_detail.html', {'user': user, 'profile': profile, 'has_interested': has_interested})


@login_required
def internship_add_view(request):
    user = get_current_user(request)
    db = get_db()
    count = db.sar_internship_profiles.count_documents({'student_id': user['id']})
    if count >= 5:
        return redirect('/internships/mine/')
    error = None

    if request.method == 'POST':
        try:
            skills = json.loads(request.POST.get('skills_json', '[]'))
        except Exception:
            skills = []
        try:
            languages = json.loads(request.POST.get('languages_json', '[]'))
        except Exception:
            languages = []
        try:
            relocatable_locations = json.loads(request.POST.get('relocatable_json', '[]'))
        except Exception:
            relocatable_locations = []

        profile_doc = {
            'student_id': user['id'],
            'student_name': user['name'],
            'role_title': request.POST.get('role_title', '').strip(),
            'name': request.POST.get('name', '').strip(),
            'current_location': request.POST.get('current_location', '').strip(),
            'relocatable_locations': relocatable_locations,
            'skills': skills,
            'languages': languages,
            'description': request.POST.get('description', '').strip(),
            'stream': user.get('stream', ''),
            'admission_year': user.get('admission_year', ''),
            'current_year': user.get('current_year', '') if user.get('status') == 'student' else 'Alumni',
            'user_status': user.get('status', 'student'),
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow(),
        }
        inserted = db.sar_internship_profiles.insert_one(profile_doc)
        internship_id_str = str(inserted.inserted_id)
        now = datetime.utcnow()
        alumni_users = list(db.sar_users.find({'status': 'alumni', '_id': {'$ne': ObjectId(user['id'])}}, {'_id': 1}))
        notif_docs = [{
            'user_id': str(u['_id']),
            'type': 'new_internship',
            'title': 'New Internship Profile',
            'message': f"A new internship profile '{profile_doc['name']}' has been posted by {user['name']}",
            'link': f'/internships/{internship_id_str}/',
            'reference_id': internship_id_str,
            'read': False,
            'created_at': now,
        } for u in alumni_users]
        if notif_docs:
            db.sar_notifications.insert_many(notif_docs)
        return redirect('/internships/mine/')

    return render(request, 'internship_add.html', {'user': user, 'existing': None, 'error': error, 'count': count})


@login_required
def internship_edit_view(request, internship_id):
    user = get_current_user(request)
    db = get_db()
    try:
        existing = db.sar_internship_profiles.find_one({'_id': ObjectId(internship_id), 'student_id': user['id']})
    except Exception:
        return redirect('/internships/mine/')
    if not existing:
        return redirect('/internships/mine/')
    existing['id'] = str(existing['_id'])
    existing['skills_json'] = json.dumps(existing.get('skills', []))
    existing['languages_json'] = json.dumps(existing.get('languages', []))
    existing['relocatable_json'] = json.dumps(existing.get('relocatable_locations', []))
    error = None

    if request.method == 'POST':
        try:
            skills = json.loads(request.POST.get('skills_json', '[]'))
        except Exception:
            skills = []
        try:
            languages = json.loads(request.POST.get('languages_json', '[]'))
        except Exception:
            languages = []
        try:
            relocatable_locations = json.loads(request.POST.get('relocatable_json', '[]'))
        except Exception:
            relocatable_locations = []

        profile_doc = {
            'role_title': request.POST.get('role_title', '').strip(),
            'name': request.POST.get('name', '').strip(),
            'current_location': request.POST.get('current_location', '').strip(),
            'relocatable_locations': relocatable_locations,
            'skills': skills,
            'languages': languages,
            'description': request.POST.get('description', '').strip(),
            'stream': user.get('stream', ''),
            'admission_year': user.get('admission_year', ''),
            'current_year': user.get('current_year', '') if user.get('status') == 'student' else 'Alumni',
            'updated_at': datetime.utcnow(),
        }
        db.sar_internship_profiles.update_one({'_id': ObjectId(internship_id)}, {'$set': profile_doc})
        return redirect('/internships/mine/')

    return render(request, 'internship_add.html', {'user': user, 'existing': existing, 'error': error})


@login_required
def internship_delete_view(request, internship_id):
    user = get_current_user(request)
    db = get_db()
    try:
        db.sar_internship_profiles.delete_one({'_id': ObjectId(internship_id), 'student_id': user['id']})
    except Exception:
        pass
    return redirect('/internships/mine/')


@login_required
def internship_mine_view(request):
    user = get_current_user(request)
    db = get_db()
    profiles = list(db.sar_internship_profiles.find({'student_id': user['id']}).sort('created_at', -1))
    for p in profiles:
        p['id'] = str(p['_id'])
        if 'created_at' in p and p['created_at']:
            p['created_at_str'] = p['created_at'].strftime('%b %d, %Y')
        else:
            p['created_at_str'] = ''
        if 'updated_at' in p and p['updated_at']:
            p['updated_at_str'] = p['updated_at'].strftime('%b %d, %Y')
        else:
            p['updated_at_str'] = ''
    return render(request, 'internship_mine.html', {'user': user, 'profiles': profiles})


@login_required
def internship_interest_view(request, internship_id):
    if request.method != 'POST':
        return redirect('/internships/')
    user = get_current_user(request)
    if user.get('status') != 'alumni':
        return redirect('/internships/')
    db = get_db()
    try:
        profile = db.sar_internship_profiles.find_one({'_id': ObjectId(internship_id)})
    except Exception:
        return redirect('/internships/')
    if not profile or profile.get('student_id') == user['id']:
        return redirect('/internships/')
    existing_interest = db.sar_internship_interests.find_one({
        'internship_id': internship_id,
        'alumni_id': user['id'],
    })
    if existing_interest:
        return redirect(f'/internships/{internship_id}/')
    poster_id = profile.get('student_id', '')
    room_id = _get_room_id(user['id'], poster_id)
    now_utc = datetime.utcnow()
    role_part = f" — {profile.get('role_title')}" if profile.get('role_title') else ''
    msg_content = f"Hi! I'm interested in your internship profile: {profile.get('name', '')}{role_part}"
    msg_doc = {
        'room_id': room_id,
        'sender_id': user['id'],
        'sender_name': user.get('name', ''),
        'content': msg_content,
        'sent_at': now_utc,
        'reactions': {},
        'read': False,
    }
    db.sar_chat_messages.insert_one(msg_doc)
    db.sar_chat_rooms.update_one(
        {'room_id': room_id},
        {
            '$set': {
                'last_message': msg_content[:120],
                'last_message_at': now_utc,
                'last_sender_id': user['id'],
            },
            '$inc': {f'unread.{poster_id}': 1},
            '$setOnInsert': {
                'room_id': room_id,
                'participants': sorted([user['id'], poster_id]),
            }
        },
        upsert=True
    )
    db.sar_internship_interests.insert_one({
        'internship_id': internship_id,
        'alumni_id': user['id'],
        'alumni_name': user.get('name', ''),
        'sent_at': now_utc,
    })
    db.sar_notifications.insert_one({
        'user_id': poster_id,
        'type': 'internship_interest',
        'title': 'Alumni Interest',
        'message': f"{user.get('name', '')} is interested in your internship profile: {profile.get('name', '')}",
        'link': f'/chat/{user["id"]}/',
        'reference_id': internship_id,
        'read': False,
        'created_at': now_utc,
    })
    return redirect(f'/chat/{poster_id}/')


@login_required
def notifications_view(request):
    user = get_current_user(request)
    db = get_db()
    notifications_raw = list(db.sar_notifications.find({'user_id': user['id']}).sort('created_at', -1).limit(200))
    dm_seen = set()
    job_app_by_ref = {}
    interest_by_ref = {}
    new_job_list = []
    new_internship_list = []
    mentor_reply_by_ref = {}
    other_notifications = []
    for n in notifications_raw:
        n['id'] = str(n['_id'])
        if n.get('created_at'):
            try:
                ca = n['created_at']
                if ca.tzinfo is None:
                    ca = ca.replace(tzinfo=timezone.utc)
                n['time_str'] = ca.astimezone(IST).strftime('%b %d, %Y %I:%M %p')
            except Exception:
                n['time_str'] = ''
        else:
            n['time_str'] = ''
        t = n.get('type', '')
        if t == 'dm':
            ref = n.get('reference_id', '')
            if ref not in dm_seen:
                dm_seen.add(ref)
                other_notifications.append(n)
        elif t == 'job_application':
            ref = n.get('reference_id', '')
            if ref not in job_app_by_ref:
                job_app_by_ref[ref] = []
            job_app_by_ref[ref].append(n)
        elif t == 'internship_interest':
            ref = n.get('reference_id', '')
            if ref not in interest_by_ref:
                interest_by_ref[ref] = []
            interest_by_ref[ref].append(n)
        elif t == 'new_job':
            new_job_list.append(n)
        elif t == 'new_internship':
            new_internship_list.append(n)
        elif t == 'mentor_reply':
            ref = n.get('reference_id', '')
            if ref not in mentor_reply_by_ref:
                mentor_reply_by_ref[ref] = []
            mentor_reply_by_ref[ref].append(n)
        else:
            other_notifications.append(n)
    for ref, notifs in job_app_by_ref.items():
        if len(notifs) <= 3:
            other_notifications.extend(notifs)
        else:
            n = notifs[0]
            n['message'] = f"{len(notifs)} people applied to your job: {n.get('job_title', '')}"
            other_notifications.append(n)
    for ref, notifs in interest_by_ref.items():
        if len(notifs) <= 3:
            other_notifications.extend(notifs)
        else:
            n = notifs[0]
            n['message'] = f"{len(notifs)} alumni are interested in your internship profile"
            n['link'] = '/chat/'
            other_notifications.append(n)
    if len(new_job_list) <= 3:
        other_notifications.extend(new_job_list)
    elif new_job_list:
        n = new_job_list[0]
        n['title'] = 'New Jobs Posted'
        n['message'] = f"{len(new_job_list)} new jobs have been posted"
        n['link'] = '/jobs/'
        other_notifications.append(n)
    if len(new_internship_list) <= 3:
        other_notifications.extend(new_internship_list)
    elif new_internship_list:
        n = new_internship_list[0]
        n['title'] = 'New Internship Profiles'
        n['message'] = f"{len(new_internship_list)} new internship profiles have been posted"
        n['link'] = '/internships/'
        other_notifications.append(n)
    for ref, notifs in mentor_reply_by_ref.items():
        if len(notifs) <= 3:
            other_notifications.extend(notifs)
        else:
            n = notifs[0]
            n['message'] = f"{len(notifs)} people replied to your question"
            other_notifications.append(n)
    other_notifications.sort(key=lambda x: x.get('created_at', datetime.min), reverse=True)
    db.sar_notifications.update_many({'user_id': user['id'], 'read': False}, {'$set': {'read': True}})
    return render(request, 'notifications.html', {'user': user, 'notifications': other_notifications})


@login_required
def notifications_api_view(request):
    user = get_current_user(request)
    db = get_db()
    count = db.sar_notifications.count_documents({'user_id': user['id'], 'read': False})
    return JsonResponse({'count': count})


@login_required
def mentorship_view(request):
    user = get_current_user(request)
    db = get_db()

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        body = request.POST.get('body', '').strip()
        if title and body:
            db.sar_questions.insert_one({
                'title': title,
                'body': body,
                'posted_by': user['id'],
                'posted_by_name': user['name'],
                'posted_by_pic': user.get('profile_pic', ''),
                'posted_at': datetime.utcnow(),
                'upvotes': [],
                'downvotes': [],
            })
        return redirect('/mentorship/')

    questions = list(db.sar_questions.find({}).sort('posted_at', -1))
    for q in questions:
        q['id'] = str(q['_id'])
        q['up_count'] = len(q.get('upvotes', []))
        q['down_count'] = len(q.get('downvotes', []))
        q['reply_count'] = db.sar_replies.count_documents({'question_id': q['id']})
        if 'posted_at' in q:
            q['posted_at_str'] = q['posted_at'].strftime('%b %d, %Y')
        q['is_author'] = q['posted_by'] == user['id']
        q['user_vote'] = 'up' if user['id'] in q.get('upvotes', []) else ('down' if user['id'] in q.get('downvotes', []) else None)

    return render(request, 'mentorship.html', {'user': user, 'questions': questions})


@login_required
def mentorship_question_view(request, question_id):
    user = get_current_user(request)
    db = get_db()
    try:
        question = db.sar_questions.find_one({'_id': ObjectId(question_id)})
    except Exception:
        return redirect('/mentorship/')
    if not question:
        return redirect('/mentorship/')

    question['id'] = str(question['_id'])
    question['up_count'] = len(question.get('upvotes', []))
    question['down_count'] = len(question.get('downvotes', []))
    question['user_vote'] = 'up' if user['id'] in question.get('upvotes', []) else ('down' if user['id'] in question.get('downvotes', []) else None)
    question['is_author'] = question['posted_by'] == user['id']
    if 'posted_at' in question:
        question['posted_at_str'] = question['posted_at'].strftime('%b %d, %Y at %H:%M')

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add_reply':
            content = request.POST.get('content', '').strip()
            parent_reply_id = request.POST.get('parent_reply_id', '') or None
            parent_reply_name = request.POST.get('parent_reply_name', '') or None
            if content:
                db.sar_replies.insert_one({
                    'question_id': question_id,
                    'parent_reply_id': parent_reply_id,
                    'parent_reply_name': parent_reply_name,
                    'content': content,
                    'posted_by': user['id'],
                    'posted_by_name': user['name'],
                    'posted_by_pic': user.get('profile_pic', ''),
                    'posted_at': datetime.utcnow(),
                    'upvotes': [],
                    'downvotes': [],
                })
                question_poster_id = question.get('posted_by', '')
                if question_poster_id and question_poster_id != user['id']:
                    db.sar_notifications.insert_one({
                        'user_id': question_poster_id,
                        'type': 'mentor_reply',
                        'title': 'New Reply',
                        'message': f"{user['name']} replied to your question: {question.get('title', '')}",
                        'link': f'/mentorship/{question_id}/',
                        'reference_id': question_id,
                        'read': False,
                        'created_at': datetime.utcnow(),
                    })
        elif action == 'delete_question' and question['is_author']:
            db.sar_questions.delete_one({'_id': ObjectId(question_id)})
            db.sar_replies.delete_many({'question_id': question_id})
            return redirect('/mentorship/')
        elif action == 'delete_reply':
            reply_id = request.POST.get('reply_id', '')
            try:
                reply = db.sar_replies.find_one({'_id': ObjectId(reply_id)})
                if reply and reply['posted_by'] == user['id']:
                    db.sar_replies.delete_one({'_id': ObjectId(reply_id)})
                    db.sar_replies.delete_many({'parent_reply_id': reply_id})
            except Exception:
                pass
        return redirect(f'/mentorship/{question_id}/')

    all_replies = list(db.sar_replies.find({'question_id': question_id}).sort('posted_at', 1))
    for r in all_replies:
        r['id'] = str(r['_id'])
        r['up_count'] = len(r.get('upvotes', []))
        r['down_count'] = len(r.get('downvotes', []))
        r['user_vote'] = 'up' if user['id'] in r.get('upvotes', []) else ('down' if user['id'] in r.get('downvotes', []) else None)
        r['is_author'] = r['posted_by'] == user['id']
        if 'posted_at' in r:
            r['posted_at_str'] = r['posted_at'].strftime('%b %d, %Y at %H:%M')

    top_replies = [r for r in all_replies if not r.get('parent_reply_id')]
    reply_children = {}
    for r in all_replies:
        if r.get('parent_reply_id'):
            pid = r['parent_reply_id']
            if pid not in reply_children:
                reply_children[pid] = []
            reply_children[pid].append(r)

    for r in top_replies:
        r['children'] = reply_children.get(r['id'], [])

    return render(request, 'mentorship_question.html', {
        'user': user,
        'question': question,
        'top_replies': top_replies,
    })


@login_required
def mentorship_vote_view(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    user = get_current_user(request)
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    item_type = data.get('item_type')
    item_id = data.get('item_id')
    vote = data.get('vote')

    db = get_db()
    collection = db.sar_questions if item_type == 'question' else db.sar_replies

    try:
        item = collection.find_one({'_id': ObjectId(item_id)})
    except Exception:
        return JsonResponse({'error': 'Not found'}, status=404)

    if not item:
        return JsonResponse({'error': 'Not found'}, status=404)

    if item['posted_by'] == user['id']:
        return JsonResponse({'error': 'Cannot vote on own content'}, status=400)

    upvotes = list(item.get('upvotes', []))
    downvotes = list(item.get('downvotes', []))
    uid = user['id']

    if vote == 'up':
        if uid in upvotes:
            upvotes.remove(uid)
        else:
            upvotes.append(uid)
            if uid in downvotes:
                downvotes.remove(uid)
    elif vote == 'down':
        if uid in downvotes:
            downvotes.remove(uid)
        else:
            downvotes.append(uid)
            if uid in upvotes:
                upvotes.remove(uid)

    collection.update_one({'_id': ObjectId(item_id)}, {'$set': {'upvotes': upvotes, 'downvotes': downvotes}})
    user_vote = 'up' if uid in upvotes else ('down' if uid in downvotes else None)
    return JsonResponse({'up': len(upvotes), 'down': len(downvotes), 'user_vote': user_vote})


def _get_room_id(uid1, uid2):
    parts = sorted([uid1, uid2])
    return f'{parts[0]}_{parts[1]}'


def _serialize_message(msg, current_user_id):
    reactions = msg.get('reactions', {})
    sent_at = msg.get('sent_at')
    if sent_at:
        if sent_at.tzinfo is None:
            sent_at = sent_at.replace(tzinfo=timezone.utc)
        sent_at_ist = sent_at.astimezone(IST)
        sent_at_str = sent_at_ist.strftime('%b %d, %Y %I:%M %p')
    else:
        sent_at_str = ''
    return {
        'id': str(msg['_id']),
        'sender_id': msg.get('sender_id', ''),
        'sender_name': msg.get('sender_name', ''),
        'content': msg.get('content', ''),
        'sent_at': sent_at_str,
        'reactions': {k: len(v) for k, v in reactions.items()},
        'my_reactions': [k for k, v in reactions.items() if current_user_id in v],
        'is_mine': msg.get('sender_id') == current_user_id,
        'read': msg.get('read', False),
    }


@login_required
def chat_view(request):
    user = get_current_user(request)
    db = get_db()
    rooms = list(db.sar_chat_rooms.find({'participants': user['id']}).sort('last_message_at', -1))
    conversations = []
    for room in rooms:
        other_id = next((p for p in room.get('participants', []) if p != user['id']), None)
        if not other_id:
            continue
        try:
            other_user = db.sar_users.find_one({'_id': ObjectId(other_id)}, {'name': 1, 'profile_pic': 1, 'stream': 1, 'status': 1})
        except Exception:
            continue
        if not other_user:
            continue
        unread = room.get('unread', {}).get(user['id'], 0)
        last_at = room.get('last_message_at')
        conversations.append({
            'room_id': room['room_id'],
            'other_id': other_id,
            'other_name': other_user.get('name', ''),
            'other_pic': other_user.get('profile_pic', ''),
            'other_stream': other_user.get('stream', ''),
            'other_status': other_user.get('status', ''),
            'last_message': room.get('last_message', ''),
            'last_at': last_at.strftime('%b %d, %Y %H:%M') if last_at else '',
            'unread': unread,
        })
    total_unread = sum(c['unread'] for c in conversations)
    return render(request, 'chat.html', {'user': user, 'conversations': conversations, 'total_unread': total_unread})


@login_required
def chat_room_view(request, other_user_id):
    user = get_current_user(request)
    if other_user_id == user['id']:
        return redirect('/chat/')
    db = get_db()
    try:
        other_user = db.sar_users.find_one({'_id': ObjectId(other_user_id)}, {'name': 1, 'profile_pic': 1, 'stream': 1, 'status': 1, 'admission_year': 1})
    except Exception:
        return redirect('/chat/')
    if not other_user:
        return redirect('/chat/')
    other_user['id'] = str(other_user['_id'])

    room_id = _get_room_id(user['id'], other_user_id)

    db.sar_chat_rooms.update_one(
        {'room_id': room_id},
        {
            '$set': {f'unread.{user["id"]}': 0},
            '$setOnInsert': {
                'room_id': room_id,
                'participants': sorted([user['id'], other_user_id]),
                'last_message': '',
                'last_message_at': None,
                'last_sender_id': '',
            }
        },
        upsert=True
    )

    db.sar_notifications.update_many(
        {'user_id': user['id'], 'type': 'dm', 'reference_id': room_id, 'read': False},
        {'$set': {'read': True}}
    )

    messages_cursor = db.sar_chat_messages.find({'room_id': room_id}).sort('sent_at', -1).limit(50)
    messages_raw = list(messages_cursor)
    messages_raw.reverse()
    messages = [_serialize_message(m, user['id']) for m in messages_raw]
    has_more = db.sar_chat_messages.count_documents({'room_id': room_id}) > 50

    return render(request, 'chat_room.html', {
        'user': user,
        'other_user': other_user,
        'room_id': room_id,
        'messages_json': json.dumps(messages),
        'has_more': has_more,
    })


@login_required
def chat_messages_api(request, room_id):
    user = get_current_user(request)
    uid = user['id']
    parts = room_id.split('_')
    if uid not in parts:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    before_id = request.GET.get('before', '')
    db = get_db()
    query = {'room_id': room_id}
    if before_id:
        try:
            query['_id'] = {'$lt': ObjectId(before_id)}
        except Exception:
            pass
    msgs_raw = list(db.sar_chat_messages.find(query).sort('sent_at', -1).limit(50))
    msgs_raw.reverse()
    messages = [_serialize_message(m, uid) for m in msgs_raw]
    oldest_id = messages[0]['id'] if messages else None
    has_more = False
    if oldest_id:
        has_more = db.sar_chat_messages.count_documents({'room_id': room_id, '_id': {'$lt': ObjectId(oldest_id)}}) > 0
    return JsonResponse({'messages': messages, 'has_more': has_more})


@login_required
def chat_unread_api(request):
    user = get_current_user(request)
    db = get_db()
    rooms = list(db.sar_chat_rooms.find({'participants': user['id']}, {f'unread.{user["id"]}': 1}))
    total = sum(r.get('unread', {}).get(user['id'], 0) for r in rooms)
    return JsonResponse({'count': total})


def admin_login_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.session.get('admin_id'):
            return redirect('/admin/')
        return view_func(request, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper


def admin_login_view(request):
    db = get_db()
    admin_exists = db.sar_admins.count_documents({}) > 0
    error = None
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        if not admin_exists:
            doc = {
                'username': username,
                'password': make_password(password),
                'created_at': datetime.utcnow(),
            }
            result = db.sar_admins.insert_one(doc)
            request.session['admin_id'] = str(result.inserted_id)
            return redirect('/admin/dashboard/')
        admin = db.sar_admins.find_one({'username': username})
        if admin and check_password(password, admin['password']):
            request.session['admin_id'] = str(admin['_id'])
            return redirect('/admin/dashboard/')
        error = 'Invalid username or password.'
    return render(request, 'admin_login.html', {'admin_exists': admin_exists, 'error': error})


def admin_logout_view(request):
    request.session.pop('admin_id', None)
    return redirect('/admin/')


@admin_login_required
def admin_dashboard_view(request):
    db = get_db()
    user_count = db.sar_users.count_documents({})
    job_count = db.sar_jobs.count_documents({})
    internship_count = db.sar_internship_profiles.count_documents({})
    question_count = db.sar_questions.count_documents({})
    flagged_jobs = db.sar_jobs.count_documents({'flagged': True})
    flagged_internships = db.sar_internship_profiles.count_documents({'flagged': True})
    flagged_questions = db.sar_questions.count_documents({'flagged': True})
    flagged_replies = db.sar_replies.count_documents({'flagged': True})
    flagged_users = db.sar_users.count_documents({'flagged': True})
    return render(request, 'admin_dashboard.html', {
        'user_count': user_count,
        'job_count': job_count,
        'internship_count': internship_count,
        'question_count': question_count,
        'flagged_jobs': flagged_jobs,
        'flagged_internships': flagged_internships,
        'flagged_questions': flagged_questions,
        'flagged_replies': flagged_replies,
        'flagged_users': flagged_users,
    })


@admin_login_required
def admin_users_view(request):
    db = get_db()
    users = list(db.sar_users.find({}).sort('_id', -1))
    for u in users:
        u['id'] = str(u['_id'])
    return render(request, 'admin_users.html', {'users': users})


@admin_login_required
def admin_user_flag_view(request, user_id):
    if request.method == 'POST':
        db = get_db()
        try:
            u = db.sar_users.find_one({'_id': ObjectId(user_id)})
            if u:
                new_flagged = not u.get('flagged', False)
                db.sar_users.update_one({'_id': ObjectId(user_id)}, {'$set': {'flagged': new_flagged}})
                if new_flagged:
                    db.sar_notifications.insert_one({
                        'user_id': user_id,
                        'type': 'account_flagged',
                        'title': 'Account Flagged',
                        'message': 'Your account has been flagged by the admin. Please review your profile.',
                        'link': '/profile/',
                        'reference_id': '',
                        'read': False,
                        'created_at': datetime.utcnow(),
                    })
        except Exception:
            pass
    return redirect(f'/admin/users/{user_id}/')


@admin_login_required
def admin_jobs_view(request):
    db = get_db()
    jobs = list(db.sar_jobs.find({}).sort('posted_at', -1))
    for j in jobs:
        j['id'] = str(j['_id'])
        if 'posted_at' in j and j['posted_at']:
            j['posted_at_str'] = j['posted_at'].strftime('%b %d, %Y')
        else:
            j['posted_at_str'] = ''
    return render(request, 'admin_jobs.html', {'jobs': jobs})


@admin_login_required
def admin_job_delete_view(request, job_id):
    if request.method == 'POST':
        db = get_db()
        try:
            db.sar_jobs.delete_one({'_id': ObjectId(job_id)})
        except Exception:
            pass
    return redirect('/admin/jobs/')


@admin_login_required
def admin_job_flag_view(request, job_id):
    if request.method == 'POST':
        db = get_db()
        try:
            job = db.sar_jobs.find_one({'_id': ObjectId(job_id)})
            if job:
                new_flagged = not job.get('flagged', False)
                db.sar_jobs.update_one({'_id': ObjectId(job_id)}, {'$set': {'flagged': new_flagged}})
                if new_flagged:
                    db.sar_notifications.insert_one({
                        'user_id': job.get('posted_by', ''),
                        'type': 'content_flagged',
                        'title': 'Job Flagged',
                        'message': f"Your job posting '{job.get('title', '')}' has been flagged by the admin.",
                        'link': f'/jobs/{job_id}/',
                        'reference_id': job_id,
                        'read': False,
                        'created_at': datetime.utcnow(),
                    })
        except Exception:
            pass
    return redirect('/admin/jobs/')


@admin_login_required
def admin_internships_view(request):
    db = get_db()
    profiles = list(db.sar_internship_profiles.find({}).sort('created_at', -1))
    for p in profiles:
        p['id'] = str(p['_id'])
        if 'created_at' in p and p['created_at']:
            p['created_at_str'] = p['created_at'].strftime('%b %d, %Y')
        else:
            p['created_at_str'] = ''
    return render(request, 'admin_internships.html', {'profiles': profiles})


@admin_login_required
def admin_internship_delete_view(request, internship_id):
    if request.method == 'POST':
        db = get_db()
        try:
            db.sar_internship_profiles.delete_one({'_id': ObjectId(internship_id)})
        except Exception:
            pass
    return redirect('/admin/internships/')


@admin_login_required
def admin_internship_flag_view(request, internship_id):
    if request.method == 'POST':
        db = get_db()
        try:
            p = db.sar_internship_profiles.find_one({'_id': ObjectId(internship_id)})
            if p:
                new_flagged = not p.get('flagged', False)
                db.sar_internship_profiles.update_one({'_id': ObjectId(internship_id)}, {'$set': {'flagged': new_flagged}})
                if new_flagged:
                    db.sar_notifications.insert_one({
                        'user_id': p.get('student_id', ''),
                        'type': 'content_flagged',
                        'title': 'Internship Profile Flagged',
                        'message': f"Your internship profile '{p.get('name', '')}' has been flagged by the admin.",
                        'link': f'/internships/{internship_id}/',
                        'reference_id': internship_id,
                        'read': False,
                        'created_at': datetime.utcnow(),
                    })
        except Exception:
            pass
    return redirect('/admin/internships/')


@admin_login_required
def admin_mentorship_view(request):
    db = get_db()
    questions = list(db.sar_questions.find({}).sort('posted_at', -1))
    for q in questions:
        q['id'] = str(q['_id'])
        q['reply_count'] = db.sar_replies.count_documents({'question_id': q['id']})
        q['up_count'] = len(q.get('upvotes', []))
        q['down_count'] = len(q.get('downvotes', []))
        if 'posted_at' in q:
            q['posted_at_str'] = q['posted_at'].strftime('%b %d, %Y')
        else:
            q['posted_at_str'] = ''
    return render(request, 'admin_mentorship.html', {'questions': questions})


@admin_login_required
def admin_mentorship_question_view(request, question_id):
    db = get_db()
    try:
        question = db.sar_questions.find_one({'_id': ObjectId(question_id)})
    except Exception:
        return redirect('/admin/mentorship/')
    if not question:
        return redirect('/admin/mentorship/')
    question['id'] = str(question['_id'])
    question['up_count'] = len(question.get('upvotes', []))
    question['down_count'] = len(question.get('downvotes', []))
    if 'posted_at' in question:
        question['posted_at_str'] = question['posted_at'].strftime('%b %d, %Y at %H:%M')
    else:
        question['posted_at_str'] = ''
    all_replies = list(db.sar_replies.find({'question_id': question_id}).sort('posted_at', 1))
    for r in all_replies:
        r['id'] = str(r['_id'])
        r['up_count'] = len(r.get('upvotes', []))
        r['down_count'] = len(r.get('downvotes', []))
        if 'posted_at' in r:
            r['posted_at_str'] = r['posted_at'].strftime('%b %d, %Y at %H:%M')
        else:
            r['posted_at_str'] = ''
    top_replies = [r for r in all_replies if not r.get('parent_reply_id')]
    reply_children = {}
    for r in all_replies:
        if r.get('parent_reply_id'):
            pid = r['parent_reply_id']
            if pid not in reply_children:
                reply_children[pid] = []
            reply_children[pid].append(r)
    for r in top_replies:
        r['children'] = reply_children.get(r['id'], [])
    return render(request, 'admin_mentorship_question.html', {'question': question, 'top_replies': top_replies})


@admin_login_required
def admin_question_delete_view(request, question_id):
    if request.method == 'POST':
        db = get_db()
        try:
            db.sar_questions.delete_one({'_id': ObjectId(question_id)})
            db.sar_replies.delete_many({'question_id': question_id})
        except Exception:
            pass
    return redirect('/admin/mentorship/')


@admin_login_required
def admin_question_flag_view(request, question_id):
    if request.method == 'POST':
        db = get_db()
        try:
            q = db.sar_questions.find_one({'_id': ObjectId(question_id)})
            if q:
                new_flagged = not q.get('flagged', False)
                db.sar_questions.update_one({'_id': ObjectId(question_id)}, {'$set': {'flagged': new_flagged}})
                if new_flagged:
                    db.sar_notifications.insert_one({
                        'user_id': q.get('posted_by', ''),
                        'type': 'content_flagged',
                        'title': 'Question Flagged',
                        'message': f"Your mentorship question '{q.get('title', '')}' has been flagged by the admin.",
                        'link': f'/mentorship/{question_id}/',
                        'reference_id': question_id,
                        'read': False,
                        'created_at': datetime.utcnow(),
                    })
        except Exception:
            pass
    return redirect(f'/admin/mentorship/{question_id}/')


@admin_login_required
def admin_reply_delete_view(request, reply_id):
    if request.method == 'POST':
        db = get_db()
        try:
            r = db.sar_replies.find_one({'_id': ObjectId(reply_id)})
            if r:
                question_id = r.get('question_id', '')
                db.sar_replies.delete_one({'_id': ObjectId(reply_id)})
                db.sar_replies.delete_many({'parent_reply_id': reply_id})
                return redirect(f'/admin/mentorship/{question_id}/')
        except Exception:
            pass
    return redirect('/admin/mentorship/')


@admin_login_required
def admin_reply_flag_view(request, reply_id):
    if request.method == 'POST':
        db = get_db()
        try:
            r = db.sar_replies.find_one({'_id': ObjectId(reply_id)})
            if r:
                question_id = r.get('question_id', '')
                new_flagged = not r.get('flagged', False)
                db.sar_replies.update_one({'_id': ObjectId(reply_id)}, {'$set': {'flagged': new_flagged}})
                if new_flagged:
                    db.sar_notifications.insert_one({
                        'user_id': r.get('posted_by', ''),
                        'type': 'content_flagged',
                        'title': 'Reply Flagged',
                        'message': 'Your reply in mentorship has been flagged by the admin.',
                        'link': f'/mentorship/{question_id}/',
                        'reference_id': question_id,
                        'read': False,
                        'created_at': datetime.utcnow(),
                    })
                return redirect(f'/admin/mentorship/{question_id}/')
        except Exception:
            pass
    return redirect('/admin/mentorship/')


@admin_login_required
def admin_job_detail_view(request, job_id):
    db = get_db()
    try:
        job = db.sar_jobs.find_one({'_id': ObjectId(job_id)})
    except Exception:
        return redirect('/admin/jobs/')
    if not job:
        return redirect('/admin/jobs/')
    job['id'] = str(job['_id'])
    if 'posted_at' in job and job['posted_at']:
        job['posted_at_str'] = job['posted_at'].strftime('%b %d, %Y')
    else:
        job['posted_at_str'] = ''
    return render(request, 'admin_job_detail.html', {'job': job})


@admin_login_required
def admin_internship_detail_view(request, internship_id):
    db = get_db()
    try:
        profile = db.sar_internship_profiles.find_one({'_id': ObjectId(internship_id)})
    except Exception:
        return redirect('/admin/internships/')
    if not profile:
        return redirect('/admin/internships/')
    profile['id'] = str(profile['_id'])
    if 'created_at' in profile and profile['created_at']:
        profile['created_at_str'] = profile['created_at'].strftime('%b %d, %Y')
    else:
        profile['created_at_str'] = ''
    if 'updated_at' in profile and profile['updated_at']:
        profile['updated_at_str'] = profile['updated_at'].strftime('%b %d, %Y')
    else:
        profile['updated_at_str'] = ''
    return render(request, 'admin_internship_detail.html', {'profile': profile})


@admin_login_required
def admin_user_detail_view(request, user_id):
    db = get_db()
    try:
        profile_user = db.sar_users.find_one({'_id': ObjectId(user_id)})
    except Exception:
        return redirect('/admin/users/')
    if not profile_user:
        return redirect('/admin/users/')
    profile_user['id'] = str(profile_user['_id'])
    return render(request, 'admin_user_detail.html', {'profile_user': profile_user})
