from datetime import datetime
from typing import Iterable, Any, Optional

from django.contrib.auth.models import User
from post_office.models import EmailTemplate

from courses import models as models
from courses.models import Voucher, Course
from courses.services import get_subsequent_offering
from courses.services.general import log
from email_system.services import send_all_emails
from payment.utils.generate_voucher_pdf import generate_voucher_pdfs
from survey.models import SurveyInstance, Survey
from tq_website import settings


def copy_course(course, to=None, set_preceeding_course=False):
    old_course_pk = course.pk
    if to is None:
        to = get_subsequent_offering()
    if to is not None:
        course_copy = course.copy()
        course_copy.offering = to
        course_copy.active = False
        course_copy.save()

        if set_preceeding_course:
            cs = models.CourseSuccession(predecessor=models.Course.objects.get(pk=old_course_pk), successor=course)
            cs.save()


def send_course_email(data: dict[str, Any], courses: Iterable[Course]) -> None:
    email_template: Optional[EmailTemplate] = data['email_template']
    email_subject: Optional[str] = data['email_subject']
    email_content: Optional[str] = data['email_content']
    send_to_participants: bool = data['send_to_participants']
    send_to_teachers: bool = data['send_to_teachers']
    survey: Optional[Survey] = data['survey']
    survey_url_expire_date: Optional[datetime] = data['survey_url_expire_date']

    emails = []

    for course in courses:
        recipients: list[User] = []
        if send_to_participants:
            recipients += [p.user for p in course.participatory().all()]
        if send_to_teachers:
            recipients += course.get_teachers()

        for recipient in recipients:

            # Get context for email
            context = {
                'first_name': recipient.first_name,
                'last_name': recipient.last_name,
                'course': course.type.name,
                'offering': course.offering.name,
            }

            if survey:
                survey_instance = SurveyInstance.objects.create(
                    survey=survey,
                    email_template=email_template,
                    course=course,
                    user=recipient,
                    url_expire_date=survey_url_expire_date
                )
                context['survey_url'] = survey_instance.create_full_url()
                context['survey_expiration'] = survey_instance.url_expire_date

            subject: str = email_subject or email_template.subject
            html_message: str = email_content or email_template.html_content

            emails.append(dict(
                to=recipient.email,
                reply_to=settings.EMAIL_ADDRESS_COURSES,
                subject=subject,
                message=email_template.content,
                html_message=html_message,
                context=context,
            ))

    log.info('Sending {} emails'.format(len(emails)))
    send_all_emails(emails)


def send_vouchers(data, recipients):
    percentage = data['percentage']
    purpose = data['purpose']
    expires_flag = data['expires_flag']
    expires = data['expires']

    emails = []

    for recipient in recipients:
        voucher = Voucher(purpose=purpose, percentage=percentage, expires=expires if expires_flag else None)
        voucher.save()
        generate_voucher_pdfs(vouchers=[voucher])

        email_context = {
            'first_name': recipient.first_name,
            'last_name': recipient.last_name,
            'voucher_key': voucher.key,
            'voucher_url': voucher.pdf_file.url,
        }

        emails.append(dict(
            to=recipient.email,
            template='voucher',
            context=email_context,
            attachments={'Voucher.pdf': voucher.pdf_file.file}
        ))

    log.info('Sending {} emails'.format(len(emails)))
    send_all_emails(emails)
