# Política de privacidad

_Última actualización: 16 de agosto de 2026_

## Qué es esta aplicación

Es un conjunto de herramientas personales de línea de comandos que usa **una sola persona: el
propietario de las cuentas** [@chistoricas3](https://www.instagram.com/chistoricas3) (Instagram y
Threads), [@chistoricas3](https://www.youtube.com/@chistoricas3) (YouTube),
[@curiosidad3s_historicas](https://www.tiktok.com/@curiosidad3s_historicas) (TikTok) y la página de
Facebook *Curiosidades Históricas*.

Sirve para dos cosas sobre **esas mismas cuentas, que son suyas**:

1. **Consultar sus estadísticas** sin descargarlas a mano de cada panel.
2. **Publicar en ellas** el contenido que él mismo genera.

No es un servicio, no tiene usuarios registrados, no tiene servidores y no está abierta al público.
Se ejecuta en su ordenador personal.

## Qué datos usa, y para qué

Con su propia autorización, y **solo sobre sus propias cuentas**:

| Plataforma | Qué hace | Permisos |
|---|---|---|
| **YouTube** | Solo lectura de estadísticas | `yt-analytics.readonly`, `youtube.readonly` |
| **Instagram / Facebook** | Lee estadísticas **y publica** sus propios vídeos e imágenes | `instagram_basic`, `instagram_manage_insights`, `instagram_content_publish`, `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`, `read_insights` |
| **Threads** | Lee estadísticas **y publica** sus propios mensajes | `threads_basic`, `threads_content_publish`, `threads_manage_insights` |
| **TikTok** | Solo lectura de estadísticas | `user.info.basic`, `video.list` |

Los datos consultados son **estadísticas agregadas de las propias publicaciones**: visualizaciones,
alcance, me gusta, comentarios, veces compartido, retención. La aplicación **no accede a datos
personales de los espectadores**, ni a sus perfiles, ni a mensajes privados, ni a información de
pago, ni a datos de ninguna persona que no sea el propietario de las cuentas.

Lo que publica es contenido **creado por el propio titular**: vídeos, imágenes y textos sobre
divulgación histórica. Nunca publica en cuentas de terceros.

## Dónde se guardan

Todo **localmente**, en el ordenador de su propietario:

- Los tokens de acceso, en archivos con permisos restringidos (`600`, solo su usuario puede leerlos).
- Las estadísticas descargadas, en archivos CSV en el mismo equipo.

## Con quién se comparten

**Con nadie.** No hay servidores propios, ni bases de datos remotas, ni servicios de analítica, ni
publicidad, ni cesión a terceros. Los datos no salen del equipo salvo la comunicación con las APIs
de las propias plataformas, necesaria para consultarlos o publicar.

No se venden, no se ceden y no se usan para entrenar ningún modelo.

Para **generar** el contenido (no para analizarlo) la aplicación envía los textos que ella misma
redacta a servicios de terceros: OpenAI y Anthropic (guiones y descripciones), ElevenLabs
(locución) y fal.ai (ilustraciones). Nada de lo que se envía contiene datos de estadísticas ni
información de ninguna persona.

## Cuánto tiempo se conservan

Mientras le resulten útiles a su propietario. Puede borrarlos en cualquier momento eliminando los
archivos correspondientes de su equipo.

## Cómo revocar el acceso

En cualquier momento, y de forma independiente por plataforma:

| Plataforma | Dónde |
|---|---|
| Google / YouTube | [myaccount.google.com/permissions](https://myaccount.google.com/permissions) |
| Instagram / Facebook / Threads | Configuración de la cuenta → *Aplicaciones y sitios web* |
| TikTok | Configuración → *Seguridad* → *Administrar permisos de aplicaciones* |

A partir de ese momento la aplicación deja de poder consultar ni publicar nada.

## Menores

La aplicación no está dirigida a menores y no recoge datos de ninguna persona distinta de su
propietario.

## Cambios

Si la aplicación pasara a usar otros permisos o a compartir datos con alguien, esta política se
actualizaría antes de que ocurriera.

## Contacto

juan_barmo@hotmail.com
