"""Automated screening logic."""
from flask import current_app


def calculate_screening_score(application):
    """
    Calculate screening score based on job requirements.
    
    Returns a score from 0-100 based on how well the applicant
    matches the job's minimum requirements.
    """
    score = 0
    max_score = 100
    
    job = application.job
    requirements = job.minimum_requirements or {}
    
    # Note: In a real implementation, you would:
    # 1. Parse the CV document to extract education, experience, skills
    # 2. Compare against the job requirements
    # 3. Use NLP/ML for better matching
    
    # For this MVP, we'll use a simplified scoring based on available data
    applicant = application.applicant
    
    # Basic profile completeness (20 points)
    profile_score = 0
    if applicant.first_name and applicant.last_name:
        profile_score += 5
    if applicant.email:
        profile_score += 5
    if applicant.phone:
        profile_score += 5
    if applicant.id_number:
        profile_score += 5
    score += profile_score
    
    # Document submission (30 points)
    doc_score = 0
    documents = application.documents.all()
    doc_types = [doc.document_type for doc in documents]
    
    if 'cv' in doc_types:
        doc_score += 15  # CV is essential
    if 'id' in doc_types:
        doc_score += 10
    if 'qualification' in doc_types:
        doc_score += 5
    score += doc_score
    
    # Cover letter (10 points)
    if application.cover_letter and len(application.cover_letter) > 100:
        score += 10
    elif application.cover_letter:
        score += 5
    
    # EE Target matching (10 points) - if job has EE target
    if job.ee_target_category:
        ee_target = job.ee_target_category.lower()
        
        # Check race matching
        if applicant.race and applicant.race.lower() in ee_target:
            score += 5
        
        # Check gender matching
        if applicant.gender and applicant.gender.lower() in ee_target:
            score += 3
        
        # Disability preference
        if 'disability' in ee_target and applicant.disability_status:
            score += 2
    else:
        # No EE target, give full points
        score += 10
    
    # Application timing (10 points) - earlier applications slightly preferred
    days_before_deadline = job.days_until_closing
    if days_before_deadline >= 14:
        score += 10
    elif days_before_deadline >= 7:
        score += 7
    elif days_before_deadline >= 3:
        score += 5
    else:
        score += 2
    
    # Normalize to max score
    final_score = min(score, max_score)
    
    return round(final_score, 1)


def auto_shortlist_threshold():
    """Get the minimum score for auto-shortlisting."""
    return current_app.config.get('AUTO_SHORTLIST_THRESHOLD', 70)


def get_top_candidates(job_id, limit=10):
    """Get top candidates for a job based on screening score."""
    from app.models import Application
    
    return Application.query.filter_by(
        job_id=job_id
    ).filter(
        Application.screening_score.isnot(None)
    ).order_by(
        Application.screening_score.desc()
    ).limit(limit).all()


def compare_candidates(app1, app2):
    """Compare two applications for ranking."""
    # Primary: Screening score
    if app1.screening_score != app2.screening_score:
        return app2.screening_score - app1.screening_score
    
    # Secondary: Interview score (if available)
    score1 = app1.interview_score or 0
    score2 = app2.interview_score or 0
    if score1 != score2:
        return score2 - score1
    
    # Tertiary: Application date (earlier is better)
    if app1.application_date != app2.application_date:
        return (app1.application_date - app2.application_date).days
    
    return 0


def bulk_screen_applications(job_id):
    """Screen all unscreened applications for a job."""
    from app.models import Application
    from app import db
    
    applications = Application.query.filter_by(
        job_id=job_id,
        status='submitted'
    ).filter(
        Application.screening_score.is_(None)
    ).all()
    
    results = {
        'total': len(applications),
        'screened': 0,
        'qualified': 0,
        'scores': []
    }
    
    threshold = auto_shortlist_threshold()
    
    for app in applications:
        score = calculate_screening_score(app)
        app.screening_score = score
        app.status = 'under_review'
        app.current_stage = 'Screened'
        
        results['screened'] += 1
        results['scores'].append(score)
        
        if score >= threshold:
            results['qualified'] += 1
    
    db.session.commit()
    
    results['avg_score'] = sum(results['scores']) / len(results['scores']) if results['scores'] else 0
    
    return results


# Advanced matching functions (placeholders for future implementation)

def extract_skills_from_cv(cv_document):
    """Extract skills from CV document using NLP."""
    # Placeholder: Would use document parsing + NLP
    # Libraries like pdfplumber, python-docx, spaCy, etc.
    return []


def match_education_level(required_level, applicant_education):
    """Check if applicant meets education requirements."""
    education_hierarchy = [
        'matric', 'certificate', 'diploma', 
        'degree', 'honours', 'masters', 'doctorate'
    ]
    
    try:
        required_idx = education_hierarchy.index(required_level.lower())
        applicant_idx = education_hierarchy.index(applicant_education.lower())
        return applicant_idx >= required_idx
    except (ValueError, AttributeError):
        return False


def calculate_experience_match(required_years, cv_content):
    """Extract and compare experience years from CV."""
    # Placeholder: Would parse CV for experience duration
    # Using regex or NLP to extract years of experience
    return True  # Default to True for MVP
