import re
import unicodedata
from datetime import date

from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q
from django.utils.translation import ugettext as _

import courses.models as models
from courses.utils import export
from .emailcenter import *

log = logging.getLogger('tq')


# Create your services here.
def get_all_offerings():
    return models.Offering.objects.order_by('period__date_from', '-active')


def get_offerings_to_display(request=None, force_preview=False):
    '''return offerings that have display flag on and order them by start date in ascending order'''
    if force_preview or (request and request.user.is_staff):
        return models.Offering.objects.filter(Q(display=True) | Q(period__date_to__gte=date.today())).order_by(
            'period__date_from')
    else:
        return models.Offering.objects.filter(display=True).order_by('-active', 'period__date_from')


def get_current_active_offering():
    return models.Offering.objects.filter(active=True).order_by('period__date_from').first()


def get_subsequent_offering():
    res = models.Offering.objects.filter(period__date_from__gte=date.today()).order_by(
        'period__date_from').all()
    if len(res) > 0:
        return res[0]
    else:
        return None


def update_user(user, user_data):
    if 'email' in user_data:
        user.email = user_data['email']
    if 'first_name' in user_data:
        user.first_name = user_data['first_name']
    if 'last_name' in user_data:
        user.last_name = user_data['last_name']
    user.save()

    profile = get_or_create_userprofile(user)

    # convenience method. if key is not given, assume same as attr
    def set_if_given(attr, key=None):
        if not key:
            key = attr
        if key in user_data:
            setattr(profile, attr, user_data[key])

    set_if_given('legi')
    set_if_given('gender')
    set_if_given('phone_number')
    set_if_given('student_status')
    set_if_given('body_height')
    set_if_given('newsletter')
    set_if_given('get_involved')

    set_if_given('picture')
    set_if_given('about_me')

    set_if_given('birthdate')
    set_if_given('nationality')
    set_if_given('residence_permit')
    set_if_given('ahv_number')

    if all((key in user_data) for key in ['street', 'plz', 'city']):
        if profile.address:
            profile.address.street = user_data['street']
            profile.address.plz = user_data['plz']
            profile.address.city = user_data['city']
            profile.address.save()
        else:
            profile.address = models.Address.objects.create_from_user_data(user_data)

    if all((key in user_data) for key in ['iban']):
        if profile.bank_account:
            profile.bank_account.iban = user_data['iban']
            profile.bank_account.bank_name = user_data['bank_name']
            profile.bank_account.bank_zip_code = user_data['bank_zip_code']
            profile.bank_account.bank_city = user_data['bank_city']
            profile.bank_account.bank_country = user_data['bank_country']
            profile.bank_account.save()
        else:
            profile.bank_account = models.BankAccount.objects.create_from_user_data(user_data)

    profile.save()

    return user


def find_unused_username_variant(name, ignore=None):
    un = name
    i = 1
    while User.objects.exclude(username=ignore).filter(username=un).count() > 0:
        un = name + str(i)
        i += 1
    return un


def clean_username(name):
    '''first try to find ascii similar character, then strip away disallowed characters still left'''
    name = unicodedata.normalize('NFKD', name)
    return re.sub('[^0-9a-zA-Z+-.@_]+', '', name)


