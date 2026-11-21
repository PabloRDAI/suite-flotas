import { Alert, Button, Center, Paper, PasswordInput, Stack, Text, TextInput, Title } from '@mantine/core'
import { IconAlertCircle, IconTruck } from '@tabler/icons-react'
import { useState, type FormEvent } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router'
import { useSesion } from '../auth/contexto.ts'

export default function Login() {
  const { usuario, entrar } = useSesion()
  const navegar = useNavigate()
  const ubicacion = useLocation()
  const destino = (ubicacion.state as { desde?: string } | null)?.desde ?? '/'

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [enviando, setEnviando] = useState(false)

  if (usuario) return <Navigate to={destino} replace />

  const enviar = async (evento: FormEvent) => {
    evento.preventDefault() // el formulario no recarga la página: lo gestiona React
    setError(null)
    setEnviando(true)
    try {
      await entrar(email, password)
      void navegar(destino, { replace: true })
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo iniciar sesión')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <Center mih="100vh" p="md">
      <Paper withBorder shadow="sm" p="xl" radius="md" w="100%" maw={400}>
        <form onSubmit={(e) => void enviar(e)}>
          <Stack>
            <Stack gap={4} align="center">
              <IconTruck size={40} stroke={1.5} aria-hidden />
              <Title order={1} size="h2">
                Suite Flotas
              </Title>
              <Text c="dimmed" size="sm">
                Flota, personal y mantenimiento
              </Text>
            </Stack>

            {error && (
              <Alert color="red" icon={<IconAlertCircle />} role="alert">
                {error}
              </Alert>
            )}

            <TextInput
              label="Email"
              type="email"
              autoComplete="username"
              required
              value={email}
              onChange={(e) => setEmail(e.currentTarget.value)}
            />
            <PasswordInput
              label="Contraseña"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.currentTarget.value)}
            />
            <Button type="submit" loading={enviando} fullWidth>
              Entrar
            </Button>

            {/* Solo en desarrollo: recordatorio de los usuarios de la empresa demo. */}
            {import.meta.env.DEV && (
              <Text size="xs" c="dimmed" ta="center">
                Demo: admin | trafico | taller | conductor @demo.example.com — contraseña «demostracion»
              </Text>
            )}
          </Stack>
        </form>
      </Paper>
    </Center>
  )
}
