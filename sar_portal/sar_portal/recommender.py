from sentence_transformers import SentenceTransformer
import numpy as np
import traceback

print("LOADING SENTENCE TRANSFORMERS MODEL...")
_model = SentenceTransformer('all-MiniLM-L6-v2')
print("MODEL LOADED SUCCESSFULLY.")

def get_model():
    return _model

def build_user_text(user):
    parts = []
    if user.get('stream'):
        parts.append('Stream: ' + str(user['stream']))
    if user.get('location'):
        parts.append('Location: ' + str(user['location']))
    if user.get('skills'):
        parts.append('Skills: ' + ', '.join([str(s) for s in user['skills']]))
    if user.get('status') == 'alumni':
        if user.get('current_company_name'):
            parts.append('Company: ' + str(user['current_company_name']))
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
            parts.append('Year: ' + str(user['current_year']))
        if user.get('achievements'):
            for ach in user['achievements']:
                title = ach.get('title', '') or ach.get('name', '')
                if title:
                    parts.append('Achievement: ' + str(title))
        if user.get('startup') and user.get('startup', {}).get('name'):
            parts.append('Startup: ' + str(user['startup']['name']))
            
    result_text = ' | '.join(parts) if parts else 'student profile'
    print("BUILT USER TEXT:", result_text)
    return result_text

def build_job_text(job):
    parts = []
    if job.get('title'):
        parts.append(str(job['title']))
    if job.get('company_name'):
        parts.append('Company: ' + str(job['company_name']))
    if job.get('eligibility'):
        parts.append('Skills required: ' + ', '.join([str(e) for e in job['eligibility']]))
    if job.get('locations'):
        parts.append('Location: ' + ', '.join([str(l) for l in job['locations']]))
    if job.get('experience_required'):
        parts.append('Experience: ' + str(job['experience_required']))
    if job.get('description'):
        parts.append(str(job['description'])[:300])
    if job.get('company_description'):
        parts.append(str(job['company_description'])[:200])
        
    result_text = ' | '.join(parts) if parts else 'job posting'
    print("BUILT JOB TEXT:", result_text)
    return result_text

def rank_by_similarity(user_text, items, item_texts):
    print("STARTING RANK BY SIMILARITY...")
    if not items or not item_texts:
        print("NO ITEMS OR ITEM TEXTS PROVIDED")
        return []
    try:
        model = get_model()
        user_emb = model.encode([user_text], convert_to_numpy=True, normalize_embeddings=True)
        item_embs = model.encode(item_texts, convert_to_numpy=True, normalize_embeddings=True, batch_size=32, show_progress_bar=False)
        scores = (item_embs @ user_emb.T).flatten()
        scores = [float(max(0.0, min(1.0, s))) for s in scores]
        ranked = sorted(zip(items, scores), key=lambda x: x[1], reverse=True)
        print("RANK BY SIMILARITY SUCCESS, TOP SCORE:", ranked[0][1] if ranked else "None")
        return ranked
    except Exception as e:
        print("ERROR IN RANK_BY_SIMILARITY:")
        traceback.print_exc()
        return [(item, 0.0) for item in items]

def calculate_similarity(text1, text2):
    print("STARTING CALCULATE SIMILARITY...")
    if not text1 or not text2:
        print("MISSING TEXT1 OR TEXT2")
        return 0.0
    try:
        model = get_model()
        emb1 = model.encode([text1], convert_to_numpy=True, normalize_embeddings=True)
        emb2 = model.encode([text2], convert_to_numpy=True, normalize_embeddings=True)
        score = (emb1 @ emb2.T).flatten()[0]
        score = max(0.0, min(1.0, float(score)))
        final_score = score * 100
        print("CALCULATE SIMILARITY SUCCESS:", final_score)
        return final_score
    except Exception as e:
        print("ERROR IN CALCULATE_SIMILARITY:")
        traceback.print_exc()
        return 0.0