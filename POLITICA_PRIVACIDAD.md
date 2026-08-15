# Política de privacidad — chistoricas-metricas

_Última actualización: 15 de agosto de 2026_

## Qué es esta aplicación

`chistoricas-metricas` es una herramienta personal de línea de comandos que usa **una sola
persona: la propietaria del canal de YouTube [@chistoricas3](https://www.youtube.com/@chistoricas3)**.
Sirve para consultar las estadísticas de ese mismo canal sin tener que descargarlas a mano desde
YouTube Studio.

No es un servicio, no tiene usuarios registrados, no tiene servidores y no está abierta al público.
Se ejecuta en el ordenador personal de su propietaria.

## Qué datos usa

Con la autorización de la propietaria del canal, accede **en modo solo lectura** a:

| Permiso | Para qué |
|---|---|
| `https://www.googleapis.com/auth/yt-analytics.readonly` | Leer las estadísticas del canal: visualizaciones, tiempo de reproducción, retención de audiencia |
| `https://www.googleapis.com/auth/youtube.readonly` | Leer el título y el identificador de los vídeos del canal, para saber a qué vídeo corresponde cada cifra |

Los datos consultados son **estadísticas agregadas del propio canal**. La aplicación no accede a
datos personales de los espectadores, ni a comentarios, ni a mensajes, ni a información de pago.

**No escribe ni modifica nada**: los permisos son de solo lectura. No publica vídeos, no cambia
títulos, no responde comentarios.

## Dónde se guardan

Todo se guarda **localmente**, en el ordenador de la propietaria del canal:

- El token de acceso, en un archivo con permisos restringidos (`600`, solo su usuario puede leerlo).
- Las estadísticas descargadas, en archivos CSV en el mismo equipo.

## Con quién se comparten

**Con nadie.** No hay servidores, ni bases de datos remotas, ni servicios de analítica, ni
publicidad, ni terceros de ningún tipo. Los datos no salen del equipo donde se ejecuta la
aplicación, salvo la propia comunicación con las APIs de Google necesaria para consultarlos.

No se venden, no se ceden y no se usan para entrenar ningún modelo.

## Cuánto tiempo se conservan

Mientras le resulten útiles a su propietaria. Puede borrarlos en cualquier momento eliminando los
archivos correspondientes de su equipo.

## Cómo revocar el acceso

En cualquier momento, desde [myaccount.google.com/permissions](https://myaccount.google.com/permissions),
retirando el acceso a `chistoricas-metricas`. A partir de ese momento la aplicación deja de poder
consultar nada.

## Cambios

Si la aplicación pasara a usar otros permisos o a compartir datos con alguien, esta política se
actualizaría antes de que ocurriera.

## Contacto

juan_barmo@hotmail.com