def subscribe(course_id, data):
    '''Actually enrols a user or a pair of users in a course'''
    res = dict()

    course = models.Course.objects.get(id=course_id)
    user1 = models.UserProfile.objects.filter(user__id=data['user_id1'])
    assert user1.count() == 1
    user1 = user1[0]
    user2 = None
    if 'user_id2' in data:
        user2 = models.UserProfile.objects.filter(user__id=data['user_id2'])
        assert user2.count() == 1
        user2 = user2[0]

    if user1 == user2:
        res['tag'] = 'danger'
        res['text'] = 'Du kannst dich nicht mit dir selbst anmelden!'
    elif models.Subscribe.objects.filter(user=user1.user, course__id=course_id).count() > 0:
        res['tag'] = 'danger'
        res['text'] = 'Du ({}) bist schon für diesen Kurs angemeldet!'.format(user1.user.first_name)
        res['long_text'] = 'Wenn du einen Fehler bei der Anmeldung gemacht hast, wende dich an anmeldungen@tq.vseth.ch'
    elif user2 is not None and models.Subscribe.objects.filter(user=user2.user, course__id=course_id).count() > 0:
        res['tag'] = 'danger'
        res['text'] = 'Dein Partner {} ist schon für diesen Kurs angemeldet!'.format(user2.user.first_name)
        res['long_text'] = 'Wenn du einen Fehler bei der Anmeldung gemacht hast, wende dich an anmeldungen@tq.vseth.ch'
    else:
        if user2:
            subscription = models.Subscribe(user=user1.user, course=course, partner=user2.user,
                                            experience=data['experience'],
                                            comment=data['comment'])
        else:
            subscription = models.Subscribe(user=user1.user, course=course,
                                            experience=data['experience'],
                                            comment=data['comment'])
        subscription.derive_matching_state()
        subscription.save()
        send_subscription_confirmation(subscription)

        if user2:
            subscription.matching_state = models.Subscribe.MatchingState.COUPLE
            subscription.save()

            subscription2 = models.Subscribe(user=user2.user, course=course, partner=user1.user,
                                             experience=data['experience'], comment=data['comment'])
            subscription2.matching_state = models.Subscribe.MatchingState.COUPLE
            subscription2.save()
            send_subscription_confirmation(subscription2)

        res['tag'] = 'info'
        res['text'] = 'Anmeldung erfolgreich.'
        res['long_text'] = 'Du erhältst in Kürze eine Emailbestätigung.'

    return res


# creates a copy of course and sets its offering to the next offering in the future
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


# matches partners within the same course, considering their subscription time (fairness!) and respects also body_height (second criteria)
DEFAULT_BODY_HEIGHT = 170


def match_partners(subscriptions, request=None):
    courses = subscriptions.values_list('course', flat=True)
    match_count = 0
    for course_id in courses:
        single = subscriptions.filter(course__id=course_id, partner__isnull=True).all().exclude(
            state=models.Subscribe.State.REJECTED)
        sm = single.filter(user__profile__gender=models.UserProfile.Gender.MEN).order_by('date').all()
        sw = single.filter(user__profile__gender=models.UserProfile.Gender.WOMAN).order_by('date').all()
        c = min(sm.count(), sw.count())
        sm = list(sm[0:c])  # list() enforces evaluation of queryset
        sw = list(sw[0:c])
        sm.sort(key=lambda
            x: x.user.profile.body_height if x.user.profile and x.user.profile.body_height else DEFAULT_BODY_HEIGHT)
        sw.sort(key=lambda
            x: x.user.profile.body_height if x.user.profile and x.user.profile.body_height else DEFAULT_BODY_HEIGHT)
        while c > 0:
            c = c - 1
            m = sm[c]
            w = sw[c]
            m.partner = w.user
            m.matching_state = models.Subscribe.MatchingState.MATCHED
            m.save()
            w.partner = m.user
            w.matching_state = models.Subscribe.MatchingState.MATCHED
            w.save()
            match_count += 1
    if match_count:
        messages.add_message(request, messages.SUCCESS,
                             _(u'{} couples matched successfully').format(match_count))


def correct_matching_state_to_couple(subscriptions, request=None):
    corrected_count = 0

    for s in subscriptions.all():
        partner_subs = subscriptions.filter(user=s.partner, course=s.course)
        if partner_subs.count() == 1:
            partner_sub = partner_subs.first()
            # because we update matching state iteratively, we have to allow also COUPLE State
            allowed_states = [models.Subscribe.MatchingState.MATCHED, models.Subscribe.MatchingState.COUPLE]
            if s.matching_state == models.Subscribe.MatchingState.MATCHED and partner_sub.matching_state in allowed_states:
                s.matching_state = models.Subscribe.MatchingState.COUPLE
                s.save()
                corrected_count += 1

    if corrected_count:
        messages.add_message(request, messages.SUCCESS,
                             _(u'{} subscriptions ({} couples) corrected successfully').format(corrected_count,
                                                                                               corrected_count / 2))


