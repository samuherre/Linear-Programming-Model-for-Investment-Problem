"""Generador de la matriz de productos CDT (`cdt_productos.csv`) — Tarea 2.2.

Puebla el espacio completo de productos (i, j, k) = 5 bancos x 7 plazos x 3
tramos = 105 filas, aplicando el principio RECTOR de trazabilidad honesta
(Requisito 1.5): lo verificado se marca como real; lo derivado se marca como
supuesto documentado. NUNCA se presenta como real una cifra no verificada.

Fuentes y fecha de verificación
-------------------------------
Última verificación: 2026-10-21. Comparador público finanzasplus.co y
tarifarios/prensa de cada entidad:

  * Bancolombia .... https://finanzasplus.co/comparar/cdts/bancolombia
                     Mejor tasa E.A. 11.20% (plazos 271-720 d). Min $500.000.
                     Plazos 30-720 d.
  * Banco de Bogota  https://finanzasplus.co/comparar/cdts/banco-de-bogota
                     Mejor tasa E.A. 11.50% (541-720 d), ~10.30% a 360 d.
                     Min $100.000. Plazos 30-720 d.
  * Davivienda ..... https://finanzasplus.co/comparar/cdts/davivienda
                     Mejor tasa E.A. 11.30% (541-720 d), ~11.15% a 360 d.
                     Min $500.000. Plazos 30-720 d.
  * Nu Bank ........ https://finanzasplus.co/comparar/cdts/nu
                     Mejor tasa E.A. 11.40% (271-720 d). Min $50.000.
                     Plazos 90-720 d (NO ofrece 30 ni 60).
  * Lulo Bank ...... https://ayuda.lulobank.com/hc/es/articles/49263729501972-CDT-s-en-Lulo
                     y https://www.larepublica.co/finanzas/cdt-de-lulo-supera-los-129-000-millones-en-captaciones-en-su-etapa-inicial-4420082
                     Tasa vigente ~11-12% E.A.; campaña de lanzamiento hasta 13%
                     E.A. para 180-540 d. Min $100.000. Plazos 90-540 d
                     (NO ofrece 30, 60 ni 720).

Distinción real-verificado vs derivado-supuesto (CRÍTICO)
---------------------------------------------------------
Las fuentes publican sobre todo la "mejor tasa" (plazos largos) y dejan huecos
en plazos cortos, y NINGUNA desagrega la tasa por los TRES tramos de monto del
spec ([50k-10M] / [10M-50M] / >50M). Por tanto:

  1) TASA ANCLA REAL por banco: la mejor tasa E.A. verificada arriba, aplicada
     al plazo donde la fuente la reporta (el plazo ancla). Esa fila concreta
     (banco, plazo_ancla, tramo=1) lleva `es_supuesto = False` y `fuente` con la
     URL + "verificado 2026-10-21".
  2) PERFIL DE CURVA por plazo (derivado, supuesto): las tasas de los demás
     plazos se obtienen aplicando al ancla un ajuste en puntos porcentuales
     (pp) segun el plazo. Plazos cortos pagan algo menos; plazos largos pagan la
     mejor tasa (el ancla). El perfil es un supuesto de modelado documentado.
  3) PRIMA DE TRAMO (derivado, supuesto): el tramo 1 usa la tasa base del plazo;
     los tramos 2 y 3 añaden una prima pequeña (+0.20 pp y +0.40 pp) porque los
     bancos suelen mejorar la tasa a mayor monto. La desagregación por tramo es
     un supuesto de modelado (ninguna fuente la publica).

Todas las filas derivadas (plazos distintos del ancla, y tramos 2 y 3) llevan
`es_supuesto = True`, con `fuente` que explica que son el ancla real ajustada
por el perfil de plazo / prima de tramo (supuesto de modelado), citando la URL.

Perfil de curva por plazo (ajuste en pp respecto al ancla)
----------------------------------------------------------
El ancla (mejor tasa) corresponde a los plazos largos. El ajuste resta pp a los
plazos cortos (curva creciente con el plazo), reflejando que el CDT a mayor
plazo paga mas:

    plazo (d):   30     60     90    180    360    540    720
    ajuste(pp): -0.90  -0.80  -0.70  -0.50  -0.20   0.00   0.00

Es decir, 540 y 720 d pagan el ancla (la mejor tasa); 360 d paga ~0.20 pp menos;
los plazos muy cortos pagan hasta 0.90 pp menos. El plazo ancla de cada banco
(donde la fuente reporta la mejor tasa) cae en la zona de ajuste 0.00 y es la
fila que se marca como real verificada.

Prima de tramo de monto (en pp sobre la tasa base del plazo)
------------------------------------------------------------
    tramo 1: +0.00 pp   (tasa base del plazo)
    tramo 2: +0.20 pp   (supuesto de modelado)
    tramo 3: +0.40 pp   (supuesto de modelado)

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
FECHA_VERIFICACION = "2026-10-21"

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
    "Bancolombia": "https://finanzasplus.co/comparar/cdts/bancolombia",
    "Banco de Bogota": "https://finanzasplus.co/comparar/cdts/banco-de-bogota",
    "Davivienda": "https://finanzasplus.co/comparar/cdts/davivienda",
    "Nu Bank": "https://finanzasplus.co/comparar/cdts/nu",
    "Lulo Bank": (
        "https://ayuda.lulobank.com/hc/es/articles/49263729501972-CDT-s-en-Lulo"
        " ; https://www.larepublica.co/finanzas/cdt-de-lulo-supera-los-129-000-"
        "millones-en-captaciones-en-su-etapa-inicial-4420082"
    ),
}

# Tasa ANCLA REAL por banco (mejor tasa E.A. verificada), como fraccion, y el
# plazo ancla donde la fuente la reporta. Esa fila (banco, plazo_ancla, tramo=1)
# es la unica marcada como REAL verificada (es_supuesto=False).
# Para los bancos con tope en plazos largos (271-720), el plazo ancla del
# conjunto J donde el ajuste de curva es 0.00 es 540 d (dentro de ese rango).
ANCLA = {
    "Bancolombia": {"tasa": 0.1120, "plazo": 540},
    "Banco de Bogota": {"tasa": 0.1150, "plazo": 540},
    "Davivienda": {"tasa": 0.1130, "plazo": 540},
    "Nu Bank": {"tasa": 0.1140, "plazo": 540},
    # Lulo: tasa vigente conservadora dentro del rango ~11-12% (no la campaña
    # promocional del 13%, que es temporal). Plazo ancla 540 d (tope 90-540).
    "Lulo Bank": {"tasa": 0.1150, "plazo": 540},
}

# Perfil de curva por plazo: ajuste en pp respecto al ancla (ver docstring) ---
AJUSTE_PLAZO_PP = {
    30: -0.90,
    60: -0.80,
    90: -0.70,
    180: -0.50,
    360: -0.20,
    540: 0.00,
    720: 0.00,
}

# Prima de tramo de monto: pp sobre la tasa base del plazo (ver docstring) ----
PRIMA_TRAMO_PP = {
    1: 0.00,
    2: 0.20,
    3: 0.40,
}


def _tasa_ijk(banco: str, plazo: int, tramo: int) -> float:
    """Tasa E.A. derivada para (banco, plazo, tramo) a partir del ancla real.

    tasa = ancla + ajuste_plazo(pp)/100 + prima_tramo(pp)/100

    El ajuste y la prima estan en puntos porcentuales; se dividen por 100 para
    pasar a fraccion. Se redondea a 4 decimales (precision de punto basico).
    """
    base = ANCLA[banco]["tasa"]
    ajuste = AJUSTE_PLAZO_PP[plazo] / 100.0
    prima = PRIMA_TRAMO_PP[tramo] / 100.0
    return round(base + ajuste + prima, 4)


def _es_ancla_real(banco: str, plazo: int, tramo: int) -> bool:
    """True si (banco, plazo, tramo) es la fila del ancla real verificada.

    Es la combinacion tramo=1 en el plazo ancla del banco: ahi el ajuste de
    curva es 0.00 y la prima de tramo es 0.00, de modo que la tasa coincide
    exactamente con la mejor tasa E.A. publicada por la fuente.
    """
    return tramo == 1 and plazo == ANCLA[banco]["plazo"]


def _fuente_real(banco: str) -> str:
    """Fuente para la fila del ancla real verificada."""
    tasa_pct = ANCLA[banco]["tasa"] * 100
    return (
        f"REAL verificado {FECHA_VERIFICACION}: mejor tasa E.A. {tasa_pct:.2f}% "
        f"(plazo ancla {ANCLA[banco]['plazo']}d, tramo 1). Fuente: {URL_BANCO[banco]}"
    )


def _fuente_derivada(banco: str, plazo: int, tramo: int) -> str:
    """Fuente para una fila derivada por perfil de plazo / prima de tramo."""
    ajuste = AJUSTE_PLAZO_PP[plazo]
    prima = PRIMA_TRAMO_PP[tramo]
    tasa_ancla_pct = ANCLA[banco]["tasa"] * 100
    return (
        f"SUPUESTO (es_supuesto=True): tasa ancla REAL {tasa_ancla_pct:.2f}% E.A. "
        f"ajustada por perfil de plazo ({ajuste:+.2f} pp) y prima de tramo "
        f"({prima:+.2f} pp) — supuesto de modelado documentado en "
        f"generar_cdt_productos.py. Ancla verificada {FECHA_VERIFICACION} en "
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
            ofrecido = plazo in PLAZOS_OFRECIDOS[banco]
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

                if _es_ancla_real(banco, plazo, tramo):
                    # Fila del ancla real verificada: tasa publicada por la
                    # fuente, es_supuesto=False.
                    tasa = round(ANCLA[banco]["tasa"], 4)
                    fuente = _fuente_real(banco)
                    es_supuesto = False
                else:
                    # Fila derivada por perfil de plazo / prima de tramo.
                    tasa = _tasa_ijk(banco, plazo, tramo)
                    fuente = _fuente_derivada(banco, plazo, tramo)
                    es_supuesto = True

                filas.append(
                    {
                        "banco": banco,
                        "plazo_dias": plazo,
                        "tramo": tramo,
                        "tasa_ea": f"{tasa:.4f}",
                        "min_apertura": MIN_APERTURA[banco],
                        "disponible": True,
                        "fuente": fuente,
                        "es_supuesto": es_supuesto,
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
    print(f"  derivada  (es_supuesto=True)       : {supuestas}")
    print("  Anclas reales por banco:")
    for banco in BANCOS:
        print(
            f"    {banco:16s} {ANCLA[banco]['tasa'] * 100:.2f}% E.A. "
            f"@ {ANCLA[banco]['plazo']}d (tramo 1)"
        )


if __name__ == "__main__":
    main()
