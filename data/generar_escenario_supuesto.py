"""Generador del ESCENARIO ILUSTRATIVO de tasas supuestas — `escenario_supuesto.csv`.

PROPÓSITO Y ADVERTENCIA (principio de cero invención de datos)
--------------------------------------------------------------
La matriz real `cdt_productos.csv` deja `tasa_ea` VACÍA en las 105 filas porque
ninguna fuente pública desagrega la tasa por los 3 tramos de monto del spec.
Por eso, ejecutar `main.py` sobre los datos reales NO produce asignación óptima
(el flujo termina con el mensaje "fije tasas supuestas").

Para poder redactar la Sección de Resultados del artículo con SALIDAS REALES de
Python (y no cifras inventadas a mano), este script crea un escenario
EXPLÍCITAMENTE ETIQUETADO COMO SUPUESTO: un conjunto de tasas E.A. ilustrativas,
plausibles pero NO verificadas contra tarifarios oficiales por (i, j, k). TODAS
las filas llevan `es_supuesto = True` y el campo `fuente` declara que son un
supuesto del artículo, no tasas reales de mercado.

Estas tasas NO deben presentarse como reales. El artículo las cita como
escenario ilustrativo (ver Sección 5 y la nota de la Sección 8 Referencias).

Construcción de las tasas supuestas (regla transparente)
--------------------------------------------------------
Las tasas se construyen con una regla simple y declarada, no al azar:

  tasa_ea(i, j, k) = base_banco[i] + ajuste_plazo[j] + prima_tramo[k]

- `base_banco`: nivel E.A. ancla por banco, inspirado en los órdenes de magnitud
  de los agregadores citados en `cdt_productos.csv` (p. ej. Lulo con la oferta
  más alta; Banco de Bogotá algo más baja). Son ANCLAS, no tasas puntuales.
- `ajuste_plazo`: los plazos intermedios (180-360 d) pagan algo más que los muy
  cortos; los muy largos ceden un poco. Es un perfil ilustrativo de la curva.
- `prima_tramo`: premia colocar montos mayores (tramo 3 > tramo 2 > tramo 1),
  que es justamente la lógica escalonada por monto que motiva el MILP.

La disponibilidad por banco/plazo reutiliza la MISMA de `generar_cdt_productos.py`
(Nu desde 90 d; Lulo 90-540 d) para que el escenario sea coherente con el resto
del proyecto. Las combinaciones no ofrecidas quedan `disponible = False`.

Ejecutar:  python data/generar_escenario_supuesto.py
"""

from __future__ import annotations

import csv
import os

BANCOS = ["Bancolombia", "Banco de Bogota", "Davivienda", "Nu Bank", "Lulo Bank"]
PLAZOS = [30, 60, 90, 180, 360, 540, 720]
TRAMOS = [1, 2, 3]

# Disponibilidad idéntica a la matriz real (coherencia de proyecto).
PLAZOS_OFRECIDOS = {
    "Bancolombia": {30, 60, 90, 180, 360, 540, 720},
    "Banco de Bogota": {30, 60, 90, 180, 360, 540, 720},
    "Davivienda": {30, 60, 90, 180, 360, 540, 720},
    "Nu Bank": {90, 180, 360, 540, 720},
    "Lulo Bank": {90, 180, 360, 540},
}

MIN_APERTURA = {
    "Bancolombia": 100_000,
    "Banco de Bogota": 100_000,
    "Davivienda": 100_000,
    "Nu Bank": 100_000,
    "Lulo Bank": 100_000,
}

# --- Regla de construcción de tasas supuestas (fracción E.A.) ---------------
# Nivel ancla por banco (orden de magnitud inspirado en agregadores citados).
BASE_BANCO = {
    "Bancolombia": 0.1050,
    "Banco de Bogota": 0.0990,
    "Davivienda": 0.1075,
    "Nu Bank": 0.1055,
    "Lulo Bank": 0.1180,
}

# Perfil de curva por plazo (puntos porcentuales sobre la base).
AJUSTE_PLAZO = {
    30: -0.0060,
    60: -0.0040,
    90: -0.0010,
    180: 0.0010,
    360: 0.0035,
    540: 0.0025,
    720: 0.0005,
}

# Prima por tramo de monto: a mayor monto, mejor tasa (lógica escalonada).
PRIMA_TRAMO = {
    1: 0.0000,
    2: 0.0030,
    3: 0.0060,
}

FECHA = "2026-02"
CRITERIO_SUPUESTO = (
    "ESCENARIO ILUSTRATIVO DEL ARTICULO (es_supuesto=True): tasa_ea construida con la "
    "regla declarada base_banco[i] + ajuste_plazo[j] + prima_tramo[k] en "
    "data/generar_escenario_supuesto.py. NO es una tasa real de mercado ni un tarifario "
    "oficial por (i,j,k); se usa solo para generar salidas de Python reproducibles en la "
    f"Seccion de Resultados. Consulta de anclas: {FECHA}."
)
NOTA_NO_OFRECIDO = (
    "Producto NO ofrecido por el banco en este plazo (coherente con cdt_productos.csv, "
    f"Req 1.6). Consulta: {FECHA}."
)


def tasa_supuesta(banco: str, plazo: int, tramo: int) -> float:
    """Tasa E.A. supuesta según la regla declarada (redondeada a 4 decimales)."""
    bruta = BASE_BANCO[banco] + AJUSTE_PLAZO[plazo] + PRIMA_TRAMO[tramo]
    return round(bruta, 4)


def construir_filas() -> list[dict]:
    filas: list[dict] = []
    for banco in BANCOS:
        for plazo in PLAZOS:
            ofrecido = plazo in PLAZOS_OFRECIDOS[banco]
            for tramo in TRAMOS:
                if ofrecido:
                    filas.append(
                        {
                            "banco": banco,
                            "plazo_dias": plazo,
                            "tramo": tramo,
                            "tasa_ea": f"{tasa_supuesta(banco, plazo, tramo):.4f}",
                            "min_apertura": MIN_APERTURA[banco],
                            "disponible": True,
                            "fuente": CRITERIO_SUPUESTO,
                            "es_supuesto": True,
                        }
                    )
                else:
                    filas.append(
                        {
                            "banco": banco,
                            "plazo_dias": plazo,
                            "tramo": tramo,
                            "tasa_ea": "",
                            "min_apertura": "",
                            "disponible": False,
                            "fuente": NOTA_NO_OFRECIDO,
                            "es_supuesto": True,
                        }
                    )
    return filas


def main() -> None:
    ruta = os.path.join(os.path.dirname(__file__), "escenario_supuesto.csv")
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
    print(f"Escritas {len(filas)} filas en {ruta}")
    print(f"  disponibles      : {disponibles}")
    print(f"  no disponibles   : {len(filas) - disponibles}")
    print(f"  es_supuesto=True : {sum(1 for f in filas if f['es_supuesto'])}")


if __name__ == "__main__":
    main()
