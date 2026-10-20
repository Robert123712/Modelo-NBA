from pathlib import Path

from modelo_nba import reporte_nba as rn

PDF = Path(__file__).parent / "fixtures" / "injury_report_2026-10-20_03PM.pdf"


def test_lee_el_reporte_oficial():
    df = rn.parse_pdf(PDF.read_bytes())
    hoy = df[df.fecha.astype(str) == "2026-10-20"]
    estado = dict(zip(hoy.jugador, hoy.estado))
    assert estado["Elijah Harkless"] == "out"  # two-way en la G League
    assert estado["Anfernee Simons"] == "questionable"
    assert estado["Jayden Quaintance"] == "out"  # renglon que cruza de pagina
    assert set(hoy.partido) == {"BOS@DET", "PHI@NYK", "OKC@SAS"}
    assert hoy.equipo.str.contains(" ").all()
    # Equipos que todavia no entregan (del dia siguiente) quedan aparte.
    assert any(e == "Atlanta Hawks" for _, e in df.attrs["sin_reporte"])


def test_reportes_del_indice_en_hora_del_este():
    html = ('<a href="https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-10-20_03_00PM.pdf">'
            '<a href="https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-10-20_12_45AM.pdf">')
    r = rn.reportes(html)
    assert [t.strftime("%H:%M") for t, _ in r] == ["00:45", "15:00"]
    assert str(r[0][0].tz) == "America/New_York"


def test_el_reporte_manda_sobre_espn():
    reporte = rn.parse_pdf(PDF.read_bytes())
    reporte = reporte[reporte.fecha.astype(str) == "2026-10-20"]
    reporte.attrs["sin_reporte"] = []
    roster = [
        {"athlete_id": 1, "nombre": "Elijah Harkless", "estado": "active", "prob_juega": 1.0, "estado_conocido": True},
        {"athlete_id": 2, "nombre": "Cade Cunningham", "estado": "day-to-day", "prob_juega": 0.6, "estado_conocido": True},
        {"athlete_id": 3, "nombre": "Jalen Duren", "estado": "out", "prob_juega": 0.0, "estado_conocido": True},
    ]
    r = {x["nombre"]: x for x in rn.aplicar(roster, reporte, "Detroit Pistons")}
    assert r["Elijah Harkless"]["prob_juega"] == 0  # el reporte lo saca
    assert r["Cade Cunningham"]["prob_juega"] == 1  # no listado: disponible
    assert r["Jalen Duren"]["prob_juega"] == 0  # ESPN Out y no listado: se queda fuera
    # Equipo que no ha entregado: se queda ESPN.
    reporte.attrs["sin_reporte"] = ["Detroit Pistons"]
    assert rn.aplicar(roster, reporte, "Detroit Pistons") == roster
    assert rn.aplicar(roster, None, "Detroit Pistons") == roster
