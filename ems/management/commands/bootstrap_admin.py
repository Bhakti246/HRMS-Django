import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create the initial production admin from environment variables, if configured."

    def handle(self, *args, **options):
        username = os.environ.get("DJANGO_SUPERUSER_USERNAME", "").strip()
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "").strip()
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "")
        if not username or not password:
            self.stdout.write("Admin bootstrap skipped; credentials are not configured.")
            return

        User = get_user_model()
        user, created = User.objects.get_or_create(
            username=username,
            defaults={"email": email, "is_staff": True, "is_superuser": True},
        )
        if created:
            user.set_password(password)
            user.save(update_fields=["password"])
            self.stdout.write(self.style.SUCCESS("Initial admin account created."))
        else:
            if os.environ.get("DJANGO_SUPERUSER_RESET_PASSWORD", "").lower() in {"1", "true", "yes"}:
                user.set_password(password)
                user.is_staff = True
                user.is_superuser = True
                user.save(update_fields=["password", "is_staff", "is_superuser"])
                self.stdout.write(self.style.SUCCESS("Existing admin password was reset."))
            else:
                self.stdout.write("Admin account already exists; password was not changed.")
