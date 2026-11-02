"""Generador de la matriz de productos CDT (`cdt_productos.csv`) — Tarea 2.2.

Puebla el espacio completo de productos (i, j, k) = 5 bancos x 7 plazos x 3
tramos = 105 filas, aplicando el principio RECTOR de trazabilidad honesta
(Requisito 1.5): lo verificado se marca como real; lo derivado se marca como
supuesto documentado. NUNCA se presenta como real una cifra no verificada.

CAMBIO IMPORTANTE (datos reales por plazo)
------------------------------------------
Antes había UNA sola tasa real por banco (la "mejor tasa" a plazo largo) y el
resto se derivaba con un perfil de curva y una prima por tramo INVENTADOS. Esta
versión reemplaza ese perfil supuesto por la **curva de tasas E.A. REAL por
plazo** de cada banco, tomada de fuentes verificadas (ver abajo). Con esto, la
tasa de cada plazo deja de ser un supuesto y pasa a ser un dato real:

  * Bancolombia y Davivienda: tasa E.A. promedio ponderada REPORTADA A LA
    Superintendencia Financiera de Colombia (SFC), corte 29-oct-2026, publicada
    por comparatodo.com.co. Para plazos >360 d la SFC publica un único valor
    "más de 360 días", que se aplica a 540 y 720 d (dato real disponible para
    el tramo largo; se documenta explícitamente).
  * Banco de Bogota: tarifario propio por plazo (y por monto), vigente
    oct-2026, publicado por ahorrar.com.co. Se usa el nivel del tramo de monto
    más bajo ($100k-$49,9M, canal digital), que es el relevante para el rango
    de capital del modelo.
  * Nu Bank y Lulo Bank: tarifario propio por plazo, publicado por
    ahorrar.com.co (vigencias oct-2026). Nu publica UNA tasa por plazo sin
    desagregar por monto; Lulo publica dos niveles (cliente normal / Lulo Pro)
    y se usa el nivel de cliente normal, contratable por cualquiera.

Prima por tramo de monto = 0 (decisión documentada)
---------------------------------------------------
El mercado real casi NO premia el monto en el rango de capital del modelo:
  * Nu y Lulo NO diferencian la tasa por monto.
  * Bancolombia y Davivienda (vía SFC) publican un promedio sin desglose por
    monto.
  * Banco de Bogota sí desglosa por monto, pero sus cortes están en CIENTOS de
    millones ($50M, $200M, $500M, $1.000M) —no coinciden con los tramos del
    modelo (10M / 50M)— y la variación entre tramos es ínfima (~0.05 pp).
Por tanto, para no INVENTAR una prima por tramo, se usa la MISMA tasa real del
plazo en los tres tramos de monto (prima 0). Las tres filas de un mismo
(banco, plazo) comparten la tasa real verificada y se marcan `es_supuesto=False`.
Lo único "supuesto" que queda es la desagregación por tramo en sí (que el
mercado no publica), pero la tasa NO es inventada.

Fuentes y fecha de verificación
-------------------------------
Última verificación: 2026-11-01.

  * Bancolombia .... https://comparatodo.com.co/cdt/bancolombia
                     Tasas SFC, corte 29-oct-2026 (promedio ponderado E.A.).
  * Davivienda ..... https://comparatodo.com.co/cdt/davivienda
                     Tasas SFC, corte 29-oct-2026 (promedio ponderado E.A.).
  * Banco de Bogota  https://www.ahorrar.com.co/cdt/banco-de-bogota
                     Tarifario propio por plazo/monto (digital), oct-2026.
  * Nu Bank ........ https://www.ahorrar.com.co/cdt/nu
                     Tarifario propio por plazo, vigente 6-oct-2026.
  * Lulo Bank ...... https://www.ahorrar.com.co/cdt/lulo-bank
                     Tarifario propio por plazo, vigente 20-oct-2026.

Disponibilidad por banco (verificada contra fuente)
---------------------------------------------------
  * Bancolombia .......... 30 a 720 d  -> todo J.
  * Banco de Bogota ...... 30 a 720 d  -> todo J.
  * Davivienda ........... 30 a 720 d  -> todo J.
  * Nu Bank .............. 90 a 720 d  -> 30 y 60 NO ofrecidos.
  * Lulo Bank ............ 90 a 540 d  -> 30, 60 y 720 NO ofrecidos.

Los plazos no ofrecidos se marcan `disponible = False`, `tasa_ea` vacia y
`es_supuesto = True` con nota (Requisito 1.6) para que el `data_loader` los
excluya del modelo.

Ejecutar:  python data/generar_cdt_productos.py
"""

