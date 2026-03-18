from sentence_transformers import SentenceTransformer
import numpy as np

_model = None


def get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer('all-MiniLM-L6-v2')
    return _model


def build_user_text(user):
    parts = []
    if user.get('stream'):
        parts.append('Stream: ' + user['stream'])
    if user.get('location'):
        parts.append('Location: ' + user['location'])
    if user.get('skills'):
        parts.append('Skills: ' + ', '.join(user['skills']))
    if user.get('status') == 'alumni':
        if user.get('current_company_name'):
            parts.append('Company: ' + user['current_company_name'])
        if user.get('current_status') == 'working':
            parts.append('Currently working at a company')
        elif user.get('current_status') == 'owning':
            parts.append('Currently owning a company')
        if user.get('experience'):
            for exp in user['experience']:
                role = exp.get('role', '')
                company = exp.get('company', '')
                if role or company:
                    parts.append(f"Experience: {role} at {company}".strip(' at'))
    elif user.get('status') == 'student':
        if user.get('current_year'):
            parts.append('Year: ' + user['current_year'])
        if user.get('achievements'):
            for ach in user['achievements']:
                title = ach.get('title', '') or ach.get('name', '')
                if title:
                    parts.append('Achievement: ' + title)
        if user.get('startup') and user['startup'].get('name'):
            parts.append('Startup: ' + user['startup']['name'])
    return ' | '.join(parts) if parts else 'student profile'


def build_job_text(job):
    parts = []
    if job.get('title'):
        parts.append(job['title'])
    if job.get('company_name'):
        parts.append('Company: ' + job['company_name'])
    if job.get('eligibility'):
        parts.append('Skills required: ' + ', '.join(job['eligibility']))
    if job.get('locations'):
        parts.append('Location: ' + ', '.join(job['locations']))
    if job.get('experience_required'):
        parts.append('Experience: ' + str(job['experience_required']))
    if job.get('description'):
        parts.append(job['description'][:300])
    if job.get('company_description'):
        parts.append(job['company_description'][:200])
    return ' | '.join(parts) if parts else 'job posting'


def build_internship_text(profile):
    parts = []
    if profile.get('name'):
        parts.append(profile['name'])
    if profile.get('role_title'):
        parts.append('Role: ' + profile['role_title'])
    if profile.get('stream'):
        parts.append('Stream: ' + profile['stream'])
    if profile.get('skills'):
        parts.append('Skills: ' + ', '.join(profile['skills']))
    if profile.get('current_location'):
        parts.append('Location: ' + profile['current_location'])
    if profile.get('relocatable_locations'):
        parts.append('Open to relocate: ' + ', '.join(profile['relocatable_locations']))
    if profile.get('languages'):
        parts.append('Languages: ' + ', '.join(profile['languages']))
    if profile.get('description'):
        parts.append(profile['description'][:250])
    return ' | '.join(parts) if parts else 'internship profile'


def rank_by_similarity(user_text, items, item_texts):
    if not items or not item_texts:
        return []
    model = get_model()
    user_emb = model.encode([user_text], convert_to_numpy=True, normalize_embeddings=True)
    item_embs = model.encode(item_texts, convert_to_numpy=True, normalize_embeddings=True, batch_size=32, show_progress_bar=False)
    scores = (item_embs @ user_emb.T).flatten()
    ranked = sorted(zip(items, scores.tolist()), key=lambda x: x[1], reverse=True)
    return ranked
