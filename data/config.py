"""Configuración de parámetros escalares y de política del modelo de CDT.

Este archivo define los parámetros que NO van en la matriz tabular de productos
(`cdt_productos.csv`): el capital total `A`, los límites de los tramos de monto
`K`, la concentración máxima por banco `p_i` y las cotas de liquidez.

Principio de cero invención de datos
------------------------------------
- Los límites de tramo provienen del enunciado del problema (Requisito 1.3).
- La concentración `p_i` es una política de diversificación del equipo.
- Las cotas de liquidez (`L_corto/U_corto/L_largo/U_largo`) son política de
  tesorería. Mientras el equipo no fije un valor real, se dejan en `None`, lo
  que DESACTIVA esa cota en el modelo (no se inventa ningún porcentaje).

Las claves de banco deben coincidir exactamente con la columna `banco` de
`cdt_productos.csv` y con el conjunto `I` del spec.
"""

# ---------------------------------------------------------------------------
# Capital total disponible a invertir (A)
# ---------------------------------------------------------------------------
# Valor de referencia del enunciado/escenario. Ajústese al capital real del
# caso de estudio antes de ejecutar el modelo en producción.
A = 100_000_000

# ---------------------------------------------------------------------------
# Límites de los tramos de monto (K = {1, 2, 3})  ->  (L_k, U_k)
# ---------------------------------------------------------------------------
# Tramo 1: [50.000, 10.000.000]
# Tramo 2: [10.000.001, 50.000.000]
# Tramo 3: (> 50.000.000)  ->  cota superior None (sin cota superior / infinito)
# Fuente: Requisito 1.3 del spec (no es un supuesto inventado).
TRAMOS = {
    1: (50_000, 10_000_000),
    2: (10_000_001, 50_000_000),
    3: (50_000_001, None),
}

# ---------------------------------------------------------------------------
# Concentración máxima por banco (p_i), fracción de A en (0, 1]
# ---------------------------------------------------------------------------
# Política de diversificación del equipo. Un valor menor obliga a repartir el
# capital entre más entidades. Debe cubrir exactamente el conjunto I.
CONCENTRACION_MAX = {
    "Bancolombia": 0.40,
    "Banco de Bogota": 0.40,
    "Davivienda": 0.40,
    "Nu Bank": 0.40,
    "Lulo Bank": 0.40,
}

# ---------------------------------------------------------------------------
# Cotas de liquidez (política de tesorería) — fracciones de A
# ---------------------------------------------------------------------------
# Partición de plazos: corto = {j <= 180}, largo = {j > 180}.
#   L_corto <= (capital en plazos cortos) / A <= U_corto
#   L_largo <= (capital en plazos largos) / A <= U_largo
# None  =>  cota DESACTIVADA (equivale a 0 para las inferiores y 1 para las
# superiores). NO inventar porcentajes: dejar en None hasta fijar la política.
LIQUIDEZ = {
    "L_corto": None,
    "U_corto": None,
    "L_largo": None,
    "U_largo": None,
}


def get_config() -> dict:
    """Devuelve la configuración consolidada como un único diccionario.

    Estructura esperada por `data_loader` (tarea 3):
        {
            "A": int,
            "tramos": {k: (L_k, U_k)},
            "concentracion_max": {banco: p_i},
            "liquidez": {"L_corto": .., "U_corto": .., "L_largo": .., "U_largo": ..},
        }
    """
    return {
        "A": A,
        "tramos": TRAMOS,
        "concentracion_max": CONCENTRACION_MAX,
        "liquidez": LIQUIDEZ,
    }