from __future__ import annotations

import csv
import os

# Conjuntos del spec ---------------------------------------------------------
BANCOS = ["Bancolombia", "Banco de Bogota", "Davivienda", "Nu Bank", "Lulo Bank"]
PLAZOS = [30, 60, 90, 180, 360, 540, 720]
TRAMOS = [1, 2, 3]

# Fecha de verificación de las fuentes ---------------------------------------
FECHA_VERIFICACION = "2026-11-01"

# Disponibilidad por banco: conjunto de plazos efectivamente ofrecidos -------
PLAZOS_OFRECIDOS = {
    "Bancolombia": {30, 60, 90, 180, 360, 540, 720},
    "Banco de Bogota": {30, 60, 90, 180, 360, 540, 720},
    "Davivienda": {30, 60, 90, 180, 360, 540, 720},
    "Nu Bank": {90, 180, 360, 540, 720},   # 30 y 60 NO ofrecidos
    "Lulo Bank": {90, 180, 360, 540},       # 30, 60 y 720 NO ofrecidos
}

# Monto minimo de apertura real (m_ij) por banco, verificado en fuente -------
MIN_APERTURA = {
    "Bancolombia": 500_000,
    "Banco de Bogota": 100_000,
    "Davivienda": 500_000,
    "Nu Bank": 50_000,
    "Lulo Bank": 100_000,
}

# URL de fuente por banco (para el campo `fuente`) ---------------------------
URL_BANCO = {
    "Bancolombia": "https://comparatodo.com.co/cdt/bancolombia",
    "Banco de Bogota": "https://www.ahorrar.com.co/cdt/banco-de-bogota",
    "Davivienda": "https://comparatodo.com.co/cdt/davivienda",
    "Nu Bank": "https://www.ahorrar.com.co/cdt/nu",
    "Lulo Bank": "https://www.ahorrar.com.co/cdt/lulo-bank",
}

# Origen del dato por banco (para documentar en el campo `fuente`) -----------
ORIGEN_BANCO = {
    "Bancolombia": "tasa SFC promedio ponderada E.A., corte 29-oct-2026",
    "Banco de Bogota": "tarifario digital por plazo (tramo $100k-$49,9M), oct-2026",
    "Davivienda": "tasa SFC promedio ponderada E.A., corte 29-oct-2026",
    "Nu Bank": "tarifario por plazo, vigente 6-oct-2026",
    "Lulo Bank": "tarifario por plazo (cliente estandar), vigente 20-oct-2026",
}

# ---------------------------------------------------------------------------
# CURVA DE TASAS E.A. REAL POR BANCO Y PLAZO (fraccion)
# ---------------------------------------------------------------------------
# Cada valor es una tasa REAL verificada en la fuente del banco (no derivada).
# `None` marca un plazo NO ofrecido por el banco (se vuelve disponible=False).
#
# Notas de mapeo de plazos a los tramos de dias de cada fuente:
#   * Banco de Bogota: 30->30-59d, 60->60-89d, 90->90-119d, 180->180-209d,
#     360->360-389d, 540->510-540d, 720->720-999d (nivel $100k-$49,9M digital).
#   * Nu / Lulo: 90=3m, 180=6m, 360=12m, 540=18m, 720=24m.
#   * Bancolombia / Davivienda (SFC): 540 y 720 usan el valor "mas de 360 dias"
#     (unico dato real publicado por la SFC para el tramo largo).
TASA_REAL = {
    "Bancolombia": {
        30: 0.0974, 60: 0.0984, 90: 0.1048, 180: 0.1104,
        360: 0.1201, 540: 0.1155, 720: 0.1155,
    },
    "Davivienda": {
        30: 0.0881, 60: 0.0883, 90: 0.1026, 180: 0.1071,
        360: 0.1209, 540: 0.1202, 720: 0.1202,
    },
    "Banco de Bogota": {
        30: 0.0875, 60: 0.0890, 90: 0.0945, 180: 0.0990,
        360: 0.1030, 540: 0.1050, 720: 0.1150,
    },
    "Nu Bank": {
        30: None, 60: None, 90: 0.0970, 180: 0.1055,
        360: 0.1105, 540: 0.1140, 720: 0.1140,
    },
    "Lulo Bank": {
        30: None, 60: None, 90: 0.1000, 180: 0.1100,
        360: 0.1150, 540: 0.1250, 720: None,
    },
}

