"""Carga y validación de la matriz de CDT — `data_loader.py` (Tarea 3).

Este módulo alimenta el modelo MILP con parámetros reales/supuestos de CDT. Su
responsabilidad es:

1. Leer la matriz tabular de productos `(i, j, k)` desde `data/` en **CSV** o
   **Excel** (`.csv`/`.xlsx`). Como respaldo admite un módulo Python que exponga
   una lista de diccionarios (misma estructura de columnas).
2. Leer los parámetros escalares y de política desde `data/config.py`
   (`get_config()`): capital `A`, límites de tramo `K`, concentración `p_i` y
   cotas de liquidez.
3. Validar tipos, rangos, coherencia de límites de tramo y las marcas de
   `fuente`/`es_supuesto` ANTES de construir el modelo (Requisito 1.7).
4. Precalcular el coeficiente objetivo `f_ijk = (1 + r_ijk)^(j/360) − 1`
   (Requisito 2.5).
5. Devolver estructuras indexadas por `(i, j, k)` y los escalares del problema,
   excluyendo las combinaciones no disponibles (`disponible = False`,
   Requisito 1.6).

Principio de cero invención de datos
------------------------------------
La matriz actual deja `tasa_ea` VACÍA en todas las filas porque ninguna fuente
pública desagrega la tasa por los tres tramos de monto del spec (ver
`data/generar_cdt_productos.py`). Este cargador NO inventa tasas: las filas
disponibles pero sin tasa numérica se EXCLUYEN del modelo y se reportan en
`info["excluidos_sin_tasa"]` para que el equipo fije la tasa supuesta de forma
explícita. Las filas marcadas `es_supuesto = True` o con `fuente` vacía se
reportan en `info["supuestos"]` para que el informe las señale (Requisito 1.5).

Si tras la carga no queda ninguna combinación con tasa utilizable, el modelo no
puede construirse; el llamador debe revisar `info` para entender por qué.
"""

from __future__ import annotations

import csv
import importlib
import importlib.util
import math
import os
from dataclasses import dataclass, field
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Conjuntos esperados del spec (Glosario de requisitos)
# ---------------------------------------------------------------------------
BANCOS_ESPERADOS = {
    "Bancolombia",
    "Banco de Bogota",
    "Davivienda",
    "Nu Bank",
    "Lulo Bank",
}
PLAZOS_VALIDOS = {30, 60, 90, 180, 360, 540, 720}
TRAMOS_VALIDOS = {1, 2, 3}

# Columnas obligatorias de la matriz tabular.
COLUMNAS_REQUERIDAS = [
    "banco",
    "plazo_dias",
    "tramo",
    "tasa_ea",
    "min_apertura",
    "disponible",
    "fuente",
    "es_supuesto",
]

# Umbral de advertencia para tasas E.A. claramente fuera de rango razonable.
# No es un dato inventado: es una validación defensiva (0 < r < 1 ≡ 0%-100%).
TASA_MIN = 0.0
TASA_MAX = 1.0


class DataLoaderError(ValueError):
    """Error de carga/validación de datos con mensaje claro para el usuario."""


@dataclass
class DatosCDT:
    """Estructuras de entrada ya validadas e indexadas por `(i, j, k)`.

    Atributos
    ---------
    bancos, plazos, tramos:
        Conjuntos efectivos presentes en las combinaciones utilizables.
    r, f, m, disp:
        Diccionarios indexados por la tupla `(banco, plazo, tramo)`:
        - `r`  : tasa efectiva anual `r_ijk`.
        - `f`  : factor de rendimiento del periodo `f_ijk`.
        - `m`  : monto mínimo de apertura `m_ij` (por combinación disponible).
        - `disp`: disponibilidad `disp_ijk ∈ {0, 1}` (siempre 1 en los índices
                  retornados, pues las no disponibles se excluyen).
    p:
        Concentración máxima por banco `p_i`.
    A:
        Capital total disponible.
    tramos_limites:
        `{k: (L_k, U_k)}` con `U_3 = None` (sin cota superior / infinito).
    liquidez:
        `{"L_corto", "U_corto", "L_largo", "U_largo"}`; `None` = cota desactivada.
    combinaciones:
        Lista ordenada de las tuplas `(i, j, k)` utilizables en el modelo.
    info:
        Metadatos de la carga (supuestos, exclusiones, conteos) para el reporte.
    """

    bancos: list[str]
    plazos: list[int]
    tramos: list[int]
    r: dict[tuple[str, int, int], float]
    f: dict[tuple[str, int, int], float]
    m: dict[tuple[str, int, int], float]
    disp: dict[tuple[str, int, int], int]
    p: dict[str, float]
    A: float
    tramos_limites: dict[int, tuple[float, Optional[float]]]
    liquidez: dict[str, Optional[float]]
    combinaciones: list[tuple[str, int, int]] = field(default_factory=list)
    info: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Utilidades de parseo robusto
