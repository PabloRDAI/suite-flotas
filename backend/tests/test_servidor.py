"""Servidor de la imagen Docker: la API bajo /api y la web (con las rutas de React) en el resto."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.servidor import crear_servidor


@pytest.fixture
def cliente(tmp_path: Path) -> TestClient:
    (tmp_path / "index.html").write_text("<!doctype html><title>Suite Flotas</title>", encoding="utf-8")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    return TestClient(crear_servidor(tmp_path))


def test_la_api_esta_bajo_api(cliente: TestClient) -> None:
    r = cliente.get("/api/salud")

    assert r.status_code == 200
    assert r.json()["estado"] == "ok"


def test_la_portada_es_la_web(cliente: TestClient) -> None:
    assert "Suite Flotas" in cliente.get("/").text


@pytest.mark.parametrize("ruta", ["/panel", "/vehiculos/3", "/ordenes-trabajo/12"])
def test_las_rutas_de_react_devuelven_la_web(cliente: TestClient, ruta: str) -> None:
    """Entrar directamente o recargar en /vehiculos/3 no da 404: lo resuelve React."""
    r = cliente.get(ruta)

    assert r.status_code == 200
    assert "Suite Flotas" in r.text


def test_los_archivos_se_sirven_tal_cual(cliente: TestClient) -> None:
    assert cliente.get("/assets/app.js").text == "console.log(1)"


def test_un_archivo_que_no_existe_es_404(cliente: TestClient) -> None:
    assert cliente.get("/assets/no-existe.js").status_code == 404


def test_una_ruta_de_la_api_que_no_existe_es_404_de_la_api(cliente: TestClient) -> None:
    """No se confunde con la web: la API responde su propio 404 en JSON."""
    r = cliente.get("/api/no-existe")

    assert r.status_code == 404
    assert r.json() == {"detail": "Not Found"}
