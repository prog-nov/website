from cms.app_base import CMSApp
from cms.apphook_pool import apphook_pool
from django.utils.translation import gettext_lazy as _


@apphook_pool.register
class PhotosApphook(CMSApp):
    name = _("Photos")
    app_name = "photos"

    def get_urls(self, page=None, language=None, **kwargs):
        return ["photologue.urls"]

