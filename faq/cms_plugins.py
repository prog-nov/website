from cms.plugin_base import CMSPluginBase
from cms.plugin_pool import plugin_pool
from cms.models.pluginmodel import CMSPlugin
from django.utils.translation import gettext_lazy as _
from django.db import models
from faq.models import QuestionGroup


class FaqPluginModel(CMSPlugin):
    question_group = models.ForeignKey(QuestionGroup, on_delete=models.PROTECT)
    question_group.help_text ="Question group with questions to be displayed in this plugin."


class FaqPlugin(CMSPluginBase):
    name = _("FAQ")
    model = FaqPluginModel
    render_template = "faq/faq.html"
    text_enabled = False
    allow_children = False

    def render(self, context, instance, placeholder):
        context.update({
            'question_group': instance.question_group
        })
        return context


plugin_pool.register_plugin(FaqPlugin)
