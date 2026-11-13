# Cafetería Fiores

Aplicación Django para consultar productos, armar pedidos para retiro y hacer seguimiento de pedidos.

## Requisitos

- Python 3.12 o posterior
- pip

## Instalación y ejecución en Windows

Abre PowerShell en la carpeta del proyecto y ejecuta:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py cargar_datos_demo
python manage.py runserver
```

Abre <http://127.0.0.1:8000/>. La aplicación solicita iniciar sesión.

Para activar la base de datos de cambios pendientes, ejecuta `python manage.py migrate` después de actualizar el proyecto.

## Usuarios de prueba

El comando `cargar_datos_demo` crea estas cuentas con la contraseña `FioresDemo2026!` cuando todavía no existen:

| Usuario | Rol |
| --- | --- |
| `encargado` | Encargado |
| `cliente1` | Cliente |
| `cliente2` | Cliente |

Si una cuenta ya existía, el comando conserva su contraseña. Para asignarle una nueva:

```powershell
python manage.py changepassword encargado
```

El encargado puede acceder al panel de pedidos de la aplicación. Para administrar todos los modelos en Django Admin, crea una cuenta superusuario:

```powershell
python manage.py createsuperuser
```

Luego entra a <http://127.0.0.1:8000/admin/>.

## Pruebas

```powershell
python manage.py test cafeteria_app
```
