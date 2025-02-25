from django.db import models
from djangocms_text_ckeditor.fields import HTMLField
from parler.models import TranslatableModel, TranslatedFields


class CourseType(TranslatableModel):
    name = models.CharField(max_length=255, unique=True, blank=False)
    styles = models.ManyToManyField('Style', related_name='course_types', blank=True)
    level = models.IntegerField(default=None, blank=True, null=True)
    couple_course = models.BooleanField(default=True)

    translations = TranslatedFields(
        description=HTMLField(verbose_name='[TR] Description', blank=True, null=True,
                              help_text="This text is added to the description of each course instance.")
    )

    def format_styles(self) -> str:
        return ', '.join(map(str, self.styles.all()))

    format_styles.short_description = "Styles"

    def __str__(self) -> str:
        return "{}".format(self.name)

    class Meta:
        ordering = ['name', 'level']
