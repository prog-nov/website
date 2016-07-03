from django.conf.urls import url, include

from survey import views
import survey.api.urls

urlpatterns = [
    url(r'^$', views.survey_invitation, name='survey_invitation'),
    url(r'^api/', include(survey.api.urls, namespace='api')),  # nested namespace 'api'
    url(r'^(?P<survey_id>\d+)/$', views.survey_test, name='survey_test'),
    url(r'^done$', views.survey_done, name='survey_done'),
    url(r'^error$', views.survey_error, name='survey_error'),
]