def unmatch_partners(subscriptions, request):
    corrected_count = 0
    invalid_state_count = 0
    invalid_matching_state_count = 0
    for s in subscriptions.all():
        if s.state == models.Subscribe.State.NEW:
            allowed_states = [models.Subscribe.MatchingState.MATCHED]
            partner_subs = subscriptions.filter(user=s.partner, course=s.course)
            if partner_subs.count() == 1 and s.matching_state in allowed_states and partner_subs.first().matching_state in allowed_states:
                _unmatch_person(s)
                _unmatch_person(partner_subs.first())
                corrected_count += 1
            else:
                invalid_matching_state_count += 1
        else:
            invalid_state_count += 1

    invalid_matching_state_count -= corrected_count  # subtract wrongly counted errors

    if corrected_count:
        messages.add_message(request, messages.SUCCESS,
                             _(u'{} couples unmatched successfully').format(corrected_count))
    if invalid_state_count:
        messages.add_message(request, messages.WARNING,
                             _(u'{} subscriptions can not be unmatched because already CONFIRMED').format(
                                 invalid_state_count))
    if invalid_matching_state_count:
        messages.add_message(request, messages.WARNING,
                             _(u'{} subscriptions can not be unmatched because invalid matching state').format(
                                 invalid_matching_state_count))


def breakup_couple(subscriptions, request):
    corrected_count = 0
    invalid_state_count = 0
    invalid_matching_state_count = 0
    for s in subscriptions.all():
        if s.state == models.Subscribe.State.NEW:
            allowed_states = [models.Subscribe.MatchingState.COUPLE]
            partner_subs = subscriptions.filter(user=s.partner, course=s.course)
            if partner_subs.count() == 1 and s.matching_state in allowed_states and partner_subs.first().matching_state in allowed_states:
                _unmatch_person(s)
                _unmatch_person(partner_subs.first())
                corrected_count += 1
            else:
                invalid_matching_state_count += 1
        else:
            invalid_state_count += 1

    invalid_matching_state_count -= corrected_count  # subtract wrongly counted errors

    if corrected_count:
        messages.add_message(request, messages.SUCCESS,
                             _(u'{} couples broken up successfully').format(corrected_count))
    if invalid_state_count:
        messages.add_message(request, messages.WARNING,
                             _(u'{} couples can not be broken up because already CONFIRMED').format(
                                 invalid_state_count))
    if invalid_matching_state_count:
        messages.add_message(request, messages.WARNING,
                             _(u'{} couples can not be broken up because invalid matching state').format(
                                 invalid_matching_state_count))


def _unmatch_person(subscription):
    subscription.partner = None
    subscription.matching_state = models.Subscribe.MatchingState.TO_REMATCH
    subscription.save()


class NoPartnerException(Exception):
    def __str__(self):
        return 'This subscription has no partner set'


def confirm_subscription(subscription, request=None, allow_single_in_couple_course=False):
    '''sends a confirmation mail if subscription is confirmed (by some other method) and no confirmation mail was sent before'''
    # check: only people with partner are confirmed (in couple courses)
    if not allow_single_in_couple_course and subscription.course.type.couple_course and subscription.partner is None:
        raise NoPartnerException()

    if subscription.state == models.Subscribe.State.NEW:
        subscription.state = models.Subscribe.State.CONFIRMED
        subscription.save()

        m = send_participation_confirmation(subscription)
        if m:
            # log that we sent the confirmation
            c = models.Confirmation(subscription=subscription, mail=m)
            c.save()
            return True
        else:
            return False
    else:
        return False


# same as confirm_subscription, but for multiple subscriptions at once
MESSAGE_NO_PARTNER_SET = _(u'{} subscriptions were not confirmed because no partner set')


def confirm_subscriptions(subscriptions, request=None, allow_single_in_couple_course=False):
    no_partner_count = 0
    confirmed_count = 0
    for subscription in subscriptions:
        try:
            if confirm_subscription(subscription, request, allow_single_in_couple_course):
                confirmed_count += 1
        except NoPartnerException as e:
            no_partner_count += 1

    if no_partner_count:  # if any subscriptions not confirmed due to missing partner
        log.warning(MESSAGE_NO_PARTNER_SET.format(no_partner_count))
        if request:
            messages.add_message(request, messages.WARNING, MESSAGE_NO_PARTNER_SET.format(no_partner_count))
    if confirmed_count:
        messages.add_message(request, messages.SUCCESS,
                             _(u'{} of {} confirmed successfully').format(confirmed_count, len(subscriptions)))


def unconfirm_subscriptions(subscriptions, request=None):
    for s in subscriptions.all():
        if s.state == models.Subscribe.State.CONFIRMED:
            s.state = models.Subscribe.State.NEW
            s.save()


