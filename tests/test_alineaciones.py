from modelo_nba import alineaciones


def _jug(nombre, pos, estado="Expected", t="2026-10-22T10:14:49"):
    return {"playerName": nombre, "position": pos, "lineupStatus": estado, "rosterStatus": "Active", "timestamp": t}


DATA = {"games": [{
    "gameId": "0022600006",
    "homeTeam": {"teamAbbreviation": "PHI", "players": [
        _jug("VJ Edgecombe", "SG"), _jug("Jaylen Brown", "SF"), _jug("Tyrese Maxey", "PG"),
        _jug("LeBron James", "PF"), _jug("Joel Embiid", "C")]},
    "awayTeam": {"teamAbbreviation": "CLE", "players": [
        _jug("Donovan Mitchell", "SG", "Confirmed"), _jug("Peyton Watson", "SF", "Confirmed"),
        _jug("James Harden", "PG", "Confirmed"), _jug("Evan Mobley", "PF", "Confirmed"),
        _jug("Jarrett Allen", "C", "Confirmed"), _jug("De'Andre Hunter", "", "Confirmed"),
        _jug("Ty Jerome", "", "Confirmed")]},
}]}


def test_parse_toma_solo_a_los_cinco_titulares():
    a = alineaciones.parse(DATA)
    assert a["PHI"]["estado"] == "Expected" and len(a["PHI"]["titulares"]) == 5
    # Confirmada: viene todo el roster, pero titulares son los que traen posicion.
    assert a["CLE"]["estado"] == "Confirmed"
    assert "deandrehunter" not in a["CLE"]["titulares"] and "jarrettallen" in a["CLE"]["titulares"]


def test_cruce_con_el_roster_de_espn_por_nombre():
    a = alineaciones.parse(DATA)
    nombres = ["Donovan Mitchell", "Peyton Watson", "James Harden", "Evan Mobley", "Jarrett Allen",
               "De'Andre Hunter", "Ty Jerome"]
    roster = [{"athlete_id": 100 + i, "nombre": n} for i, n in enumerate(nombres)]
    eq = alineaciones.del_equipo(a, roster)
    assert eq["estado"] == "Confirmed" and eq["titulares"] == {100, 101, 102, 103, 104}
    # Un nombre escrito distinto no tira la alineacion; dos si.
    roster[0]["nombre"] = "Don Mitchell"
    assert alineaciones.del_equipo(a, roster)["titulares"] == {101, 102, 103, 104}
    roster[1]["nombre"] = "P. Watson"
    assert alineaciones.del_equipo(a, roster) is None
