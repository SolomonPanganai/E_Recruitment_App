"""Celery task definitions."""
from datetime import datetime, timedelta
from tasks.celery_app import celery


@celery.task(bind=True)
def send_application_confirmation(self, application_id):
    """Send confirmation email after application submission."""
    from app import create_app, db
    from app.models import Application
    from app.utils.notifications import send_application_confirmation as send_email
    
    app = create_app()
    with app.app_context():
        application = Application.query.get(application_id)
        if application:
            result = send_email(application)
            return {'success': result, 'application_id': application_id}
        return {'success': False, 'error': 'Application not found'}


@celery.task(bind=True)
def send_status_update(self, application_id):
    """Send status update notification."""
    from app import create_app
    from app.models import Application
    from app.utils.notifications import send_status_update_email
    
    app = create_app()
    with app.app_context():
        application = Application.query.get(application_id)
        if application:
            result = send_status_update_email(application)
            return {'success': result, 'application_id': application_id}
        return {'success': False, 'error': 'Application not found'}


@celery.task(bind=True)
def send_interview_invite(self, interview_id):
    """Send interview invitation email."""
    from app import create_app
    from app.models import Interview
    from app.utils.notifications import send_interview_invitation
    
    app = create_app()
    with app.app_context():
        interview = Interview.query.get(interview_id)
        if interview:
            result = send_interview_invitation(interview)
            return {'success': result, 'interview_id': interview_id}
        return {'success': False, 'error': 'Interview not found'}


@celery.task(bind=True)
def send_interview_reminder(self, interview_id):
    """Send interview reminder (24 hours before)."""
    from app import create_app
    from app.models import Interview
    from app.utils.notifications import send_interview_sms_reminder
    
    app = create_app()
    with app.app_context():
        interview = Interview.query.get(interview_id)
        if interview and interview.status == 'scheduled':
            result = send_interview_sms_reminder(interview)
            return {'success': result, 'interview_id': interview_id}
        return {'success': False, 'error': 'Interview not found or not scheduled'}


@celery.task(bind=True)
def send_offer_notification(self, offer_id):
    """Send job offer email."""
    from app import create_app
    from app.models import Offer
    from app.utils.notifications import send_offer_email
    
    app = create_app()
    with app.app_context():
        offer = Offer.query.get(offer_id)
        if offer:
            result = send_offer_email(offer)
            return {'success': result, 'offer_id': offer_id}
        return {'success': False, 'error': 'Offer not found'}


@celery.task(bind=True)
def auto_screen_applications(self, job_id):
    """Auto-screen all new applications for a job."""
    from app import create_app, db
    from app.models import Application
    from app.utils.screening import calculate_screening_score
    
    app = create_app()
    with app.app_context():
        applications = Application.query.filter_by(
            job_id=job_id,
            status='submitted'
        ).filter(
            Application.screening_score.is_(None)
        ).all()
        
        screened = 0
        for application in applications:
            application.screening_score = calculate_screening_score(application)
            application.status = 'under_review'
            application.current_stage = 'Screened'
            screened += 1
        
        db.session.commit()
        
        return {'job_id': job_id, 'screened': screened}


@celery.task(bind=True)
def sync_to_sharepoint(self, application_id):
    """Sync application documents to SharePoint."""
    from app import create_app, db
    from app.models import Application
    from app.utils.sharepoint import sync_documents_to_sharepoint
    
    app = create_app()
    with app.app_context():
        application = Application.query.get(application_id)
        if application:
            sync_documents_to_sharepoint(application)
            db.session.commit()
            return {'success': True, 'application_id': application_id}
        return {'success': False, 'error': 'Application not found'}


@celery.task(bind=True)
def generate_recruitment_report(self, job_id=None, report_type='summary'):
    """Generate recruitment report."""
    from app import create_app, db
    from app.models import JobPosting, Application, User
    
    app = create_app()
    with app.app_context():
        report = {
            'generated_at': datetime.utcnow().isoformat(),
            'report_type': report_type,
            'data': {}
        }
        
        if job_id:
            job = JobPosting.query.get(job_id)
            if not job:
                return {'success': False, 'error': 'Job not found'}
            
            applications = Application.query.filter_by(job_id=job_id).all()
            
            report['data'] = {
                'job': {
                    'reference': job.job_reference,
                    'title': job.title,
                    'department': job.department
                },
                'applications': {
                    'total': len(applications),
                    'by_status': {},
                    'avg_screening_score': 0
                }
            }
            
            scores = []
            for app in applications:
                status = app.status
                report['data']['applications']['by_status'][status] = \
                    report['data']['applications']['by_status'].get(status, 0) + 1
                if app.screening_score:
                    scores.append(app.screening_score)
            
            if scores:
                report['data']['applications']['avg_screening_score'] = sum(scores) / len(scores)
        
        else:
            # General summary
            report['data'] = {
                'total_jobs': JobPosting.query.count(),
                'active_jobs': JobPosting.query.filter_by(status='published').count(),
                'total_applications': Application.query.count(),
                'total_applicants': User.query.filter_by(role='applicant').count()
            }
        
        return {'success': True, 'report': report}


@celery.task(bind=True)
def check_closing_jobs(self):
    """Check for jobs closing soon and notify HR."""
    from app import create_app
    from app.models import JobPosting
    
    app = create_app()
    with app.app_context():
        # Jobs closing in next 3 days
        closing_soon = JobPosting.query.filter(
            JobPosting.status == 'published',
            JobPosting.closing_date <= datetime.utcnow() + timedelta(days=3),
            JobPosting.closing_date >= datetime.utcnow()
        ).all()
        
        # TODO: Send notification to HR about closing jobs
        
        return {
            'jobs_closing_soon': [
                {'id': job.id, 'reference': job.job_reference, 'closing_date': str(job.closing_date)}
                for job in closing_soon
            ]
        }


@celery.task(bind=True)
def expire_pending_offers(self):
    """Mark expired offers as expired."""
    from app import create_app, db
    from app.models import Offer
    
    app = create_app()
    with app.app_context():
        expired_offers = Offer.query.filter(
            Offer.status == 'pending',
            Offer.response_deadline < datetime.utcnow()
        ).all()
        
        count = 0
        for offer in expired_offers:
            offer.status = 'expired'
            count += 1
        
        db.session.commit()
        
        return {'expired_count': count}


# Periodic task scheduling (for beat scheduler)
celery.conf.beat_schedule = {
    'check-closing-jobs-daily': {
        'task': 'tasks.jobs.check_closing_jobs',
        'schedule': 86400.0,  # Every 24 hours
    },
    'expire-pending-offers': {
        'task': 'tasks.jobs.expire_pending_offers',
        'schedule': 3600.0,  # Every hour
    },
}
