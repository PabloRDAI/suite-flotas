// Qué puede hacer cada rol en la interfaz. Refleja los permisos de la API
// (backend/app/deps.py): la API es quien manda; aquí solo se ocultan los botones
// que el usuario no podría usar, para que no se encuentre con un error 403.

import type { Usuario } from '../api/tipos.ts'

/** Alta, edición y baja de vehículos y personal, y asignaciones: gerente y tráfico. */
export const puedeGestionarFlota = (usuario: Usuario | null): boolean =>
  usuario?.rol === 'admin' || usuario?.rol === 'trafico'

/** Planes de mantenimiento, realizaciones, averías y órdenes de trabajo: gerente y taller. */
export const puedeGestionarTaller = (usuario: Usuario | null): boolean =>
  usuario?.rol === 'admin' || usuario?.rol === 'taller'
