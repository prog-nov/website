from __future__ import annotations

from django.utils.translation import gettext_lazy as _

from datetime import date, timedelta
from decimal import Decimal
from numbers import Number
from typing import Optional, Union, Iterable

from django.conf import settings
from django.contrib import auth
from django.contrib.auth.models import User
from django.db import models
from django.db.models import QuerySet
from djangocms_text_ckeditor.fields import HTMLField
from parler.models import TranslatableModel, TranslatedFields

from courses import managers
from courses.models import PaymentMethod, Weekday, CourseSubscriptionType, LeadFollow, Subscribe, Period, \
    RegularLesson, IrregularLesson, RegularLessonException
from partners.models import Partner
from survey.models import Survey


class Course(TranslatableModel):
    # Mandatory fields
    name = models.CharField(max_length=255, blank=False)
    name.help_text = "This name is just for reference and is not displayed anywhere on the website."
    type = models.ForeignKey('CourseType', related_name='courses', blank=False, null=False, on_delete=models.PROTECT)
    type.help_text = "The name of the course type is displayed on the website as the course title ."
    subscription_type = models.CharField(max_length=20, blank=False, null=False,
                                         choices=CourseSubscriptionType.CHOICES,
                                         default=CourseSubscriptionType.REGULAR)
    display = models.BooleanField(default=True)
    display.help_text = "Defines if this course should be displayed on the Website " \
                        "(if checked, course is displayed if offering is displayed)."
    active = models.BooleanField(default=True)
    active.help_text = "Defines if clients can subscribe to this course " \
                       "(if checked, course is active if offering is active)."
    evaluated = models.BooleanField(default=False)
    evaluated.help_text = "If this course was evaluated by a survey or another way."

    # Optional - apply to all course types
    room = models.ForeignKey('Room', related_name='courses', blank=True, null=True, on_delete=models.PROTECT)
    offering = models.ForeignKey('Offering', blank=True, null=True, on_delete=models.PROTECT)
    offering.help_text = "Not required! Useful for regular courses or summer workshops. " \
                         "Do not use for irrgeular courses (e.g. ASVZ open classes)"
    period = models.ForeignKey('Period', blank=True, null=True, on_delete=models.PROTECT)
    period.help_text = "You can set a custom period for this course here. " \
                       "If this is left empty, the period from the offering is taken. " \
                       "Must be set if no offering associated but has regular lessons."

    # Translated fields
    translations = TranslatedFields(
        description=HTMLField(verbose_name='[TR] Description', blank=True, null=True,
                              help_text="Description specific for this course. "
                                        "(Gets displayed combined with the description of the course style)")
    )

    # For regular courses only
    min_subscribers = models.IntegerField(blank=True, null=True)
    max_subscribers = models.IntegerField(blank=True, null=True)

    # For external courses only
    external_url = models.URLField(max_length=500, blank=True, null=True)
    partner = models.ForeignKey(to=Partner, on_delete=models.SET_NULL, related_name='courses', blank=True, null=True)

    # Pricing
    price_with_legi = models.DecimalField(blank=True, null=True, decimal_places=2, max_digits=6, default=Decimal(35))
    price_without_legi = models.DecimalField(blank=True, null=True, decimal_places=2, max_digits=6, default=Decimal(70))
    price_special = models.CharField(max_length=255, blank=True, null=True)
    price_special.help_text = "Set this only if you want a different price schema."

    # Relations
    subscribers = models.ManyToManyField(settings.AUTH_USER_MODEL,
                                         through='Subscribe',
                                         related_name='courses',
                                         through_fields=('course', 'user'))
    preceding_courses = models.ManyToManyField('Course',
                                               related_name='succeeding_courses',
                                               through='CourseSuccession',
                                               through_fields=('successor', 'predecessor'))
    preceding_courses.help_text = "The course(s) that are immediate predecessors of this course."

    objects = managers.CourseManager()

    def participatory(self) -> QuerySet[Subscribe]:
        return self.subscriptions.accepted()

    def participants(self) -> set[User]:
        return {subscription.user for subscription in self.subscriptions.accepted()}

    def subscribed_user_ids(self) -> set[int]:
        return {subscription.user_id for subscription in self.subscriptions.all() if subscription.is_active()}

    def payment_totals(self) -> dict[str, Number]:
        """calculate different statistics in one method (performance optimization)"""
        totals = {
            'to_pay': 0,
            'paid': 0,
            'unpaid': 0,
            'paid_count': 0,
            'not_paid_count': 0,
            'paid_course': 0,
            'paid_voucher': 0,
            'paid_online': 0,
            'paid_counter': 0,
        }
        accepted = self.subscriptions.accepted()
        for subscription in accepted.all():
            amount = subscription.get_price_to_pay() or 0
            totals['to_pay'] += amount

        paid = accepted.paid()
        totals['paid_count'] = paid.count()
        totals['not_paid_count'] = accepted.count() - paid.count()
        for subscription in paid.all():
            amount = subscription.sum_of_payments() or 0
            totals['paid'] += amount
            totals['paid_voucher'] += subscription.sum_of_reductions()
            if subscription.paymentmethod == PaymentMethod.ONLINE:
                totals['paid_online'] += amount
            if subscription.paymentmethod == PaymentMethod.COURSE:
                totals['paid_course'] += amount
            if subscription.paymentmethod == PaymentMethod.COUNTER:
                totals['paid_counter'] += amount

        totals['unpaid'] = totals['to_pay'] - totals['paid'] - totals['paid_voucher']

        return totals

    def format_teachers(self) -> str:
        return ', '.join(map(auth.get_user_model().get_full_name, self.get_teachers()))

    def get_teachers(self) -> list[User]:
        return [t.teacher for t in self.teaching.all()]

    def surveys(self) -> set[Survey]:
        return {survey_instance.survey for survey_instance in self.survey_instances.all()}

    format_teachers.short_description = "Teachers"

    def get_teacher_ids(self) -> set[int]:
        return {t.teacher_id for t in self.teaching.all()}

    def format_prices(self) -> str:
        from courses.services import format_prices
        return format_prices(self.price_with_legi, self.price_without_legi, self.price_special)

    format_prices.short_description = "Prices"

    def format_description(self) -> str:
        from courses.services import model_attribute_language_fallback
        desc = ""
        desc += model_attribute_language_fallback(self, 'description') or ""
        desc += model_attribute_language_fallback(self.type, 'description') or ""
        return desc

    format_description.short_description = "Description"

    def is_custom_period(self) -> bool:
        return self.period is not None

    def get_period(self) -> Optional[Period]:
        if self.period is None:
            if self.offering:
                return self.offering.period
        else:
            return self.period
        return None

    def show_free_places_count(self) -> bool:
        return self.max_subscribers is not None

    def has_free_places(self) -> bool:
        return self.max_subscribers is None or self.get_free_places_count() > 0

    def has_free_places_for_leaders(self) -> bool:
        return self.has_free_places_for(LeadFollow.LEAD)

    def has_free_places_for_followers(self) -> bool:
        return self.has_free_places_for(LeadFollow.FOLLOW)

    def has_free_places_for(self, lead_or_follow) -> bool:
        if self.max_subscribers is None:
            return True

        free_places = self.get_free_places_count()
        if free_places == 0:
            return False

        matched_count = len({s for s in self.subscriptions.all() if s.is_matched()})
        total_for_preference = (self.max_subscribers - matched_count) / 2
        current_count_for_preference = \
            len({s for s in self.subscriptions.all() if s.is_single_with_preference(lead_or_follow)})
        free_for_preference = total_for_preference - current_count_for_preference

        return free_for_preference >= 1

    def get_free_places_count(self) -> Optional[int]:

        # No maximum => free places is not defined
        if self.max_subscribers is None:
            return None

        active_subscriptions_count = \
            len({subscription for subscription in self.subscriptions.all() if subscription.is_active()})

        total_count = self.max_subscribers - active_subscriptions_count
        total_count = int(max(total_count, 0))

        return total_count

    def get_confirmed_count(self) -> int:
        return self.subscriptions.accepted().count()

    def get_matched_and_individual_counts(self) -> tuple[int, int, int, int]:
        matched_count = self.subscriptions.active().matched().count()

        leads_count = self.subscriptions.active().to_match().leaders().count()
        follows_count = self.subscriptions.active().to_match().followers().count()
        no_preference_count = self.subscriptions.active().to_match().no_lead_follow_preference().count()

        return matched_count, leads_count, follows_count, no_preference_count

    def number_of_possible_couples(self) -> int:
        matched_count, leads_count, follows_count, no_preference_count = self.get_matched_and_individual_counts()

        smaller_set_size = min(leads_count, follows_count)
        larger_set_size = max(leads_count, follows_count)

        diff = larger_set_size - smaller_set_size

        if no_preference_count <= diff:
            return matched_count // 2 + smaller_set_size + no_preference_count

        remaining = no_preference_count - diff
        return matched_count // 2 + larger_set_size + remaining // 2

    def min_number_of_couples(self) -> int:
        return (self.min_subscribers + 1) // 2  # round up

    def has_enough_participants(self) -> bool:
        if self.min_subscribers is None:
            return True  # If there is no minimum number of subscribers, we always have enough participants

        if self.type.couple_course:
            return self.number_of_possible_couples() >= self.min_number_of_couples()

        return self.subscriptions.active().count() >= self.min_subscribers

    def participants_info_title(self) -> str:
        if self.subscriptions.active().count() == 0:
            return _("We did not receive any subscriptions yet.")

        if self.type.couple_course:
            matched_count, leads_count, follows_count, no_preference_count = self.get_matched_and_individual_counts()
            if matched_count // 2 + leads_count + follows_count + no_preference_count == 1:
                return _('Currently there is:')
            return _('Currently there are:')

        count = self.subscriptions.active().count()
        if count == 1:
            return _('We received one subscription so far.')
        return _('We received {} subscriptions so far.').format(count)

    def participants_info_list(self) -> list[str]:
        if not self.type.couple_course:
            return []

        matched_count, leads_count, follows_count, no_preference_count = self.get_matched_and_individual_counts()
        texts = []
        if matched_count:
            texts.append(_('One couple') if matched_count // 2 == 1 else
                         _('{} couples').format(matched_count // 2))
        if follows_count:
            texts.append(_('One individual follower') if follows_count == 1 else
                         _('{} individual followers').format(follows_count))
        if leads_count:
            texts.append(_('One individual leader') if leads_count == 1 else
                         _('{} individual leaders').format(leads_count))
        if no_preference_count:
            texts.append(_('One person with no lead or follow preference') if no_preference_count == 1 else
                         _('{} people with no lead or follow preference').format(no_preference_count))
        return texts

    def not_enough_participants_info(self) -> Optional[str]:
        if self.has_enough_participants():
            return None

        if self.type.couple_course:
            matched_count, leads_count, follows_count, no_preference_count = self.get_matched_and_individual_counts()

            if leads_count + follows_count + no_preference_count > 0:
                num_couples = self.number_of_possible_couples()
                if num_couples == 1:
                    return _('With this one couple is possible in total, but at least {} couples are needed.')\
                        .format(self.min_number_of_couples())
                return _('With this {} couples are possible in total, but at least {} couples are needed.')\
                    .format(num_couples, self.min_number_of_couples())

            return _('At least {} couples are needed.').format(self.min_number_of_couples())

        people_needed = self.min_subscribers - self.subscriptions.active().count()
        if people_needed == 1:
            return _('At least one more person is needed')
        return _('At least {} more people are needed.').format(people_needed)

    def has_style(self, style_name) -> bool:
        if style_name is None:
            return True

        for style in self.type.styles.all():
            if style.name == style_name:
                return True

            parent = style.parent_style
            while parent:
                if parent.name == style_name:
                    return True
                parent = parent.parent_style

        return False

    def is_displayed(self, preview: bool = False) -> bool:
        if self.offering is None:
            return self.display
        else:
            return preview or (self.offering.display and self.display)  # both must be true to be displayed

    def is_external(self) -> bool:
        return self.subscription_type == CourseSubscriptionType.EXTERNAL

    def is_open_class(self) -> bool:
        return self.subscription_type == CourseSubscriptionType.OPEN_CLASS

    def is_regular(self) -> bool:
        return self.subscription_type == CourseSubscriptionType.REGULAR

    def subscription_opens_soon(self) -> bool:
        period = self.get_period()
        if period is None or period.date_from is None:
            return False

        return self.subscription_closed() and period.date_from > date.today()

    def subscription_closed(self) -> bool:
        return self.is_regular() and not self.is_subscription_allowed()

    def is_subscription_allowed(self) -> bool:
        if not self.is_regular():
            return False

        if self.offering is None:
            return self.active

        return self.offering.active and self.active  # both must be true to allow subscription

    def is_over(self) -> bool:
        last_date = self.get_last_lesson_date()
        if last_date:
            return last_date < date.today()
        if self.get_period() and self.get_period().date_to is not None:
            return self.get_period().date_to < date.today()
        return False

    def get_lessons(self) -> list[Union[RegularLesson, IrregularLesson]]:
        lessons = []
        lessons.extend(self.regular_lessons.all())
        lessons.extend(self.irregular_lessons.all())
        return lessons

    def get_all_regular_lesson_exceptions(self) -> list[RegularLessonException]:
        exceptions = []
        for regular_lesson in self.regular_lessons.all():
            exceptions += [e for e in regular_lesson.exceptions.all() if e.is_applicable()]
        return exceptions

    def get_not_cancelled_regular_lesson_exceptions(self) -> list[RegularLessonException]:
        return [e for e in self.get_all_regular_lesson_exceptions() if not e.is_cancellation]

    def get_lessons_as_strings(self) -> Iterable[str]:
        return map(str, self.get_lessons())

    def format_lessons(self) -> str:
        return ' & '.join(self.get_lessons_as_strings())

    format_lessons.short_description = "Lessons"

    def get_regular_lesson_cancellation_dates(self) -> list[date]:
        def is_applicable(cancelled_date) -> bool:
            weekdays = [Weekday.NUMBERS[r.weekday] for r in self.regular_lessons.all()]
            if cancelled_date.weekday() not in weekdays:
                return False

            period = self.get_period()
            return period is None or period.date_from <= cancelled_date <= period.date_to

        return [d for d in self.get_cancellation_dates() if is_applicable(d)]

    def get_cancellation_dates(self) -> list[date]:
        dates = []
        for regular_lesson in self.regular_lessons.all():
            for exception in regular_lesson.exceptions.all():
                if exception.is_cancellation:
                    dates.append(exception.date)

        period = self.get_period()
        if period:
            dates += [c.date for c in period.cancellations.all()]
        return sorted(dates)

    def format_cancellations(self) -> str:
        dates = [d.strftime('%d.%m.%Y') for d in self.get_cancellation_dates()]
        return ' / '.join(dates)

    format_cancellations.short_description = "Cancellations"

    def format_preceeding_courses(self) -> str:
        return ' / '.join(map(str, self.preceding_courses.all()))

    format_preceeding_courses.short_description = "Predecessors"

    def get_first_regular_lesson(self) -> Optional[RegularLesson]:
        if self.regular_lessons.exists():
            return self.regular_lessons.all()[0]
        else:
            return None

    def get_first_irregular_lesson(self) -> Optional[IrregularLesson]:
        if self.irregular_lessons.exists():
            return self.irregular_lessons.first()
        return None

    def get_last_irregular_lesson(self) -> Optional[IrregularLesson]:
        if self.irregular_lessons.exists():
            return self.irregular_lessons.last()
        return None

    @staticmethod
    def next_weekday(d: date, weekday: int) -> date:
        days_ahead = weekday - d.weekday()
        if days_ahead < 0:  # Target day already happened
            days_ahead += 7
        return d + timedelta(days_ahead)

    def get_first_regular_lesson_date(self) -> Optional[date]:
        lesson = self.get_first_regular_lesson()
        period = self.get_period()
        if lesson and period and period.date_from:
            return Course.next_weekday(period.date_from, lesson.get_weekday_number())
        else:
            return None

    def get_last_regular_lesson_date(self) -> Optional[date]:
        period = self.get_period()
        if self.regular_lessons.exists() and period and period.date_to:
            course_weekdays = [Weekday.NUMBERS[lesson.weekday] for lesson in self.regular_lessons.all()]

            # Find last course day before date_to
            for day_delta in range(7):
                day = period.date_to - timedelta(days=day_delta)
                if day.weekday() in course_weekdays:
                    return day

        return None

    def get_first_irregular_lesson_date(self) -> Optional[date]:
        lesson = self.get_first_irregular_lesson()
        return lesson.date if lesson else None

    def get_last_irregular_lesson_date(self) -> Optional[date]:
        lesson = self.get_last_irregular_lesson()
        return lesson.date if lesson else None

    def get_first_lesson_date(self) -> Optional[date]:
        d1 = self.get_first_irregular_lesson_date()
        d2 = self.get_first_regular_lesson_date()
        if d1 is None and d2 is None:
            return None
        if d1 is None:
            return d2
        if d2 is None:
            return d1

        return d1 if d1 < d2 else d2

    def get_last_lesson_date(self) -> Optional[date]:
        d1 = self.get_last_irregular_lesson_date()
        d2 = self.get_last_regular_lesson_date()
        if d1 is None:
            return d2
        if d2 is None:
            return d1

        return d1 if d1 > d2 else d2

    def get_common_irregular_weekday(self) -> Optional[str]:
        """Returns a weekday string if all irregular lessons are on same weekday, otherwise returns None"""
        if self.irregular_lessons.exists():
            weekdays = [lesson.date.weekday() for lesson in self.irregular_lessons.all()]
            weekdays_unique = list(set(weekdays))
            if len(weekdays_unique) == 1:
                return Weekday.NUMBER_2_SLUG[weekdays_unique[0]]
            else:
                return None
        else:
            return None

    def get_teachers_welcomed(self) -> bool:
        return self.teaching.filter(welcomed=True).count() > 0

    get_teachers_welcomed.short_description = 'Teachers welcomed'
    get_teachers_welcomed.boolean = True

    def get_total_time(self) -> dict[str, Optional[float]]:
        totals = {
            'total': None,
            'regular': None,
            'irregular': None,
        }
        regular_times = [lesson.get_total_time() for lesson in list(self.regular_lessons.all())]
        irregular_times = [lesson.get_total_time() for lesson in list(self.irregular_lessons.all())]
        if all(t is not None for t in regular_times):
            totals['regular'] = sum(t.seconds / 3600 for t in regular_times)
        if all(t is not None for t in irregular_times):
            totals['irregular'] = sum(t.seconds / 3600 for t in irregular_times)
        try:
            totals['total'] = totals['regular'] + totals['irregular']
        except TypeError:
            pass
        return totals

    # create and stores identical copy of this course
    def copy(self) -> Course:
        old = Course.objects.get(pk=self.id)
        self.pk = None
        self.save()

        # copy regular lessons
        for lesson in old.regular_lessons.all():
            lesson.pk = None
            lesson.course = self
            lesson.save()

        # copy irregular lessons
        for lesson in old.irregular_lessons.all():
            lesson.pk = None
            lesson.course = self
            lesson.save()

        # copy teachers
        for teach in old.teaching.all():
            teach.pk = None
            teach.welcomed = False
            teach.course = self
            teach.save()

        return self

    # position field for ordering columns (grappelli feature)
    position = models.PositiveSmallIntegerField('Position', default=0)

    class Meta:
        ordering = ['position', 'name']

    def __str__(self) -> str:
        return "{} ({})".format(self.name, self.offering)