def reject_subscription(subscription, reason=None, send_email=True):
    '''sends a rejection mail if subscription is rejected (by some other method) and no rejection mail was sent before'''
    subscription.state = models.Subscribe.State.REJECTED
    subscription.save()
    if not reason:
        reason = detect_rejection_reason(subscription)
    c = models.Rejection(subscription=subscription, reason=reason, mail_sent=False)
    c.save()

    if send_email and models.Rejection.objects.filter(subscription=subscription, mail_sent=True).count() == 0:
        # if ensures that no mail was ever sent due to a rejection to this user

        # save if we sent the mail
        c.mail = send_rejection(subscription, reason)
        c.mail_sent = c.mail is not None
        c.save()


def reject_subscriptions(subscriptions, reason=None, send_email=True):
    '''same as reject_subscription, but for multiple subscriptions at once'''
    for subscription in subscriptions:
        reject_subscription(subscription, reason, send_email)


def unreject_subscriptions(subscriptions, request=None):
    unrejected_count = 0
    for subscription in subscriptions:
        if subscription.state == models.Subscribe.State.REJECTED:
            subscription.state = models.Subscribe.State.NEW
            subscription.save()
            unrejected_count += 1
    if unrejected_count:
        messages.add_message(request, messages.SUCCESS,
                             _(u'{} unrejected successfully').format(unrejected_count))


def welcome_teacher(teach):
    if not teach.welcomed:
        teach.welcomed = True
        teach.save()

        m = send_teacher_welcome(teach)
        if m:
            # log that we sent the confirmation
            c = models.TeacherWelcome(teach=teach, mail=m)
            c.save()
            return True
        else:
            return False
    else:
        return False


def welcome_teachers(courses, request):
    count = 0
    total = 0
    for course in courses:
        for teach in course.teaching.all():
            total += 1
            if welcome_teacher(teach):
                count += 1
    messages.add_message(request, messages.SUCCESS,
                         _(u'{} of {} welcomed successfully').format(count, total))


def welcome_teachers_reset_flag(courses, request):
    count = 0
    total = 0
    for course in courses:
        for teach in course.teaching.all():
            if teach.welcomed:
                count += 1
                teach.welcomed = False
                teach.save()
            total += 1
    messages.add_message(request, messages.SUCCESS,
                         _(u'{} of {} teachers reset successfully').format(count, total))


def get_or_create_userprofile(user):
    try:
        return models.UserProfile.objects.get(user=user)
    except ObjectDoesNotExist:
        userprofile = models.UserProfile(user=user)
        return userprofile


def calculate_relevant_experience(user, course):
    '''finds a list of courses the "user" did already and that are somehow relevant for "course"'''
    relevant_exp = [style.id for style in course.type.styles.all()]
    return [s.course for s in
            models.Subscribe.objects.filter(user=user, state__in=models.Subscribe.State.ACCEPTED_STATES,
                                            course__type__styles__id__in=relevant_exp).exclude(
                course=course).order_by('course__type__level').distinct().all()]


def format_prices(price_with_legi, price_without_legi, price_special=None):
    if price_special:
        return price_special
    elif price_with_legi and price_without_legi:
        if price_with_legi == price_without_legi:
            r = "{} CHF".format(price_with_legi.__str__())
        else:
            r = "mit Legi {} / sonst {} CHF".format(price_with_legi.__str__(), price_without_legi.__str__())
    elif price_without_legi:
        r = "mit Legi freier Eintritt (sonst {} CHF)".format(price_without_legi.__str__())
    else:
        r = None  # handle this case in template!
    return r


def model_attribute_language_fallback(model, attribute):
    for lang in [model.get_current_language()] + settings.PARLER_LANGUAGES['default']['fallbacks']:
        val = model.safe_translation_getter(attribute, language_code=lang)
        if val:
            return val
    return None


INVALID_TITLE_CHARS = re.compile(r'[^\w\-_ ]', re.IGNORECASE | re.UNICODE)