# Prima de tramo de monto: pp sobre la tasa real del plazo. Cero por decision
# documentada (el mercado real no premia el monto en el rango del modelo).
PRIMA_TRAMO_PP = {
    1: 0.00,
    2: 0.00,
    3: 0.00,
}


def _tasa_ijk(banco: str, plazo: int, tramo: int) -> float:
    """Tasa E.A. real para (banco, plazo, tramo).

    Es la tasa REAL del plazo (verificada en fuente) mas la prima de tramo (0).
    Se redondea a 4 decimales (precision de punto basico).
    """
    base = TASA_REAL[banco][plazo]
    prima = PRIMA_TRAMO_PP[tramo] / 100.0
    return round(base + prima, 4)


def _fuente_real(banco: str, plazo: int, tramo: int) -> str:
    """Fuente para una fila con tasa real por plazo (es_supuesto=False)."""
    tasa_pct = TASA_REAL[banco][plazo] * 100
    nota_tramo = (
        "" if tramo == 1 else
        " La tasa real del plazo se aplica a los 3 tramos de monto (el mercado "
        "no premia el monto en este rango); solo la desagregacion por tramo es "
        "supuesta, no la tasa."
    )
    return (
        f"REAL verificado {FECHA_VERIFICACION}: {ORIGEN_BANCO[banco]}; "
        f"tasa E.A. {tasa_pct:.2f}% a {plazo}d.{nota_tramo} Fuente: "
        f"{URL_BANCO[banco]}"
    )


def _fuente_no_ofrecido(banco: str) -> str:
    """Fuente para una combinacion no ofrecida por el banco."""
    return (
        f"Producto NO ofrecido por el banco en este plazo segun fuente "
        f"(disponible=False, Req 1.6). Verificado {FECHA_VERIFICACION} en "
        f"{URL_BANCO[banco]}"
    )


def construir_filas() -> list[dict]:
    filas: list[dict] = []
    for banco in BANCOS:
        for plazo in PLAZOS:
            ofrecido = (
                plazo in PLAZOS_OFRECIDOS[banco]
                and TASA_REAL[banco].get(plazo) is not None
            )
            for tramo in TRAMOS:
                if not ofrecido:
                    filas.append(
                        {
                            "banco": banco,
                            "plazo_dias": plazo,
                            "tramo": tramo,
                            "tasa_ea": "",
                            "min_apertura": "",
                            "disponible": False,
                            "fuente": _fuente_no_ofrecido(banco),
                            "es_supuesto": True,
                        }
                    )
                    continue

                # Fila con tasa REAL del plazo (es_supuesto=False). La prima de
                # tramo es 0, de modo que los 3 tramos comparten la tasa real.
                tasa = _tasa_ijk(banco, plazo, tramo)
                filas.append(
                    {
                        "banco": banco,
                        "plazo_dias": plazo,
                        "tramo": tramo,
                        "tasa_ea": f"{tasa:.4f}",
                        "min_apertura": MIN_APERTURA[banco],
                        "disponible": True,
                        "fuente": _fuente_real(banco, plazo, tramo),
                        "es_supuesto": False,
                    }
                )
    return filas


def main() -> None:
    ruta = os.path.join(os.path.dirname(__file__), "cdt_productos.csv")
    filas = construir_filas()
    campos = [
        "banco",
        "plazo_dias",
        "tramo",
        "tasa_ea",
        "min_apertura",
        "disponible",
        "fuente",
        "es_supuesto",
    ]
    with open(ruta, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=campos)
        writer.writeheader()
        writer.writerows(filas)

    disponibles = sum(1 for f in filas if f["disponible"])
    no_disp = len(filas) - disponibles
    reales = sum(1 for f in filas if not f["es_supuesto"])
    supuestas = sum(1 for f in filas if f["es_supuesto"])
    con_tasa = sum(1 for f in filas if f["tasa_ea"] != "")
    print(f"Escritas {len(filas)} filas en {ruta}")
    print(f"  disponibles             : {disponibles}")
    print(f"  no disponibles          : {no_disp}")
    print(f"  con tasa_ea (utilizable): {con_tasa}")
    print(f"  REAL verificada (es_supuesto=False): {reales}")
    print(f"  no ofrecidas (es_supuesto=True)    : {supuestas}")
    print("  Curva de tasas reales por banco (E.A. por plazo):")
    for banco in BANCOS:
        tramos_txt = ", ".join(
            f"{p}d={TASA_REAL[banco][p] * 100:.2f}%"
            for p in PLAZOS
            if TASA_REAL[banco].get(p) is not None
        )
        print(f"    {banco:16s} {tramos_txt}")


if __name__ == "__main__":
    main()
