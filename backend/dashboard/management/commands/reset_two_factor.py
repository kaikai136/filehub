from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from dashboard.models import AuthChallenge, UserTwoFactor


class Command(BaseCommand):
    help = "Reset a user's TOTP binding from a trusted server console."

    def add_arguments(self, parser):
        parser.add_argument("username")

    def handle(self, *args, **options):
        with transaction.atomic():
            user = get_user_model().objects.select_for_update().filter(username=options["username"]).first()
            if not user:
                raise CommandError("用户不存在")
            record, _ = UserTwoFactor.objects.get_or_create(user=user)
            record.encrypted_secret = ""
            record.enabled = False
            record.required = True
            record.bound_at = None
            record.last_step = -1
            record.save(update_fields=["encrypted_secret", "enabled", "required", "bound_at", "last_step"])
            AuthChallenge.objects.filter(kind__in=["login_2fa", "login_2fa_setup"], payload__user_id=user.pk).delete()
        self.stdout.write(self.style.SUCCESS("双因素绑定已重置，用户下次登录需要重新绑定"))
