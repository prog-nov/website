from django.contrib import admin
from django.contrib import messages
from django.db.models import QuerySet
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render
from django.urls import reverse

import courses.services.matching.change_matching
import courses.services.matching.do_matching
from courses.models import *
from payment.services import remind_of_payments
from . import services
from .admin_forms import CopyCourseForm, SendCourseEmailForm, RejectForm, EmailListForm
from .forms import SendVoucherForm


@admin.action(description="Set displayed")
def display(modeladmin, request, queryset):
    queryset.update(display=True)


@admin.action(description= "Set undisplayed")
def undisplay(modeladmin, request, queryset):
    queryset.update(display=False)


@admin.action(description="Activate")
def activate(modeladmin, request, queryset):
    queryset.update(active=True)


@admin.action(description="Deactivate")
def deactivate(modeladmin, request, queryset):
    queryset.update(active=False)


@admin.action(description="Create copy of courses in another offering")
def copy_courses(modeladmin, request, queryset):
    form = None

    if 'copy' in request.POST:
        form = CopyCourseForm(request.POST)

        if form.is_valid():
            offering = form.cleaned_data['offering']

            for c in queryset:
                services.courses.copy_course(c, to=offering, set_preceeding_course=form.cleaned_data['set_preceeding_course'])

            return HttpResponseRedirect(request.get_full_path())

    if not form:
        form = CopyCourseForm(
            initial={'_selected_action': map(str, queryset.values_list('id', flat=True)),
                     'offering': services.get_subsequent_offering(),
                     'set_preceeding_course': True})

    return render(request, 'courses/auth/action_copy_course.html', {'courses': queryset,
                                                                    'copy_form': form,
                                                                    })


@admin.action(description="Confirm selected subscriptions")
def confirm_subscriptions(modeladmin, request, queryset):
    # manually send confirmation mails
    services.subscriptions.confirm_subscriptions(queryset, request)


@admin.action(description="Confirm selected subscriptions (allow singles in couple courses)")
def confirm_subscriptions_allow_singles(modeladmin, request, queryset):
    # manually send confirmation mails
    services.subscriptions.confirm_subscriptions(queryset, request, True)


@admin.action(description="Unconfirm subscriptions (be sure to reconfirm them later!)")
def unconfirm_subscriptions(modeladmin, request, queryset):
    # manually send confirmation mails
    services.subscriptions.unconfirm_subscriptions(queryset, request)


@admin.action(description="Send payment reminder to the selected subscriptions (which are in TO_PAY state)")
def payment_reminder(modeladmin, request, queryset):
    remind_of_payments(queryset, request)


@admin.action(description="Reject selected subscriptions")
def reject_subscriptions(self, request, queryset):
    form = None

    if 'reject' in request.POST:
        form = RejectForm(request.POST)

        if form.is_valid():
            reason = form.cleaned_data['reason']

            services.subscriptions.reject_subscriptions(queryset, reason, form.cleaned_data['send_email'])

            return HttpResponseRedirect(request.get_full_path())

    if not form:
        selected_action = map(str, queryset.values_list('id', flat=True))
        form = RejectForm(
            initial={'_selected_action': selected_action, 'send_email': True})

    return render(request, 'courses/auth/action_reject.html', {'subscriptions': queryset,
                                                               'reason_form': form,
                                                               })


@admin.action(description="Unreject subscriptions")
def unreject_subscriptions(modeladmin, request, queryset):
    # manually send confirmation mails
    services.subscriptions.unreject_subscriptions(queryset, request)


@admin.action(description="Match partners (chronologically, body height optimal)")
def match_partners(modeladmin, request, queryset):
    services.match_partners(queryset, request)


@admin.action(description="Unmatch partners (both partners must be selected and unconfirmed)")
def unmatch_partners(modeladmin, request, queryset):
    courses.services.matching.change_matching.unmatch_partners(queryset, request)


@admin.action(description="Break up (unmatch) couple (both couple partners must be selected and unconfirmed)")
def breakup_couple(modeladmin, request, queryset):
    courses.services.matching.change_matching.breakup_couple(queryset, request)


@admin.action(description="Correct matching_state to COUPLE (both partners must be matched together, can already be confirmed)")
def correct_matching_state_to_couple(modeladmin, request, queryset):
    courses.services.matching.change_matching.correct_matching_state_to_couple(queryset, request)


def welcome_teachers(modeladmin, request, queryset):
    services.teachers.welcome_teachers(queryset, request)


def welcome_teachers_reset_flag(modeladmin, request, queryset):
    services.teachers.welcome_teachers_reset_flag(queryset, request)

@admin.action(description="Set selected subscriptions as paid")
def set_subscriptions_as_paid(modeladmin, request, queryset):
    queryset.filter(state=SubscribeState.CONFIRMED).update(state=SubscribeState.COMPLETED)


@admin.action(description="Export confirmed subscriptions of selected courses as CSV")
def export_confirmed_subscriptions_csv(modeladmin, request, queryset):
    ids = []
    for c in queryset:
        ids.append(c.id)
    return services.export_subscriptions(ids, 'csv')


