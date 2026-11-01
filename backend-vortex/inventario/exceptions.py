"""Traduce los errores de dominio y de validación de Django a respuestas HTTP coherentes."""
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler

from .models import (
    BorradoFisicoProhibidoError,
    InventarioError,
    ModificacionProhibidaError,
    StockInsuficienteError,
)


def manejador_excepciones(exc, context):
    if isinstance(exc, DjangoValidationError):
        detalle = exc.message_dict if hasattr(exc, 'error_dict') else {'detail': exc.messages}
        return Response(detalle, status=status.HTTP_400_BAD_REQUEST)

    if isinstance(exc, IntegrityError):
        return Response(
            {'detail': 'Ya existe un registro con esos datos o se viola una restricción de integridad.',
             'code': 'integridad'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if isinstance(exc, StockInsuficienteError):
        return Response(
            {
                'detail': str(exc),
                'code': 'stock_insuficiente',
                'disponible': str(exc.disponible),
                'solicitado': str(exc.solicitado),
            },
            status=status.HTTP_409_CONFLICT,
        )

    if isinstance(exc, (BorradoFisicoProhibidoError, ModificacionProhibidaError)):
        return Response({'detail': str(exc), 'code': 'operacion_prohibida'}, status=status.HTTP_409_CONFLICT)

    if isinstance(exc, InventarioError):
        return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    return exception_handler(exc, context)
