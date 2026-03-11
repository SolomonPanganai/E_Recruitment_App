"""Email and SMS notification utilities."""
from flask import current_app, render_template_string
from flask_mail import Message
from app import mail


def send_email(to, subject, template, **kwargs):
    """Send an email."""
    try:
        msg = Message(
            subject=subject,
            recipients=[to] if isinstance(to, str) else to,
            sender=current_app.config['MAIL_DEFAULT_SENDER']
        )
        msg.html = render_template_string(template, **kwargs)
        mail.send(msg)
        return True
    except Exception as e:
        current_app.logger.error(f'Failed to send email to {to}: {e}')
        return False


def send_application_confirmation(application):
    """Send application confirmation email to applicant."""
    template = """
    <h2>Application Received</h2>
    <p>Dear {{ application.applicant.first_name }},</p>
    <p>Thank you for your application for the position of <strong>{{ application.job.title }}</strong>.</p>
    <p>Your application reference number is: <strong>{{ application.application_reference }}</strong></p>
    <p>We will review your application and contact you regarding the next steps.</p>
    <br>
    <p>Best regards,<br>HR Department</p>
    """
    
    return send_email(
        to=application.applicant.email,
        subject=f'Application Received - {application.job.title}',
        template=template,
        application=application
    )


def send_status_update_email(application):
    """Send status update email to applicant."""
    status_messages = {
        'under_review': 'Your application is now under review.',
        'shortlisted': 'Congratulations! You have been shortlisted for the next stage.',
        'interviewed': 'Thank you for attending the interview.',
        'offered': 'We are pleased to extend a job offer to you!',
        'rejected': 'We regret to inform you that your application was not successful.',
        'withdrawn': 'Your application has been withdrawn as requested.'
    }
    
    message = status_messages.get(
        application.status, 
        f'Your application status has been updated to: {application.status}'
    )
    
    template = """
    <h2>Application Status Update</h2>
    <p>Dear {{ application.applicant.first_name }},</p>
    <p>{{ message }}</p>
    <p><strong>Position:</strong> {{ application.job.title }}<br>
    <strong>Reference:</strong> {{ application.application_reference }}<br>
    <strong>Current Stage:</strong> {{ application.current_stage }}</p>
    <br>
    <p>Best regards,<br>HR Department</p>
    """
    
    return send_email(
        to=application.applicant.email,
        subject=f'Application Update - {application.job.title}',
        template=template,
        application=application,
        message=message
    )


def send_interview_invitation(interview, is_reschedule=False):
    """Send interview invitation email."""
    application = interview.application
    
    if is_reschedule:
        subject = f'Interview Rescheduled - {application.job.title}'
        header = 'Interview Rescheduled'
        intro_text = 'Your interview has been rescheduled. Please note the new details below:'
    else:
        subject = f'Interview Invitation - {application.job.title}'
        header = 'Interview Invitation'
        intro_text = f'We are pleased to invite you for an interview for the position of <strong>{application.job.title}</strong>.'
    
    template = f"""
    <h2>{header}</h2>
    <p>Dear {{{{ application.applicant.first_name }}}},</p>
    <p>{intro_text}</p>
    <p><strong>Date:</strong> {{{{ interview.scheduled_date.strftime('%A, %d %B %Y') }}}}<br>
    <strong>Time:</strong> {{{{ interview.start_time.strftime('%H:%M') }}}} - {{{{ interview.end_time.strftime('%H:%M') }}}}<br>
    <strong>Type:</strong> {{{{ interview.interview_type.replace('_', ' ').title() }}}}<br>
    <strong>Location:</strong> {{{{ interview.location }}}}</p>
    <p>Please confirm your attendance by replying to this email.</p>
    <br>
    <p>Best regards,<br>HR Department</p>
    """
    
    return send_email(
        to=application.applicant.email,
        subject=subject,
        template=template,
        application=application,
        interview=interview
    )


def send_offer_email(offer):
    """Send job offer email."""
    application = offer.application
    
    template = """
    <h2>Job Offer</h2>
    <p>Dear {{ application.applicant.first_name }},</p>
    <p>We are delighted to extend an offer of employment for the position of <strong>{{ application.job.title }}</strong>.</p>
    <p><strong>Salary:</strong> {{ offer.salary_offered }}<br>
    <strong>Proposed Start Date:</strong> {{ offer.start_date_proposed.strftime('%d %B %Y') }}<br>
    <strong>Response Deadline:</strong> {{ offer.response_deadline.strftime('%d %B %Y') }}</p>
    {% if offer.terms %}
    <p><strong>Terms:</strong><br>{{ offer.terms }}</p>
    {% endif %}
    <p>Please log in to your account to accept or decline this offer.</p>
    <br>
    <p>Congratulations!<br>HR Department</p>
    """
    
    return send_email(
        to=application.applicant.email,
        subject=f'Job Offer - {application.job.title}',
        template=template,
        application=application,
        offer=offer
    )


def send_rejection_email(application):
    """Send rejection email to applicant."""
    template = """
    <h2>Application Status Update</h2>
    <p>Dear {{ application.applicant.first_name }},</p>
    <p>Thank you for your interest in {{ application.job.title }} at our organization.</p>
    <p>We regret to inform you that after careful consideration of your application, we have decided not to move forward at this time. 
    We appreciate the time and effort you invested in applying and wish you success in your future endeavors.</p>
    <p><strong>Position:</strong> {{ application.job.title }}<br>
    <strong>Reference:</strong> {{ application.application_reference }}</p>
    <p>We encourage you to apply for other suitable positions in the future.</p>
    <br>
    <p>Best regards,<br>HR Department</p>
    """
    
    return send_email(
        to=application.applicant.email,
        subject=f'Application Update - {application.job.title}',
        template=template,
        application=application
    )


# SMS Functions (placeholder - implement based on your SMS provider)

def send_sms(phone_number, message):
    """Send an SMS message."""
    # Placeholder for SMS gateway integration
    # Example: Twilio, BulkSMS, etc.
    try:
        api_key = current_app.config.get('SMS_API_KEY')
        if not api_key:
            current_app.logger.warning('SMS_API_KEY not configured')
            return False
        
        # Implement your SMS provider logic here
        # Example with Twilio:
        # from twilio.rest import Client
        # client = Client(api_key, current_app.config['SMS_API_SECRET'])
        # message = client.messages.create(
        #     body=message,
        #     from_=current_app.config['SMS_SENDER_ID'],
        #     to=phone_number
        # )
        
        current_app.logger.info(f'SMS sent to {phone_number}: {message[:50]}...')
        return True
    except Exception as e:
        current_app.logger.error(f'Failed to send SMS to {phone_number}: {e}')
        return False


def send_interview_sms_reminder(interview):
    """Send SMS reminder for interview."""
    application = interview.application
    phone = application.applicant.phone
    
    if not phone:
        return False
    
    message = (
        f"Reminder: Interview for {application.job.title} on "
        f"{interview.scheduled_date.strftime('%d %b')} at "
        f"{interview.start_time.strftime('%H:%M')}. "
        f"Ref: {application.application_reference}"
    )
    
    return send_sms(phone, message)
