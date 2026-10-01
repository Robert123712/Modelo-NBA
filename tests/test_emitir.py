from modelo_nba.emitir import factores, escribir_si_cambia
from modelo_nba.proyeccion import Esperado

JUEGO = {"home_abbr": "BOS", "away_abbr": "NY"}


def _e(**d):
    base = dict(localia=1.8, ofensiva_casa=0.0, defensa_casa=0.0,
                ofensiva_visita=0.0, defensa_visita=0.0, descanso=0.0)
    base.update(d)
    return Esperado(115, 112, 112, 3, 99, base)


def test_bajas_y_descanso_aparecen_y_apoyan_al_rival():
    f = factores(JUEGO, _e(descanso=-1.2), {"home": (3.4, ["Tatum"]), "away": (0.0, [])}, "away")
    por_label = {x["label"]: x for x in f}
    assert por_label["Bajas de BOS"]["favors"] == "away"
    assert "Tatum" in por_label["Bajas de BOS"]["detail"]
    assert por_label["Descanso"]["favors"] == "away"
    assert por_label["Localía"]["supports_pick"] is False
    # Los que apoyan el pick van primero.
    assert [x["supports_pick"] for x in f] == sorted((x["supports_pick"] for x in f), reverse=True)


def test_baja_menor_no_se_menciona():
    f = factores(JUEGO, _e(), {"home": (0.2, ["Banca"]), "away": (0.0, [])}, "home")
    assert not any(x["label"].startswith("Bajas") for x in f)


def test_escribir_si_cambia_ignora_el_sello(tmp_path):
    ruta = tmp_path / "x.json"
    assert escribir_si_cambia(ruta, {"generated_at": "a", "v": 1})
    assert not escribir_si_cambia(ruta, {"generated_at": "b", "v": 1})
    assert escribir_si_cambia(ruta, {"generated_at": "c", "v": 2})
