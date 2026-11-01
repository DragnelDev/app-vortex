"""Crea un superusuario local para pruebas usando credenciales del entorno."""
import os

from django.conf import settings
from django.contrib.auth import get_user_model, password_validation
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = "Crea un superusuario de pruebas (solo disponible con DEBUG=True)."

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Este comando solo se permite cuando DEBUG=True.")

        username = os.environ.get("TEST_ADMIN_USERNAME", "admin").strip()
        email = os.environ.get("TEST_ADMIN_EMAIL", "admin@example.com").strip()
        password = os.environ.get("TEST_ADMIN_PASSWORD", "")
        if not username:
            raise CommandError("TEST_ADMIN_USERNAME no puede estar vacío.")
        if not password:
            raise CommandError("Configure TEST_ADMIN_PASSWORD en el entorno o en .env.")

        user_model = get_user_model()
        user = user_model.objects.filter(username=username).first()
        if user:
            if not user.is_superuser:
                raise CommandError(
                    f"El usuario '{username}' ya existe y no es superusuario; no se modificó."
                )
            self.stdout.write(self.style.WARNING(
                f"El superusuario '{username}' ya existe; no se modificó."
            ))
            return

        user = user_model(username=username, email=email)
        password_validation.validate_password(password, user)
        user = user_model.objects.create_superuser(
            username=username,
            email=email,
            password=password,
        )
        self.stdout.write(self.style.SUCCESS(
            f"Superusuario de pruebas '{user.username}' creado."
        ))
