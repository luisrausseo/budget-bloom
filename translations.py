"""Shared English/Spanish UI catalog. Never translate user-authored content."""
from jinja2 import pass_context

SPANISH = {
    "Account": "Cuenta", "Language": "Idioma", "Apply": "Aplicar",
    "Add person": "Agregar persona", "Security & access": "Seguridad y acceso",
    "Invite user": "Invitar usuario", "Sign out": "Cerrar sesión",
    "HOUSEHOLD FINANCE": "FINANZAS DEL HOGAR", "Monthly budget": "Presupuesto mensual",
    "Grocery list": "Lista de compras", "Grocery List · Budget Bloom": "Lista de compras · Budget Bloom",
    "Show whole household for the current month": "Mostrar todo el hogar en el mes actual",
    "Application sections": "Secciones de la aplicación", "Create your household": "Crea tu hogar",
    "Start by giving your shared budget a home.": "Empieza creando un hogar para tu presupuesto compartido.",
    "Create household": "Crear hogar", "Navigate months": "Navegar entre meses",
    "Previous month": "Mes anterior", "Next month": "Mes siguiente", "Selected month": "Mes seleccionado",
    "Filter by person": "Filtrar por persona", "Whole household": "Todo el hogar", "This month": "Este mes",
    "PROJECTED MONEY LEFT": "SALDO DISPONIBLE ESTIMADO", "Income": "Ingresos", "Expenses": "Gastos",
    "MONTHLY ACTIVITY": "ACTIVIDAD MENSUAL", "Entries": "Movimientos", "Add entry": "Agregar movimiento",
    "Add a person first": "Agrega una persona primero",
    "To start budgeting, open Account and choose Add person.": "Para empezar, abre Cuenta y elige Agregar persona.",
    "Done": "Listo", "Description": "Descripción", "Category": "Categoría", "Person": "Persona",
    "Date": "Fecha", "Type": "Tipo", "Amount": "Importe", "Repeats monthly": "Se repite cada mes",
    "Monthly": "Mensual", "Edit this month only": "Editar solo este mes", "Edit": "Editar",
    "Stop recurring entry": "Detener movimiento recurrente", "Delete entry": "Eliminar movimiento",
    "Delete this and following months": "Eliminar este mes y los siguientes", "Delete": "Eliminar",
    "Delete this entry?": "¿Eliminar este movimiento?",
    "Delete this recurring entry from {month} onward? Previous months will be kept.": "¿Eliminar este movimiento recurrente desde {month}? Los meses anteriores se conservarán.",
    "Mark {name} completed for {month}": "Marcar {name} como completado en {month}",
    "Edit {name}": "Editar {name}", "No entries this month": "No hay movimientos este mes",
    "Add income or an expense to see your projection.": "Agrega un ingreso o un gasto para ver tu proyección.",
    "Close dialog": "Cerrar ventana", "NEW SPACE": "NUEVO HOGAR", "Name": "Nombre",
    "The Johnsons": "Mi hogar", "NEW MEMBER": "NUEVA PERSONA", "Add a person": "Agregar una persona",
    "Person's name": "Nombre de la persona", "Entry type": "Tipo de movimiento", "Expense": "Gasto",
    "Account or payment name…": "Nombre de la cuenta o del pago…", "Repeat monthly": "Repetir cada mes",
    "Include this entry in every following month": "Incluir este movimiento en todos los meses siguientes",
    "Save changes": "Guardar cambios", "Edit this month": "Editar este mes", "Edit entry": "Editar movimiento",
    "Changes apply only to {month}. Earlier and later months keep their existing values. Delete stops this entry from this month onward and keeps all earlier months.": "Los cambios se aplican solo a {month}. Los demás meses mantienen sus valores. Eliminar detiene este movimiento desde este mes y conserva todos los anteriores.",
    "income": "ingreso", "expense": "gasto", "SHARED HOUSEHOLD LIST": "LISTA COMPARTIDA DEL HOGAR",
    "Groceries": "Compras", "Everyone in {household} can add and complete items.": "Todos en {household} pueden agregar y completar artículos.",
    "Grocery item": "Artículo de compra", "What do you need?": "¿Qué necesitas?", "Add item": "Agregar artículo",
    "ITEM": "ARTÍCULO", "ITEMS": "ARTÍCULOS", "Household list": "Lista del hogar", "Item": "Artículo",
    "Added by": "Agregado por", "Date added": "Fecha de creación", "Mark {name} completed": "Marcar {name} como completado",
    "Modify {name}": "Modificar {name}", "Remove {name}": "Eliminar {name}", "Remove this grocery item?": "¿Eliminar este artículo de la lista?",
    "Your grocery list is empty": "Tu lista de compras está vacía", "Add the first item for your household.": "Agrega el primer artículo para tu hogar.",
    "GROCERY LIST": "LISTA DE COMPRAS", "Modify item": "Modificar artículo", "Item name": "Nombre del artículo",
    "Delete item": "Eliminar artículo", "Account security · Budget Bloom": "Seguridad de la cuenta · Budget Bloom",
    "ACCOUNT SETTINGS": "CONFIGURACIÓN DE CUENTA", "Security &": "Seguridad y", "access": "acceso",
    "Back to budget": "Volver al presupuesto", "Change password": "Cambiar contraseña",
    "Changing your password signs you out everywhere.": "Al cambiar tu contraseña se cerrarán todas tus sesiones.",
    "Current password": "Contraseña actual", "New password": "Nueva contraseña", "Active sessions": "Sesiones activas",
    "Sign out this account on every browser and device.": "Cierra esta cuenta en todos los navegadores y dispositivos.",
    "Sign out everywhere": "Cerrar todas las sesiones", "Household members": "Miembros del hogar",
    "Accounts with access to this household.": "Cuentas con acceso a este hogar.", "Owner": "Propietario",
    "Member": "Miembro", "Disabled": "Deshabilitado", "Enable": "Habilitar", "Disable": "Deshabilitar",
    "Disable this account?": "¿Deshabilitar esta cuenta?", "Unused invitations": "Invitaciones sin usar",
    "Revoke links that should no longer grant access.": "Revoca los enlaces que ya no deban permitir el acceso.",
    "Invitation #": "Invitación n.º ", "Expires": "Vence", "Revoke": "Revocar", "No active invitations": "No hay invitaciones activas",
    "Sign in · Budget Bloom": "Iniciar sesión · Budget Bloom", "WELCOME BACK": "BIENVENIDO",
    "Shared finances,": "Finanzas compartidas,", "beautifully simple.": "fáciles y claras.",
    "Plan each month together and keep every household expense in view.": "Planifica cada mes en equipo y mantén los gastos del hogar a la vista.",
    "Sign in to your household": "Inicia sesión en tu hogar", "Enter your account details to continue.": "Ingresa tus datos para continuar.",
    "Username": "Usuario", "Your username": "Tu usuario", "Password": "Contraseña", "Your password": "Tu contraseña",
    "Sign in": "Iniciar sesión", "Joining a household?": "¿Te unes a un hogar?", "Use an invitation code": "Usar un código de invitación",
    "Use invitation · Budget Bloom": "Usar invitación · Budget Bloom", "INVITATION ONLY": "SOLO CON INVITACIÓN",
    "Join {household}": "Únete a {household}", "Create account": "Crear cuenta", "Enter your invitation code": "Ingresa tu código de invitación",
    "Invitation code": "Código de invitación", "Continue": "Continuar", "Back to sign in": "Volver al inicio de sesión",
    "Invitation created · Budget Bloom": "Invitación creada · Budget Bloom", "INVITATION CREATED": "INVITACIÓN CREADA",
    "Share this link once": "Comparte esta invitación una vez", "This invitation expires {expires} and can create one account.": "Esta invitación vence el {expires} y permite crear una cuenta.",
    "Registration page": "Página de registro", "Code": "Código", "Copy invitation": "Copiar invitación",
    "Copies the registration link and the one-use code together.": "Copia el enlace de registro junto con el código de un solo uso.",
    "Switch color theme": "Cambiar tema", "Switch to light mode": "Cambiar al modo claro", "Switch to dark mode": "Cambiar al modo oscuro",
    "Light mode": "Modo claro", "Dark mode": "Modo oscuro", "Dismiss message": "Cerrar mensaje",
    "Sign in in a new tab": "Iniciar sesión en otra pestaña", "Refresh session": "Actualizar sesión",
    "Could not refresh the session. Sign in first, then try again.": "No se pudo actualizar la sesión. Inicia sesión e inténtalo de nuevo.",
    "Sign in to this household first, then refresh the session again.": "Inicia sesión en este hogar y vuelve a actualizar la sesión.",
    "Session refreshed. Your input is unchanged; you can save again.": "Sesión actualizada. Tus datos siguen aquí; puedes volver a guardar.",
    "Signing in…": "Iniciando sesión…", "Saving…": "Guardando…",
    "The server could not finish the request. Your input is still here.": "El servidor no pudo completar la solicitud. Tus datos siguen aquí.",
    "Your session has expired. Sign in in a new tab, then return here.": "Tu sesión venció. Inicia sesión en otra pestaña y vuelve aquí.",
    "Your session or permissions may have changed. Sign in again before retrying.": "Tu sesión o permisos pueden haber cambiado. Inicia sesión antes de reintentar.",
    "Too many attempts. Please wait a few minutes before trying again.": "Demasiados intentos. Espera unos minutos antes de reintentar.",
    "Check your input and try again. Your changes have not been cleared.": "Revisa tus datos e inténtalo de nuevo. Tus cambios no se han borrado.",
    "Connection interrupted. Your input is still here. The change may have saved—check the list in another tab before submitting again.": "Conexión interrumpida. Tus datos siguen aquí. El cambio podría haberse guardado; revisa la lista en otra pestaña antes de enviarlo de nuevo.",
    "Confirm action": "Confirmar acción", "Cancel": "Cancelar", "Confirm": "Confirmar", "Stop from this month": "Detener desde este mes",
    "Loading month…": "Cargando mes…", "Completed": "Completados",
    "All caught up. Your completed items are below.": "Todo al día. Tus elementos completados están abajo.",
    "Nothing left in this list. Add an item to get started.": "No queda nada en esta lista. Agrega un elemento para empezar.",
    "Completion was not confirmed. Check the list before trying again.": "No se confirmó el cambio. Revisa la lista antes de reintentar.",
    "Marked completed. Find it in the Completed section.": "Marcado como completado. Está en la sección Completados.",
    "Moved back to pending.": "Movido a pendientes.",
    "Entry removed. Earlier months of recurring entries are unchanged.": "Movimiento eliminado. Los meses anteriores de los movimientos recurrentes no cambian.",
    "Unexpected destination. Please reload.": "Destino inesperado. Recarga la página.", "Signed in successfully.": "Sesión iniciada.",
    "Signed out.": "Sesión cerrada.", "Done. Please sign in to continue.": "Listo. Inicia sesión para continuar.", "Changes saved.": "Cambios guardados.",
    "Unexpected response. Your input has been kept.": "Respuesta inesperada. Tus datos se han conservado.",
    "The save was not confirmed. Check the list before trying again.": "No se confirmó que se guardara. Revisa la lista antes de reintentar.",
    "Join my Budget Bloom household: ": "Únete a mi hogar en Budget Bloom: ", "Invitation code: ": "Código de invitación: ",
    "Invitation copied. Share it privately with the person joining your household.": "Invitación copiada. Compártela en privado con quien se unirá a tu hogar.",
    "Copying is unavailable. Select and copy the registration link and code above.": "No se puede copiar automáticamente. Selecciona y copia el enlace y el código de arriba.",
    "Invalid username or password": "Usuario o contraseña incorrectos", "Current password is incorrect": "La contraseña actual es incorrecta",
    "New password must be 12–128 characters": "La nueva contraseña debe tener entre 12 y 128 caracteres",
    "New password must be 12-128 characters": "La nueva contraseña debe tener entre 12 y 128 caracteres",
    "That invitation code is invalid, expired, or already used": "El código no es válido, venció o ya se usó",
    "Use a 3–50 character username (letters, numbers, . _ -) and a 12–128 character password": "Usa un usuario de 3 a 50 caracteres (letras, números, . _ -) y una contraseña de 12 a 128 caracteres",
    "That code is invalid or used, or the username is unavailable": "El código no es válido o ya se usó, o el usuario no está disponible",
    "Member disabled": "Miembro deshabilitado", "Member enabled": "Miembro habilitado", "Invitation revoked": "Invitación revocada",
    "Enter a valid amount": "Ingresa un importe válido", "Amount must be greater than zero": "El importe debe ser mayor que cero",
    "Description is required": "La descripción es obligatoria", "Person name is required": "El nombre de la persona es obligatorio",
    "Invalid entry details": "Datos del movimiento no válidos", "Grocery item must be 1-120 characters": "El artículo debe tener entre 1 y 120 caracteres",
    "Entry not found in the selected month": "No se encontró el movimiento en el mes seleccionado", "Grocery item not found": "Artículo no encontrado",
    "The request could not be completed": "No se pudo completar la solicitud", "Entry not found": "Movimiento no encontrado",
}


@pass_context
def language(context):
    account = context.get('account')
    if account:
        return 'es' if account.get('language') == 'es' else 'en'
    request = context.get('request')
    return 'es' if request and request.cookies.get('budget_bloom_language') == 'es' else 'en'


@pass_context
def translate(context, text, **values):
    translated = SPANISH.get(text, text) if language(context) == 'es' else text
    return translated.format(**values) if values else translated


@pass_context
def catalog(context):
    return SPANISH if language(context) == 'es' else {}


@pass_context
def month_label(context, value):
    year, month = value.split('-')
    names = ('enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre'.split()
             if language(context) == 'es' else
             'January February March April May June July August September October November December'.split())
    return f'{names[int(month) - 1]} {year}'


def configure(environment):
    environment.globals.update(t=translate, ui_language=language, ui_catalog=catalog, month_label=month_label)


def display_date(value, locale='en'):
    if locale == 'es':
        months = 'ene feb mar abr may jun jul ago sep oct nov dic'.split()
        return f'{value.day} {months[value.month - 1]} {value.year}'
    return value.strftime('%b %d, %Y').replace(' 0', ' ')
