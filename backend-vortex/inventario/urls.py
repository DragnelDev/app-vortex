from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("sucursales", views.SucursalViewSet)
router.register("almacenes", views.AlmacenViewSet)
router.register("categorias", views.CategoriaViewSet)
router.register("unidades", views.UnidadMedidaViewSet)
router.register("productos", views.ProductoViewSet)
router.register("terceros", views.TerceroViewSet)
router.register("tipos-movimiento", views.TipoMovimientoViewSet)
router.register("movimientos", views.MovimientoViewSet)
router.register("stock", views.StockViewSet)

urlpatterns = [
    path("auth/me/", views.MeView.as_view(), name="me"),
    path("dashboard/resumen/", views.DashboardResumenView.as_view(), name="dashboard-resumen"),
    path("kardex/", views.KardexView.as_view(), name="kardex"),
    path("kardex/exportar/", views.KardexExportarView.as_view(), name="kardex-exportar"),
    path("", include(router.urls)),
]
