"""Numeros en palabras, para que la voz no lea "11,629" como "once coma..."."""

_U = ("cero uno dos tres cuatro cinco seis siete ocho nueve diez once doce trece catorce quince "
      "dieciséis diecisiete dieciocho diecinueve veinte veintiuno veintidós veintitrés veinticuatro "
      "veinticinco veintiséis veintisiete veintiocho veintinueve").split()
_D = {30: "treinta", 40: "cuarenta", 50: "cincuenta", 60: "sesenta", 70: "setenta", 80: "ochenta", 90: "noventa"}
_C = {1: "ciento", 2: "doscientos", 3: "trescientos", 4: "cuatrocientos", 5: "quinientos",
      6: "seiscientos", 7: "setecientos", 8: "ochocientos", 9: "novecientos"}


def decir(n: int) -> str:
    n = int(n)
    if n < 30:
        return _U[n]
    if n < 100:
        d, u = n // 10 * 10, n % 10
        return _D[d] + (f" y {_U[u]}" if u else "")
    if n == 100:
        return "cien"
    if n < 1000:
        c, r = n // 100, n % 100
        return _C[c] + (f" {decir(r)}" if r else "")
    if n < 1_000_000:
        m, r = n // 1000, n % 1000
        miles = "mil" if m == 1 else f"{decir(m)} mil".replace("uno mil", "un mil").replace("veintiun mil", "veintiún mil")
        return miles + (f" {decir(r)}" if r else "")
    raise ValueError(n)


def miles(n: int) -> str:
    return f"{int(n):,}"
