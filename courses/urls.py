from django.conf.urls import include
from django.urls import path

import courses.api.urls
from courses import admin_views
from courses import views

app_name = 'courses'
urlpatterns = [
    path('', views.course_list, name='home'),
    path('list/', views.course_list, name='list'),
    path('list/<subscription_type>/<style_name>/', views.course_list, name='list_style'),
    path('preview/', views.course_list_preview, name='list_preview'),
    path('archive/', views.archive, name='archive'),
    path('<int:course_id>/detail/', views.course_detail, name='course_detail'),
    path('<int:course_id>/subscribe/', views.subscribe_form, name='subscribe'),
    path('offering/<int:offering_id>/', views.offering_by_id, name='offering_by_id'),
    path('auth/', views.subscription_overview, name='subscription_overview'),
    path('auth/export/', views.export_summary, name='export_summary'),
    path('auth/export/excel', views.export_summary_excel, name='export_summary_excel'),
    path('auth/export/<int:offering_id>/', views.export_offering_summary, name='export_offering_summary'),
    path('auth/export/<int:offering_id>/excel', views.export_offering_summary_excel, name='export_offering_summary_excel'),
    path('auth/export/teacher/<int:offering_id>/', views.export_offering_teacher_payment_information, name='export_offering_salary'),
    path('auth/export/teacher/<int:offering_id>/excel', views.export_offering_teacher_payment_information_excel, name='export_offering_salary_excel'),
    path('auth/offering/<int:offering_id>/', views.offering_overview, name='offering_overview'),
    path('admin/voucher_generate/', admin_views.voucher_generation_view, name='voucher_generation'),
    path('api/', include(courses.api.urls, namespace='courses_api')),  # nested namespace 'api'
]
