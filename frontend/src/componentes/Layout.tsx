// Estructura común de las pantallas con sesión: cabecera, menú lateral y contenido.
// En el móvil el menú se oculta y se abre con el botón ☰ (Burger).

import { AppShell, Burger, Button, Group, NavLink, Text, Title } from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import {
  IconAlertOctagon,
  IconCarCrash,
  IconHeartbeat,
  IconLayoutDashboard,
  IconLogout,
  IconTool,
  IconTruck,
  IconUsers,
} from '@tabler/icons-react'
import { NavLink as EnlaceRouter, Outlet } from 'react-router'
import { useSesion } from '../auth/contexto.ts'
import { nombresRol } from '../util/formato.ts'

const MENU = [
  { a: '/averias/nueva', texto: 'Comunicar avería', Icono: IconAlertOctagon },
  { a: '/panel', texto: 'Panel de flota', Icono: IconLayoutDashboard },
  { a: '/vehiculos', texto: 'Vehículos', Icono: IconTruck },
  { a: '/personal', texto: 'Personal', Icono: IconUsers },
  { a: '/taller', texto: 'Taller', Icono: IconTool },
  // exacto: que no se marque también al estar en /averias/nueva (otra opción del menú).
  { a: '/averias', texto: 'Averías', Icono: IconCarCrash, exacto: true },
  { a: '/sistema', texto: 'Estado del sistema', Icono: IconHeartbeat },
]

export default function Layout() {
  const { usuario, salir } = useSesion()
  const [menuAbierto, { toggle, close }] = useDisclosure()

  return (
    <AppShell
      header={{ height: 56 }}
      navbar={{ width: 220, breakpoint: 'sm', collapsed: { mobile: !menuAbierto } }}
      padding="md"
    >
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between" wrap="nowrap">
          <Group gap="sm" wrap="nowrap">
            <Burger opened={menuAbierto} onClick={toggle} hiddenFrom="sm" size="sm" aria-label="Abrir menú" />
            <Title order={1} size="h4">
              Suite Flotas
            </Title>
          </Group>
          <Group gap="sm" wrap="nowrap">
            {usuario && (
              <Text size="sm" visibleFrom="xs">
                {usuario.nombre} · <Text span c="dimmed">{nombresRol[usuario.rol]}</Text>
              </Text>
            )}
            <Button variant="subtle" size="xs" leftSection={<IconLogout size={16} />} onClick={salir}>
              Salir
            </Button>
          </Group>
        </Group>
      </AppShell.Header>

      <AppShell.Navbar p="xs">
        {MENU.map(({ a, texto, Icono, exacto }) => (
          // NavLink de Mantine con el enlace de React Router: se marca solo cuando la URL coincide.
          <NavLink
            key={a}
            component={EnlaceRouter}
            to={a}
            end={exacto}
            label={texto}
            leftSection={<Icono size={18} />}
            onClick={close}
          />
        ))}
      </AppShell.Navbar>

      <AppShell.Main>
        <Outlet /> {/* aquí se pinta la pantalla de la ruta actual */}
      </AppShell.Main>
    </AppShell>
  )
}
