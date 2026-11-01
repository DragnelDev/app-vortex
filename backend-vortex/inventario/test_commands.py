import os
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings


class CrearAdminPruebasCommandTest(TestCase):
    @override_settings(DEBUG=True)
    @patch.dict(os.environ, {
        "TEST_ADMIN_USERNAME": "admin",
        "TEST_ADMIN_EMAIL": "admin@example.com",
        "TEST_ADMIN_PASSWORD": "LocalTest-Password_928!",
    })
    def test_crea_superusuario_con_credenciales_configuradas(self):
        call_command("crear_admin_pruebas", verbosity=0)

        user = get_user_model().objects.get(username="admin")
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.check_password("LocalTest-Password_928!"))

    @override_settings(DEBUG=False)
    @patch.dict(os.environ, {"TEST_ADMIN_PASSWORD": "LocalTest-Password_928!"})
    def test_no_permite_crear_usuario_con_debug_desactivado(self):
        with self.assertRaisesMessage(CommandError, "solo se permite cuando DEBUG=True"):
            call_command("crear_admin_pruebas", verbosity=0)

    @override_settings(DEBUG=True)
    @patch.dict(os.environ, {"TEST_ADMIN_PASSWORD": ""})
    def test_exige_configurar_contrasena(self):
        with self.assertRaisesMessage(CommandError, "Configure TEST_ADMIN_PASSWORD"):
            call_command("crear_admin_pruebas", verbosity=0)

    @override_settings(DEBUG=True)
    @patch.dict(os.environ, {
        "TEST_ADMIN_USERNAME": "admin",
        "TEST_ADMIN_PASSWORD": "LocalTest-Password_928!",
    })
    def test_no_promueve_ni_modifica_usuario_existente(self):
        user_model = get_user_model()
        user_model.objects.create_user(username="admin", password="OriginalPassword-83!")

        with self.assertRaisesMessage(CommandError, "ya existe y no es superusuario"):
            call_command("crear_admin_pruebas", verbosity=0)

        user = user_model.objects.get(username="admin")
        self.assertFalse(user.is_staff)
        self.assertTrue(user.check_password("OriginalPassword-83!"))
