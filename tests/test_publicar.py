import json
import subprocess

from modelo_nba import vigilante


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _clon(origen, destino):
    subprocess.run(["git", "clone", "-q", str(origen), str(destino)], check=True, capture_output=True)
    _git(destino, "config", "user.name", "prueba")
    _git(destino, "config", "user.email", "prueba@example.com")
    return destino


def test_publicar_no_se_traba_si_otra_corrida_publico_antes(tmp_path, monkeypatch):
    origen = tmp_path / "origen.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origen)], check=True)
    semilla = _clon(origen, tmp_path / "semilla")
    (semilla / "data").mkdir()
    (semilla / "data" / "latest.json").write_text(json.dumps({"v": 0}))
    (semilla / "codigo.py").write_text("x = 1\n")
    _git(semilla, "add", ".")
    _git(semilla, "commit", "-q", "-m", "inicio")
    _git(semilla, "push", "-q", "origin", "HEAD:main")

    a = _clon(origen, tmp_path / "a")
    b = _clon(origen, tmp_path / "b")
    # La corrida A publica primero, y alguien sube codigo.
    (a / "data" / "latest.json").write_text(json.dumps({"v": "a"}))
    (a / "codigo.py").write_text("x = 2\n")
    _git(a, "commit", "-qam", "a")
    _git(a, "push", "-q", "origin", "HEAD:main")
    # La corrida B, con el repo viejo, calculo otra cosa en la misma linea.
    (b / "data" / "latest.json").write_text(json.dumps({"v": "b"}))
    (b / "data" / "nuevo.json").write_text("{}")
    monkeypatch.chdir(b)
    monkeypatch.setattr(vigilante.time, "sleep", lambda s: None)
    vigilante.publicar()

    final = _clon(origen, tmp_path / "final")
    assert json.loads((final / "data" / "latest.json").read_text()) == {"v": "b"}  # ganan los datos de B
    assert (final / "data" / "nuevo.json").exists()
    assert (final / "codigo.py").read_text() == "x = 2\n"  # y no se pierde lo ajeno