# ---------------------------------------------------------------------------
def _es_vacio(valor: Any) -> bool:
    """True si el valor representa un dato ausente (vacío, None o NaN)."""
    if valor is None:
        return True
    if isinstance(valor, float) and math.isnan(valor):
        return True
    if isinstance(valor, str) and valor.strip() == "":
        return True
    return False


def _a_bool(valor: Any) -> bool:
    """Interpreta un valor tabular como booleano de forma tolerante."""
    if isinstance(valor, bool):
        return valor
    if isinstance(valor, (int, float)) and not (
        isinstance(valor, float) and math.isnan(valor)
    ):
        return bool(int(valor))
    texto = str(valor).strip().lower()
    if texto in {"true", "1", "si", "sí", "yes", "verdadero", "t"}:
        return True
    if texto in {"false", "0", "no", "falso", "f"}:
        return False
    raise DataLoaderError(f"No se pudo interpretar '{valor}' como booleano.")


def _a_entero(valor: Any, campo: str, contexto: str) -> int:
    """Convierte a entero validando que el dato exista y sea numérico."""
    if _es_vacio(valor):
        raise DataLoaderError(f"{contexto}: el campo '{campo}' está vacío.")
    try:
        # Permite "180" y 180.0 (pandas suele entregar floats).
        return int(float(valor))
    except (TypeError, ValueError):
        raise DataLoaderError(
            f"{contexto}: '{campo}'='{valor}' no es un entero válido."
        )


def _a_float(valor: Any, campo: str, contexto: str) -> float:
    """Convierte a float validando que el dato exista y sea numérico."""
    if _es_vacio(valor):
        raise DataLoaderError(f"{contexto}: el campo '{campo}' está vacío.")
    try:
        return float(valor)
    except (TypeError, ValueError):
        raise DataLoaderError(
            f"{contexto}: '{campo}'='{valor}' no es un número válido."
        )


# ---------------------------------------------------------------------------
# Lectura de la matriz tabular (CSV / Excel / módulo Python)
# ---------------------------------------------------------------------------
def _leer_filas(ruta: str) -> list[dict[str, Any]]:
    """Lee la matriz de productos y la devuelve como lista de diccionarios.

    Soporta `.csv`, `.xlsx`/`.xls` (vía pandas) y `.py` (módulo de respaldo que
    exponga `FILAS` o `get_filas()`). Lanza `DataLoaderError` si la ruta no
    existe o el formato no es soportado.
    """
    if not os.path.isfile(ruta):
        raise DataLoaderError(f"No existe el archivo de datos: {ruta}")

    ext = os.path.splitext(ruta)[1].lower()

    if ext == ".csv":
        with open(ruta, "r", newline="", encoding="utf-8") as fh:
            lector = csv.DictReader(fh)
            if lector.fieldnames is None:
                raise DataLoaderError(f"El archivo '{ruta}' está vacío.")
            return [dict(fila) for fila in lector]

    if ext in {".xlsx", ".xls"}:
        try:
            import pandas as pd  # import diferido: solo si se usa Excel
        except ImportError as exc:
            raise DataLoaderError(
                "Leer Excel requiere pandas y openpyxl instalados "
                "(ver requirements.txt)."
            ) from exc
        df = pd.read_excel(ruta)
        return df.to_dict(orient="records")

    if ext == ".py":
        # Respaldo: módulo Python con los datos como diccionarios.
        spec = importlib.util.spec_from_file_location("_cdt_datos_backup", ruta)
        if spec is None or spec.loader is None:
            raise DataLoaderError(f"No se pudo importar el módulo de datos: {ruta}")
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)
        if hasattr(modulo, "get_filas"):
            return list(modulo.get_filas())
        if hasattr(modulo, "FILAS"):
            return list(modulo.FILAS)
        raise DataLoaderError(
            f"El módulo de respaldo '{ruta}' debe exponer 'FILAS' o 'get_filas()'."
        )

    raise DataLoaderError(
        f"Formato no soportado '{ext}'. Use .csv, .xlsx/.xls o .py."
    )