def export_subscriptions(course_ids, export_format):

    export_data = []
    for course_id in course_ids:
        course_name = models.Course.objects.get(id=course_id).name
        subscriptions = models.Subscribe.objects.accepted().filter(course_id=course_id).order_by('user__first_name')

        data = []
        if export_format == 'csv_google':
            data.append(['Given Name', 'Family Name', 'Gender',
                         'E-mail 1 - Type', 'E-mail 1 - Value', 'Phone 1 - Type', 'Phone 1 - Value'])
            for s in subscriptions:
                data.append([s.user.first_name, s.user.last_name, s.user.profile.gender, '* Private', s.user.email,
                             '* Private', s.user.profile.phone_number])

        if export_format == 'vcard':
            data = [subscription.user for subscription in subscriptions]
        else:
            data.append(
                ['Vorname', 'Nachname', 'Geschlecht', 'E-Mail', 'Mobile', 'Legi-Nr.', 'Zu bezahlen', 'Erfahrung'])

            for s in subscriptions:
                data.append([s.user.first_name, s.user.last_name, s.user.profile.gender, s.user.email,
                             s.user.profile.phone_number, s.user.profile.legi, s.get_price_to_pay(), s.experience])

        export_data.append({'name': course_name, 'data': data})

    if len(export_data) == 0:
        return None

    if len(export_data) == 1:
        course_name = export_data[0]['name']
        return export(export_format, title='Kursteilnehmer-{}'.format(course_name), data=export_data[0]['data'])

    return export(export_format, title="Kursteilnehmer", data=export_data, multiple=True)


def export_summary(export_format='csv', offerings=models.Offering.objects.all()):
    """exports a summary of all offerings with room usage, course/subscription numbers"""

    offering_ids = [o.pk for o in offerings]
    subscriptions = models.Subscribe.objects.accepted().filter(course__offering__in=offering_ids)

    filename = 'TQ-Room Usage-{}'.format(offerings[0].name if len(offerings) == 1 else "Multiple Offerings")
    export_data = []

    rooms = models.Room.objects.all()

    header = ['', 'TOTAL']
    header += [room.name for room in rooms]

    export_data.append(header)

    row = ['TOTAL', subscriptions.count()]
    row += [subscriptions.filter(course__room=room).count() for room in rooms]

    export_data.append(row)

    for offering in offerings:
        subs = models.Subscribe.objects.accepted().filter(course__offering=offering)
        row = [offering.name, subs.count()]
        row += [subs.filter(course__room=room).count() for room in rooms]
        export_data.append(row)

    return export(export_format, title=filename, data=export_data)


def export_teacher_payment_information(export_format='csv', offerings=models.Offering.objects.all()):
    """Exports a summary of the given ``offerings`` concerning payment of teachers.
    
    Contains profile data relevant for payment of teachers and how many lesson at what rate to be paid.
    
    :param export_format: export format
    :param offerings: offerings to include in summary
    :return: response or ``None`` if format not supported
    """
    offering_ids = [o.pk for o in offerings]
    teachs = models.Teach.objects.filter(course__offering__in=offering_ids)
    teachers = {teach.teacher for teach in teachs.all()}
    teachers = sorted(teachers, key=lambda t: t.last_name)

    filename = 'TQ-Salary-{}'.format(offerings[0].name if len(offerings) == 1 else "Multiple Offerings")

    export_data = []

    header = ['User ID', 'First Name', 'Family Name', 'Gender', 'E-mail', 'Phone']
    header += ['Street', 'PLZ', 'City', 'Country']
    header += ['Birthdate', 'Nationality', 'Residence Permit', 'AHV Number', 'IBAN', 'Bank']
    for o in offerings:
        header += ['Wage for ' + o.name]

    export_data.append(header)

    for user in teachers:
        row = [user.id, user.first_name, user.last_name, user.profile.gender, user.email,
               user.profile.phone_number]
        if user.profile.address:
            row += [user.profile.address.street, user.profile.address.plz, user.profile.address.city,
                    str(user.profile.address.country)]
        else:
            row += ["-"] * 4

        row += [user.profile.birthdate, str(user.profile.nationality), user.profile.residence_permit, user.profile.ahv_number]

        if user.profile.bank_account:
            row += [user.profile.bank_account.iban, user.profile.bank_account.bank_info_str()]
        else:
            row += ["-"] * 2

        # wages for each offering separately
        for o in offerings:
            offering_teacher_teachs = teachs.filter(course__offering=o, teacher=user).all()
            log.debug(list(offering_teacher_teachs))
            wage = 0
            for teach in offering_teacher_teachs:
                wage += teach.get_wage()
            row.append(wage)

        export_data.append(row)

    return export(export_format, title=filename, data=export_data)
