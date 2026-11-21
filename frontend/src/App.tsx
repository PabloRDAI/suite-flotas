import { useEffect, useState } from 'react'
import { comprobarSalud, type ResultadoSalud } from './api.ts'
import './App.css'

type Semaforo = 'verde' | 'rojo' | 'gris'

/** Una fila de estado: siempre icono + texto, no solo color (requisito de usabilidad de la spec). */
function FilaEstado({ nombre, semaforo, texto }: { nombre: string; semaforo: Semaforo; texto: string }) {
  const icono = { verde: '✅', rojo: '❌', gris: '⏳' }[semaforo]
  return (
    <li className={`fila fila--${semaforo}`}>
      <span className="fila__nombre">{nombre}</span>
      <span className="fila__valor">
        <span aria-hidden="true">{icono}</span> {texto}
      </span>
    </li>
  )
}

function App() {
  // Estado del componente: React vuelve a pintar la pantalla cuando cambia.
  const [resultado, setResultado] = useState<ResultadoSalud | null>(null)
  const [cargando, setCargando] = useState(true)
  const [ultimaComprobacion, setUltimaComprobacion] = useState<Date | null>(null)

  const guardarResultado = (r: ResultadoSalud) => {
    setResultado(r)
    setUltimaComprobacion(new Date())
    setCargando(false)
  }

  // useEffect con []: se ejecuta una vez, al mostrar la pantalla por primera vez.
  // El estado solo se cambia cuando llega la respuesta (no de inmediato), y si la
  // pantalla se cierra antes, se ignora la respuesta ("cancelado").
  useEffect(() => {
    let cancelado = false
    void comprobarSalud().then((r) => {
      if (!cancelado) guardarResultado(r)
    })
    return () => {
      cancelado = true
    }
  }, [])

  // Al pulsar el botón: aquí sí marcamos "cargando" porque responde a una acción del usuario.
  const volverAComprobar = async () => {
    setCargando(true)
    guardarResultado(await comprobarSalud())
  }

  // Traducimos el resultado a lo que se ve en cada fila.
  let api: [Semaforo, string] = ['gris', 'Comprobando…']
  let bd: [Semaforo, string] = ['gris', 'Comprobando…']
  if (!cargando && resultado) {
    if (resultado.tipo === 'ok') {
      api = ['verde', 'Conectada']
      bd = ['verde', 'Conectada']
    } else if (resultado.tipo === 'bd_caida') {
      api = ['verde', 'Conectada']
      bd = ['rojo', 'Sin conexión']
    } else {
      api = ['rojo', 'Sin respuesta']
      bd = ['gris', 'Desconocido']
    }
  }

  return (
    <main className="pagina">
      <header>
        <h1>Suite Flotas</h1>
        <p className="subtitulo">Flota, personal y mantenimiento</p>
      </header>

      <section className="tarjeta" aria-labelledby="titulo-estado" aria-busy={cargando}>
        <h2 id="titulo-estado">Estado del sistema</h2>
        <ul className="filas">
          <FilaEstado nombre="API" semaforo={api[0]} texto={api[1]} />
          <FilaEstado nombre="Base de datos" semaforo={bd[0]} texto={bd[1]} />
        </ul>

        {!cargando && resultado?.tipo === 'api_caida' && (
          <p className="aviso" role="alert">
            {resultado.mensaje}
          </p>
        )}

        <div className="pie">
          <button type="button" onClick={() => void volverAComprobar()} disabled={cargando}>
            {cargando ? 'Comprobando…' : 'Volver a comprobar'}
          </button>
          {ultimaComprobacion && (
            <span className="hora">Última comprobación: {ultimaComprobacion.toLocaleTimeString('es-ES')}</span>
          )}
        </div>
      </section>
    </main>
  )
}

export default App
