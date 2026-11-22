# ADR 0002: Despliegue de la demo pública

- **Estado:** aceptada, pendiente de aplicar
- **Fecha:** 2026-11-22

> **Situación actual:** de momento la aplicación no se publica; se usa en local. La imagen Docker de
> los puntos 1 y 2 ya existe (`Dockerfile`, `backend/app/servidor.py`, `docker/arranque.sh`) y se usa
> para la demo local (`docker-compose.demo.yml`), que la integración continua construye y arranca en
> cada cambio. Quedan para cuando se despliegue: crear los servicios en Render y Neon, la variable que
> desactiva las fotos (punto 3) y la tarea de reinicio diario (punto 4).

## Contexto

La fase F4 del plan de entrega termina con una *demo pública con datos ficticios*. No hay uso
comercial previsto por ahora, así que el requisito principal es que **no tenga coste**, aceptando
limitaciones de rendimiento razonables. La especificación pide además **HTTPS al desplegar**.

Lo que la aplicación necesita para funcionar:

| Necesidad | Por qué |
|---|---|
| PostgreSQL con la extensión `btree_gist` | Restricción "un conductor habitual a la vez" (PER-03, `EXCLUDE USING gist`) |
| Un proceso Python (FastAPI + uvicorn) | La API |
| Servir el frontend compilado (`frontend/dist`) | Archivos estáticos de React |
| Disco persistente | Fotos de las averías (`CARPETA_ADJUNTOS`) |
| Una tarea diaria | Regenerar la empresa de demostración: sus fechas son relativas al día en que se crea (vencimientos, preventivos, 6 meses de OT) y, al ser pública, cualquiera puede modificarla |

Precios y límites consultados el 2026-11-22 en la documentación de cada proveedor (pueden cambiar).

## Opciones consideradas

| Opción | Coste | A favor | En contra |
|---|---|---|---|
| **Render (plan gratuito) + Neon (plan gratuito)** | 0 € | Sin servidor que mantener; despliegue desde GitHub con Docker; HTTPS incluido; Neon incluye `btree_gist`, no caduca y despierta en ~0,5 s | La API se suspende tras 15 min sin visitas y tarda ~1 min en despertar; 512 MB de RAM y 0,1 CPU; disco efímero (lo escrito se pierde al reiniciar) |
| Render (plan gratuito) con su PostgreSQL gratuito | 0 € | Todo en un proveedor | La base de datos gratuita caduca a los 30 días |
| Servidor virtual (VPS) con Docker Compose | ~6 €/mes + IVA | Sin suspensión; disco persistente; control total; el mismo `docker compose` que en desarrollo | Coste mensual; mantener el servidor (actualizaciones, seguridad); conviene un dominio |
| Plataforma de pago (Render: web + PostgreSQL + disco) | ~15-20 $/mes | Sin suspensión y sin mantener servidor | Lo más caro para el mismo resultado |

## Decisión

**Render (plan gratuito) para la aplicación y Neon (plan gratuito) para PostgreSQL**, ambos en la
región de Fráncfort (UE, la más cercana).

1. **Un solo servicio para web y API.** Una imagen Docker en varias etapas: Node compila el
   frontend y la imagen final (Python) sirve la API bajo `/api` y el frontend compilado en el resto
   de rutas, con vuelta a `index.html` para las URL de React Router. Mismo origen: sin CORS y sin
   cambiar `cliente.ts`, que ya llama a `/api` (en desarrollo lo hace el proxy de Vite).
2. **Migraciones al arrancar:** el contenedor ejecuta `alembic upgrade head` antes de uvicorn (en el
   plan gratuito no hay orden previa al despliegue).
3. **Fotos de averías desactivadas en la demo pública**, con una variable de configuración: con un
   disco efímero se perderían en cada reinicio y, al ser una demo abierta, se evita que se suban
   imágenes indebidas. En desarrollo y en un despliegue con disco siguen activas.
4. **Reinicio diario de la demo con GitHub Actions** (tarea programada, gratuita), que ejecuta
   `python -m app.scripts.demo --reiniciar` contra la base de datos de Neon. Las tareas programadas
   de Render son de pago.
5. **Secretos solo en los paneles de Render y en los secretos de GitHub**, nunca en el repositorio:
   `DATABASE_URL` (con `sslmode=require`, que Neon exige) y un `JWT_SECRETO` distinto del de
   desarrollo.

## Consecuencias

- **Primera visita lenta:** si nadie ha entrado en 15 minutos, la primera carga tarda alrededor de
  un minuto. El resto de la navegación va a velocidad normal. Neon añade ~0,5 s al despertar.
- **La demo se regenera cada noche:** cualquier cambio que haga un visitante desaparece al día
  siguiente. Así las alertas, los vencimientos y los indicadores siempre tienen sentido respecto
  a la fecha actual.
- **Solo datos ficticios** (requisito de privacidad de la especificación): en producción solo existe
  la empresa de demostración; las credenciales de demo son públicas a propósito.
- **Comunicar avería funciona sin foto** en la demo pública.
- **Recursos justos:** 512 MB de RAM bastan para una demo de 25 vehículos; importar archivos grandes
  (límite de 1.000 filas) puede ir lento con 0,1 CPU.
- **Portabilidad:** la imagen Docker no depende de Render. Pasar a un VPS es añadir PostgreSQL y un
  proxy con HTTPS (p. ej. Caddy) en un `docker-compose`, montar un volumen para las fotos y volver a
  activarlas, y cambiar el reinicio diario a un `cron` del servidor. Nada del código cambia.
- **Revisar si cambian las condiciones:** si Render o Neon cambian su plan gratuito (como hizo
  Render en 2024 al pasar la caducidad de su PostgreSQL gratuito de 90 a 30 días), se reevalúa con
  un nuevo ADR.