@admin.action(description="Export confirmed subscriptions of selected courses as Google Contacts readable CSV")
def export_confirmed_subscriptions_csv_google(modeladmin, request, queryset):
    ids = []
    for c in queryset:
        ids.append(c.id)
    return services.export_subscriptions(ids, 'csv_google')


@admin.action(description="Export confirmed subscriptions of selected courses as vCard")
def export_confirmed_subscriptions_vcard(modeladmin, request, queryset):
    ids = []
    for c in queryset:
        ids.append(c.id)
    return services.export_subscriptions(ids, 'vcard')


@admin.action(description="Export confirmed subscriptions of selected courses as XLSX")
def export_confirmed_subscriptions_xlsx(modeladmin, request, queryset):
    ids = []
    for c in queryset:
        ids.append(c.id)
    return services.export_subscriptions(ids, 'xlsx')


@admin.action(description="Export teacher payment information as CSV")
def export_teacher_payment_information_csv(modeladmin, request, queryset):
    return services.export_teacher_payment_information(offerings=queryset.all())


@admin.action(description="Export teacher payment information as Excel")
def export_teacher_payment_information_excel(modeladmin, request, queryset):
    return services.export_teacher_payment_information(offerings=queryset.all(), export_format='excel')


@admin.action(description="Mark selected vouchers as used")
def mark_voucher_as_used(modeladmin, request, queryset):
    # mark vouchers as used
    for voucher in queryset:
        voucher.mark_as_used(user=request.user, comment="by admin action")


@admin.action(description="Send a voucher to users of selected subscriptions")
def send_vouchers_for_subscriptions(modeladmin, request, queryset):
    form = None

    if 'go' in request.POST:
        form = SendVoucherForm(data=request.POST)

        if form.is_valid():
            recipients = [subscription.user for subscription in queryset]
            services.courses.send_vouchers(data=form.cleaned_data, recipients=recipients)
            return HttpResponseRedirect(request.get_full_path())

    if not form:
        form = SendVoucherForm(initial={'_selected_action': map(str, queryset.values_list('id', flat=True))})

    context = {
        'form': form,
        'action': 'send_vouchers_for_subscriptions',
    }
    return render(request, 'courses/auth/action_send_voucher.html', context)


@admin.action(description="Send an email to all participants of the selected course(s)")
def send_course_email(modeladmin, request, queryset) -> HttpResponse:
    form = None

    if 'go' in request.POST:
        form = SendCourseEmailForm(data=request.POST)

        if form.is_valid():
            services.courses.send_course_email(data=form.cleaned_data, courses=queryset)
            return HttpResponseRedirect(request.get_full_path())

    if not form:
        form = SendCourseEmailForm(initial={'_selected_action': map(str, queryset.values_list('id', flat=True))})

    return render(request, 'courses/auth/action_send_course_email.html', {'courses': queryset, 'evaluate_form': form})


@admin.action(description="Undo voucher payment")
def undo_voucher_payment(modeladmin, request, queryset: QuerySet[Subscribe]):
    for subscription in queryset:
        if subscription.state in [SubscribeState.PAID,
                                  SubscribeState.COMPLETED] and subscription.paymentmethod == PaymentMethod.VOUCHER:
            subscription.state = SubscribeState.CONFIRMED
            for voucher in Voucher.objects.filter(subscription=subscription).all():
                voucher.subscription = None
                voucher.used = False
                voucher.save()
                subscription.price_reductions.filter(used_voucher=voucher).delete()
        subscription.save()


@admin.action(description="raise price to pay to fit amount")
def raise_price_to_pay(modeladmin, request, queryset):
    for subscription_payment in queryset:
        subscription: Subscribe = subscription_payment.subscription
        balance = subscription.sum_of_payments() - subscription.price_after_reductions()
        if balance > 0:
            subscription.price_to_pay += balance
            subscription.save()


@admin.action(description="List emails of selected subscribers")
def emaillist(modeladmin, request, queryset):
    form = None

    if 'ok' in request.POST:
        form = EmailListForm(request.POST)

        if form.is_valid():
            return HttpResponseRedirect(reverse('admin:courses_subscribe_changelist'))

    if not form:
        form = EmailListForm()

    return render(request, 'courses/auth/action_emaillist.html', {
        'form': form,
        'emails': [s.user.email + ';' for s in queryset.all()],
        'message': "Email addresses of selected subscribers (note that selected filters are applied!)"
    })


@admin.action(description="List emails of accepted participants")
def offering_emaillist(modeladmin, request, queryset):
    form = None

    if 'ok' in request.POST:
        form = EmailListForm(request.POST)

        if form.is_valid():
            return HttpResponseRedirect(reverse('admin:courses_offering_changelist'))

    if not form:
        form = EmailListForm()

    subscriptions = Subscribe.objects.accepted().filter(course__offering__in=queryset.all())
    return render(request, 'courses/auth/action_emaillist.html', {
        'form': form,
        'emails': [s.user.email for s in subscriptions],
        'message': "Email addresses of accepted subscribers of offerings {}".format(", ".join(map(str, queryset.all())))
    })


def make_inactive(modeladmin, request, queryset):
    for user in queryset:

        user.is_active = False
        user.save()
    messages.add_message(request, messages.SUCCESS, 'Deactivated {} profiles'.format(queryset.count()))
