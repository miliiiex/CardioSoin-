from django.conf import settings

from accounts.email_config import mail_is_ready


def email_setup(request):
    return {
        "show_email_setup_link": settings.DEBUG and not mail_is_ready(),
    }
