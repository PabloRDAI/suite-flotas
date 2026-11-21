# ADR 0001: Librería de componentes y piezas base del frontend

- **Estado:** aceptada
- **Fecha:** 2026-11-21

## Contexto

La especificación deja abierta la pregunta: *"¿Qué librería de componentes usar en el frontend?
Se decidirá con un ADR al empezar el frontend"*. También identifica el riesgo de *atascarse con el
frontend* y propone como mitigación *usar una librería de componentes; primero listados y
formularios sencillos y después lo visual*.

Las pantallas del MVP son sobre todo **tablas filtrables, fichas con pestañas, formularios y
avisos** (panel de flota, ficha de vehículo, personal, taller, comunicar avería, configuración).
Deben verse bien en el móvil y mostrar los colores de alerta siempre acompañados de texto o icono.

## Opciones consideradas

| Opción | A favor | En contra |
|---|---|---|
| **Mantine** | Muy completa de serie (tablas, formularios, pestañas, notificaciones, fechas, layout de aplicación); se usa con props, sin aprender un sistema de CSS nuevo; documentación muy clara; modo oscuro incluido | Aspecto reconocible si no se personaliza |
| shadcn/ui + Tailwind | Máxima libertad de diseño; los componentes viven dentro del proyecto | Hay que aprender Tailwind y montar a mano más piezas (tablas avanzadas, fechas): más lento para empezar |
| MUI (Material UI) | La más veterana y extendida en empresas | Más pesada, API más extensa y aspecto Material muy marcado |

## Decisión

- **Librería de componentes: Mantine** (`@mantine/core`, `@mantine/hooks`, `@mantine/notifications`),
  con iconos de **Tabler Icons** (`@tabler/icons-react`), los que usa la documentación de Mantine.
- **Navegación entre pantallas: React Router** (`react-router`): cada pantalla tiene su URL
  (`/vehiculos`, `/vehiculos/12`), que se puede guardar o compartir.
- **Datos de la API: TanStack Query** (`@tanstack/react-query`): gestiona los estados de carga y
  error, guarda las respuestas en caché y las refresca tras un cambio, sin repetir código en cada
  pantalla.

## Consecuencias

- Las pantallas se construyen con componentes de Mantine; solo se escribe CSS propio para detalles.
- El semáforo (verde, ámbar, rojo) se implementa una sola vez como componente propio que siempre
  muestra icono y texto, no solo color.
- Si en el futuro se quisiera otro aspecto, Mantine permite personalizar el tema (colores,
  tipografía, radios) sin cambiar las pantallas.
- Se añaden cinco dependencias al frontend; todas son compatibles con React 19.
