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
# Liquidez por fechas (política de tesorería) — reglas por umbral de plazo
# ---------------------------------------------------------------------------
# Esta es la respuesta a la retroalimentación de la profesora: el inversionista
# necesita poder disponer de parte del capital en una FECHA intermedia (p. ej. a
# los 6 meses) sin que el modelo inmovilice todo el dinero en el plazo más
# rentable (720 d). Como el modelo no es multiperiodo, "tener liquidez a los D
# días" se traduce en: una fracción del capital debe colocarse en CDT que
# vencen en <= D días (así ese dinero está disponible en esa fecha).
#
# Cada regla restringe la fracción del capital colocada en CDT con plazo <= D:
#       min_frac * A  <=  (capital en plazos j <= hasta_dias)  <=  max_frac * A
# donde:
#   hasta_dias : umbral de plazo en días (debe estar en PLAZOS_VALIDOS o ser un
#                entero positivo). Agrupa todos los CDT que vencen en <= D días.
#   min_frac   : fracción mínima del capital que debe vencer en <= D días
#                (None = sin cota inferior, equivale a 0).
#   max_frac   : fracción máxima del capital que puede quedar en <= D días
#                (None = sin cota superior, equivale a 1).
#
# Escenario base (política editable del equipo):
#   - Al menos 30% del capital vence en <= 180 días  -> liquidez a 6 meses.
#   - A lo sumo 40% del capital queda en plazos > 360 días: se expresa como
#     "al menos 60% vence en <= 360 días" (hasta_dias=360, min_frac=0.60),
#     que es la formulación lineal equivalente sobre la partición <= D.
LIQUIDEZ = {
    "reglas": [
        {"hasta_dias": 180, "min_frac": 0.30, "max_frac": None},
        {"hasta_dias": 360, "min_frac": 0.60, "max_frac": None},
    ],
    # Compatibilidad hacia atrás: las 4 cotas corto/largo siguen aceptándose.
    # Partición corto = {j <= 180}, largo = {j > 180}. None = cota desactivada.
    # Se dejan en None; la política activa vive en "reglas".
    "L_corto": None,
    "U_corto": None,
    "L_largo": None,
    "U_largo": None,
}

# ---------------------------------------------------------------------------
# Concentración máxima por plazo (q_j), fracción de A en (0, 1]
# ---------------------------------------------------------------------------
# Diversificación por PLAZO (segunda parte de la retroalimentación): evita que
# todo el capital quede en un único plazo (p. ej. todo a 720 d). Para cada
# plazo j con alguna combinación utilizable se impone:
#       Σ_{i,k} x_ijk  <=  q_j * A
# Una sola cota global (clave "default") aplica a todos los plazos; se puede
# afinar por plazo específico con claves enteras, p. ej. {720: 0.30}.
# None / dict vacío  =>  restricción DESACTIVADA (no se inventa diversificación).
CONCENTRACION_PLAZO_MAX = {
    "default": 0.40,   # ningún plazo único puede concentrar más del 40% de A
}


def get_config() -> dict:
    """Devuelve la configuración consolidada como un único diccionario.

    Estructura esperada por `data_loader` (tarea 3):
        {
            "A": int,
            "tramos": {k: (L_k, U_k)},
            "concentracion_max": {banco: p_i},
            "liquidez": {
                "reglas": [{"hasta_dias": D, "min_frac": .., "max_frac": ..}, ...],
                "L_corto": .., "U_corto": .., "L_largo": .., "U_largo": ..,
            },
            "concentracion_plazo_max": {"default": q, <plazo>: q_j, ...},
        }
    """
    return {
        "A": A,
        "tramos": TRAMOS,
        "concentracion_max": CONCENTRACION_MAX,
        "liquidez": LIQUIDEZ,
        "concentracion_plazo_max": CONCENTRACION_PLAZO_MAX,
    }