# ---------------------------------------------------------------------------
# Validación de la configuración escalar
# ---------------------------------------------------------------------------
def _validar_config(config: dict[str, Any]) -> None:
    """Valida la coherencia de la configuración escalar y de política."""
    requeridas = {"A", "tramos", "concentracion_max", "liquidez"}
    faltantes = requeridas - set(config)
    if faltantes:
        raise DataLoaderError(
            f"Configuración incompleta; faltan claves: {sorted(faltantes)}."
        )

    if not isinstance(config["A"], (int, float)) or config["A"] <= 0:
        raise DataLoaderError(f"El capital A debe ser positivo; se recibió {config['A']}.")

    # --- Tramos: deben cubrir K = {1, 2, 3} con límites coherentes ----------
    tramos = config["tramos"]
    if set(tramos) != TRAMOS_VALIDOS:
        raise DataLoaderError(
            f"Los tramos deben ser exactamente {sorted(TRAMOS_VALIDOS)}; "
            f"se recibió {sorted(tramos)}."
        )
    anterior_sup: Optional[float] = None
    for k in sorted(tramos):
        limites = tramos[k]
        if not isinstance(limites, (tuple, list)) or len(limites) != 2:
            raise DataLoaderError(
                f"El tramo {k} debe ser una tupla (L_k, U_k); se recibió {limites}."
            )
        L_k, U_k = limites
        if L_k is None or L_k < 0:
            raise DataLoaderError(f"Tramo {k}: la cota inferior L_k debe ser ≥ 0.")
        if U_k is not None:
            if U_k < L_k:
                raise DataLoaderError(
                    f"Tramo {k}: la cota superior U_k={U_k} es menor que L_k={L_k}."
                )
        elif k != max(tramos):
            # Solo el último tramo puede ser abierto por arriba (U_3 = ∞).
            raise DataLoaderError(
                f"Solo el último tramo puede tener U_k=None; el tramo {k} no lo es."
            )
        # Coherencia entre tramos consecutivos: deben estar ordenados.
        if anterior_sup is not None and L_k < anterior_sup:
            raise DataLoaderError(
                f"Tramo {k}: L_k={L_k} se solapa con el tramo anterior "
                f"(U_{k - 1}={anterior_sup})."
            )
        anterior_sup = U_k if U_k is not None else anterior_sup

    # --- Concentración p_i: fracción en (0, 1] ------------------------------
    for banco, p_i in config["concentracion_max"].items():
        if not isinstance(p_i, (int, float)) or not (0 < p_i <= 1):
            raise DataLoaderError(
                f"Concentración p_i de '{banco}'={p_i} debe estar en (0, 1]."
            )

    # --- Liquidez: fracciones en [0, 1] o None, con L ≤ U -------------------
    liq = config["liquidez"]
    for clave in ("L_corto", "U_corto", "L_largo", "U_largo"):
        if clave not in liq:
            raise DataLoaderError(f"Falta la cota de liquidez '{clave}'.")
        val = liq[clave]
        if val is not None and not (0 <= val <= 1):
            raise DataLoaderError(
                f"Cota de liquidez '{clave}'={val} debe estar en [0, 1] o ser None."
            )
    for lo, hi, etiqueta in (
        ("L_corto", "U_corto", "corto"),
        ("L_largo", "U_largo", "largo"),
    ):
        if liq[lo] is not None and liq[hi] is not None and liq[lo] > liq[hi]:
            raise DataLoaderError(
                f"Liquidez {etiqueta}: L={liq[lo]} no puede superar U={liq[hi]}."
            )


# ---------------------------------------------------------------------------
# API principal
# ---------------------------------------------------------------------------
def _resolver_ruta_datos(data_dir: str, archivo_datos: Optional[str]) -> str:
    """Resuelve la ruta de la matriz de datos dentro de `data/`.

    Si no se especifica archivo, prefiere `cdt_productos.csv`; si no existe,
    busca el primer `.xlsx` disponible.
    """
    if archivo_datos is not None:
        return (
            archivo_datos
            if os.path.isabs(archivo_datos)
            else os.path.join(data_dir, archivo_datos)
        )
    por_defecto = os.path.join(data_dir, "cdt_productos.csv")
    if os.path.isfile(por_defecto):
        return por_defecto
    for nombre in sorted(os.listdir(data_dir)):
        if nombre.lower().endswith((".xlsx", ".xls")):
            return os.path.join(data_dir, nombre)
    raise DataLoaderError(
        f"No se encontró 'cdt_productos.csv' ni un Excel en {data_dir}."
    )


