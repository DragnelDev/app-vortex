# Vortex — Control de Inventario y Kardex Físico-Valorado

Sistema desacoplado: **API REST** (Django 5+ / DRF / PostgreSQL / JWT) + **SPA** (Vue 3 / Vite / Tailwind CSS 4 / PrimeVue 4).

- Valoración por **Precio Promedio Ponderado (PPP)** con cada entrada.
- Precisión contable: todo es `DecimalField(14, 4)`; no se usa `float` (ni en backend ni en las validaciones del frontend).
- Sin borrado físico de movimientos: las anulaciones generan un **contra-movimiento**.
- Operaciones atómicas (`transaction.atomic` + `select_for_update`) para entradas, salidas, traspasos y anulaciones.
- Multi-sucursal, multi-almacén y catálogo de unidades de medida.

## Estructura

```
backend-vortex/
  requirements.txt
  vortex/                  ← proyecto Django (manage.py)
    .env.example           ← copiar a .env
    vortex/settings.py     ← configuración leída desde .env
    inventario/            ← app: models, services, serializers, filters, views, tests
frontend-vortex/
  .env.example             ← copiar a .env
  src/                     ← api, layouts, stores, config, utils
```

## Puesta en marcha

### 1. Backend

```bash
cd backend-vortex
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

cp .env.example .env        # Windows: Copy-Item .env.example .env
# Edite SECRET_KEY, TEST_ADMIN_PASSWORD y las credenciales de PostgreSQL en .env.
python manage.py migrate
python manage.py seed_inventario        # unidades, tipos de movimiento, sucursal/almacén base
python manage.py crear_admin_pruebas    # usuario admin local (requiere TEST_ADMIN_PASSWORD)
python manage.py runserver              # http://localhost:8000
```

Antes de ejecutar `crear_admin_pruebas`, configure una contraseña propia en `TEST_ADMIN_PASSWORD` dentro de `backend-vortex/.env`. El usuario predeterminado es `admin`. El comando solo funciona con `DEBUG=True`, no modifica cuentas existentes y no debe usarse en producción. Para crear una cuenta manualmente, use `python manage.py createsuperuser`.

Genere una `SECRET_KEY` con:
`python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"`

### 2. Frontend

```bash
cd frontend-vortex
cp .env.example .env        # VITE_API_URL=http://localhost:8000/api
npm install
npm run dev                 # http://localhost:5173
```

Ingrese con el superusuario creado. Flujo sugerido: _Catálogos → Productos_ (cree un proveedor y un cliente en _Proveedores y clientes_) → _Nuevo movimiento_ → _Kardex_.

## Variables de entorno

| Backend (`vortex/.env`)                                   | Descripción                               | Por defecto                                   |
| --------------------------------------------------------- | ----------------------------------------- | --------------------------------------------- |
| `SECRET_KEY`                                              | Clave secreta de Django (**obligatoria**) | —                                             |
| `DEBUG`                                                   | Modo depuración                           | `False`                                       |
| `ALLOWED_HOSTS`                                           | Hosts permitidos (separados por coma)     | `localhost,127.0.0.1`                         |
| `TIME_ZONE`                                               | Zona horaria                              | `America/La_Paz`                              |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | PostgreSQL                                | `vortex`, `postgres`, ``, `localhost`, `5432` |
| `TEST_ADMIN_USERNAME`, `TEST_ADMIN_EMAIL`, `TEST_ADMIN_PASSWORD` | Credenciales del admin local | `admin`, `admin@example.com`, vacío |
| `CORS_ALLOWED_ORIGINS`                                    | Orígenes del frontend                     | `http://localhost:5173`                       |
| `CSRF_TRUSTED_ORIGINS`                                    | Orígenes de confianza CSRF                | vacío                                         |
| `JWT_ACCESS_MINUTES` / `JWT_REFRESH_DAYS`                 | Vida de los tokens                        | `30` / `7`                                    |
| `PAGE_SIZE`                                               | Tamaño de página por defecto              | `25`                                          |

| Frontend (`.env`) | Descripción                         |
| ----------------- | ----------------------------------- |
| `VITE_API_URL`    | URL base de la API (incluye `/api`) |

Los archivos `.env` están en `.gitignore`; versione solo los `.env.example`.

## API (prefijo `/api/`)

| Recurso                                  | Endpoint                                                                                                                                         |
| ---------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| Autenticación JWT                        | `POST auth/token/`, `POST auth/token/refresh/`, `GET auth/me/`                                                                                   |
| Catálogos (CRUD; `DELETE` = baja lógica) | `sucursales`, `almacenes`, `categorias`, `unidades`, `productos`, `terceros`, `tipos-movimiento`                                                 |
| Comprobantes                             | `GET movimientos/`, `GET movimientos/{id}/`, `POST movimientos/` (entrada/salida), `POST movimientos/traspaso/`, `POST movimientos/{id}/anular/` |
| Stock                                    | `GET stock/` (`?almacen=&producto=&bajo_minimo=true`)                                                                                            |
| Kardex                                   | `GET kardex/?producto=&almacen=[&desde=&hasta=]` (paginado + resumen), `GET kardex/exportar/` (CSV)                                              |
| Dashboard                                | `GET dashboard/resumen/`                                                                                                                        |

Todos los listados admiten `?search=`, `?ordering=`, `?page=` y `?page_size=`.

Errores de dominio: `409` con `code: "stock_insuficiente"` si una salida supera el stock; `400` para validaciones.

## Reglas de negocio clave

- **PPP**: entrada → `nuevo PPP = (valor + cant × costo) / (stock + cant)`. La salida se valora al PPP vigente. Cada línea guarda el saldo resultante, así el Kardex valorado no se recalcula.
- **Anulación**: crea un contra-movimiento y marca el original como `ANULADO`. Una compra ya consumida no puede anularse (stock insuficiente). Anular un traspaso anula ambos comprobantes.
- **Traspaso**: dos comprobantes enlazados (salida al PPP de origen, entrada al mismo costo en destino).
- **Orden del Kardex**: orden de registro. La fecha del comprobante es informativa.
- Los comprobantes, sus líneas y el stock **no se pueden eliminar ni editar** (ni por ORM ni por admin).

## Pruebas

```bash
cd backend-vortex/vortex && python manage.py test inventario   # 12 pruebas (servicios y API)
cd frontend-vortex && npm run test:unit -- --run && npm run build
```

Para ejecutar las pruebas del backend sin PostgreSQL: `DB_ENGINE=django.db.backends.sqlite3 DB_NAME=/tmp/t.sqlite3 SECRET_KEY=x python manage.py test inventario`.

## Producción

`DEBUG=False`, `SECRET_KEY` propia, `ALLOWED_HOSTS` y `CORS_ALLOWED_ORIGINS` con los dominios reales; sirva Django con gunicorn/uvicorn detrás de HTTPS y publique `frontend-vortex/dist` (`npm run build`).