def cargar_datos(
    data_dir: Optional[str] = None,
    archivo_datos: Optional[str] = None,
    config: Optional[dict[str, Any]] = None,
) -> DatosCDT:
    """Carga, valida y devuelve los datos del modelo de CDT.

    Parámetros
    ----------
    data_dir:
        Carpeta de datos. Por defecto, `data/` junto a la raíz del proyecto.
    archivo_datos:
        Nombre o ruta de la matriz tabular. Por defecto, `cdt_productos.csv`.
    config:
        Configuración escalar ya resuelta. Si es `None`, se importa
        `data/config.py::get_config()`.

    Retorna
    -------
    DatosCDT con las estructuras indexadas por `(i, j, k)` y los escalares del
    problema. Las combinaciones no disponibles y las que carecen de tasa
    numérica se excluyen y se reportan en `.info`.

    Lanza
    -----
    DataLoaderError ante cualquier inconsistencia de datos o configuración.
    """
    # --- Resolver rutas por defecto relativas a la raíz del proyecto --------
    if data_dir is None:
        raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        data_dir = os.path.join(raiz, "data")
    if not os.path.isdir(data_dir):
        raise DataLoaderError(f"No existe la carpeta de datos: {data_dir}")

    # --- Configuración escalar ---------------------------------------------
    if config is None:
        config_path = os.path.join(data_dir, "config.py")
        if not os.path.isfile(config_path):
            raise DataLoaderError(f"No existe la configuración: {config_path}")
        spec = importlib.util.spec_from_file_location("_cdt_config", config_path)
        modulo_cfg = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo_cfg)
        if not hasattr(modulo_cfg, "get_config"):
            raise DataLoaderError("data/config.py debe exponer 'get_config()'.")
        config = modulo_cfg.get_config()
    _validar_config(config)

    # --- Leer la matriz tabular --------------------------------------------
    ruta_datos = _resolver_ruta_datos(data_dir, archivo_datos)
    filas = _leer_filas(ruta_datos)
    if not filas:
        raise DataLoaderError(f"La matriz de datos '{ruta_datos}' no tiene filas.")

    # Validar cabecera / columnas.
    columnas = set(filas[0].keys())
    faltan_cols = set(COLUMNAS_REQUERIDAS) - columnas
    if faltan_cols:
        raise DataLoaderError(
            f"Faltan columnas en '{ruta_datos}': {sorted(faltan_cols)}."
        )

    # --- Procesar fila a fila ----------------------------------------------
    r: dict[tuple[str, int, int], float] = {}
    f: dict[tuple[str, int, int], float] = {}
    m: dict[tuple[str, int, int], float] = {}
    disp: dict[tuple[str, int, int], int] = {}

    vistos: set[tuple[str, int, int]] = set()
    bancos_vistos: set[str] = set()

    excluidos_no_disp: list[tuple[str, int, int]] = []
    excluidos_sin_tasa: list[tuple[str, int, int]] = []
    supuestos: list[tuple[str, int, int]] = []
    total_filas = 0

    tramos_limites = {int(k): tuple(v) for k, v in config["tramos"].items()}

    for idx, fila in enumerate(filas, start=2):  # fila 2 = primera tras cabecera
        total_filas += 1
        contexto = f"Fila {idx} de '{os.path.basename(ruta_datos)}'"

        banco = str(fila["banco"]).strip()
        if not banco:
            raise DataLoaderError(f"{contexto}: 'banco' vacío.")
        if banco not in BANCOS_ESPERADOS:
            raise DataLoaderError(
                f"{contexto}: banco '{banco}' no pertenece al conjunto I "
                f"{sorted(BANCOS_ESPERADOS)}."
            )

        plazo = _a_entero(fila["plazo_dias"], "plazo_dias", contexto)
        if plazo not in PLAZOS_VALIDOS:
            raise DataLoaderError(
                f"{contexto}: plazo {plazo} no pertenece a J "
                f"{sorted(PLAZOS_VALIDOS)}."
            )

        tramo = _a_entero(fila["tramo"], "tramo", contexto)
        if tramo not in TRAMOS_VALIDOS:
            raise DataLoaderError(
                f"{contexto}: tramo {tramo} no pertenece a K "
                f"{sorted(TRAMOS_VALIDOS)}."
            )

        clave = (banco, plazo, tramo)
        if clave in vistos:
            raise DataLoaderError(
                f"{contexto}: combinación duplicada {clave}."
            )
        vistos.add(clave)
        bancos_vistos.add(banco)

        disponible = _a_bool(fila["disponible"])
        es_supuesto = _a_bool(fila["es_supuesto"])
        fuente = "" if _es_vacio(fila.get("fuente")) else str(fila["fuente"]).strip()

        # Marca de dato real vs supuesto (Requisito 1.5): se registra para el
        # reporte; una fuente vacía también se considera no verificada.
        if es_supuesto or not fuente:
            supuestos.append(clave)

        # Excluir combinaciones no disponibles (Requisito 1.6).
        if not disponible:
            excluidos_no_disp.append(clave)
            continue

        # Monto mínimo de apertura (obligatorio en filas disponibles).
        m_ij = _a_float(fila["min_apertura"], "min_apertura", contexto)
        if m_ij < 0:
            raise DataLoaderError(
                f"{contexto}: min_apertura={m_ij} no puede ser negativo."
            )

        # Tasa: puede estar vacía por el principio de cero invención de datos.
        # En ese caso se EXCLUYE del modelo (no se inventa tasa) y se reporta.
        if _es_vacio(fila["tasa_ea"]):
            excluidos_sin_tasa.append(clave)
            continue

        r_ijk = _a_float(fila["tasa_ea"], "tasa_ea", contexto)
        if not (TASA_MIN <= r_ijk < TASA_MAX):
            raise DataLoaderError(
                f"{contexto}: tasa_ea={r_ijk} fuera de rango razonable "
                f"[{TASA_MIN}, {TASA_MAX}) (use fracción E.A., p. ej. 0.11)."
            )

        # Coeficiente objetivo: factor de rendimiento efectivo del periodo.
        f_ijk = (1.0 + r_ijk) ** (plazo / 360.0) - 1.0

        r[clave] = r_ijk
        f[clave] = f_ijk
        m[clave] = m_ij
        disp[clave] = 1

    # --- Validar cobertura de bancos de la configuración --------------------
    bancos_cfg = set(config["concentracion_max"])
    if bancos_cfg != BANCOS_ESPERADOS:
        raise DataLoaderError(
            "La concentración de la configuración debe cubrir exactamente I "
            f"{sorted(BANCOS_ESPERADOS)}; se recibió {sorted(bancos_cfg)}."
        )

    combinaciones = sorted(r.keys())
    bancos = sorted({i for (i, _, _) in combinaciones})
    plazos = sorted({j for (_, j, _) in combinaciones})
    tramos = sorted({k for (_, _, k) in combinaciones})

    info = {
        "archivo_datos": ruta_datos,
        "total_filas": total_filas,
        "combinaciones_utilizables": len(combinaciones),
        "excluidos_no_disponibles": excluidos_no_disp,
        "excluidos_sin_tasa": excluidos_sin_tasa,
        "supuestos": supuestos,
        "todas_supuestas": len(supuestos) == total_filas,
    }

    return DatosCDT(
        bancos=bancos,
        plazos=plazos,
        tramos=tramos,
        r=r,
        f=f,
        m=m,
        disp=disp,
        p=dict(config["concentracion_max"]),
        A=float(config["A"]),
        tramos_limites=tramos_limites,
        liquidez=dict(config["liquidez"]),
        combinaciones=combinaciones,
        info=info,
    )


# ---------------------------------------------------------------------------
# Autocomprobación ligera (sin framework de pruebas): valida contra data/ real.
# El diseño indica que las pruebas formales se añaden solo si el usuario las
# solicita; esto es una verificación de humo ejecutable con:  python src/data_loader.py
# ---------------------------------------------------------------------------
def _resumen(datos: DatosCDT) -> None:
    info = datos.info
    print("== Carga de datos de CDT ==")
    print(f"Archivo            : {info['archivo_datos']}")
    print(f"Capital A          : {datos.A:,.0f}")
    print(f"Tramos (L_k, U_k)  : {datos.tramos_limites}")
    print(f"Concentración p_i  : {datos.p}")
    print(f"Liquidez           : {datos.liquidez}")
    print(f"Filas totales      : {info['total_filas']}")
    print(f"No disponibles     : {len(info['excluidos_no_disponibles'])}")
    print(f"Disponibles s/tasa : {len(info['excluidos_sin_tasa'])}")
    print(f"Marcadas supuesto  : {len(info['supuestos'])}")
    print(f"Utilizables (i,j,k): {info['combinaciones_utilizables']}")
    if datos.combinaciones:
        ejemplo = datos.combinaciones[0]
        print(
            f"Ejemplo {ejemplo}: r={datos.r[ejemplo]:.4f} "
            f"f={datos.f[ejemplo]:.6f} m={datos.m[ejemplo]:,.0f}"
        )
    else:
        print(
            "ADVERTENCIA: no hay combinaciones con tasa utilizable. "
            "El equipo debe fijar tasas supuestas explícitas en data/ "
            "(ver info['excluidos_sin_tasa'])."
        )


if __name__ == "__main__":
    try:
        datos = cargar_datos()
    except DataLoaderError as err:
        print(f"ERROR de carga: {err}")
        raise SystemExit(1)
    _resumen(datos)
