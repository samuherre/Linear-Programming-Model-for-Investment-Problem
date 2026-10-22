"""Construcción del modelo MILP de inversión en CDT — `model.py` (Tarea 4).

Este módulo arma el problema de Programación Lineal Entera Mixta (MILP) con
PuLP a partir de las estructuras validadas que entrega `data_loader.cargar_datos`
(un `DatosCDT`). Se construye de forma **incremental** a lo largo de las
subtareas del plan:

- Tarea 4.1 (este archivo): variables de decisión `x_ijk`, `z_ijk`, la holgura
  de no-inversión `s_0` y la función objetivo `max Σ f_ijk·x_ijk` (con la
  variante lineal `Σ r_ijk·x_ijk` expuesta para contraste didáctico).
- Tarea 4.2 (este archivo): restricciones de tramos escalonados vía
  `agregar_restricciones_tramos` (vínculo `x`–`z` `L_k·z ≤ x ≤ U_k·z` y
  "a lo sumo un tramo por `(i, j)`").
- Tarea 4.3 (este archivo): capital total con holgura, concentración por banco,
  mínimo de apertura y cotas de liquidez corto/largo plazo vía
  `agregar_restricciones_riesgo`.

Diseño para crecer sin fricción
--------------------------------
`construir_modelo` devuelve un `ModeloCDT` que agrupa el `LpProblem` junto con
los diccionarios de variables (`x`, `z`, la holgura `s_0`) y las expresiones de
objetivo ya calculadas (`objetivo_f`, `objetivo_r`). Las subtareas 4.2 y 4.3
reciben ese `ModeloCDT` y añaden restricciones al `modelo.problema` sin
reconstruir variables.

Referencias de requisitos
--------------------------
- Requisito 2.1: variables binarias `z_ijk ∈ {0,1}` para activar el tramo.
- Requisito 2.2: `z_ijk = 0 ⇒ x_ijk = 0` (cota superior `x ≤ U_k·z`).
- Requisito 2.3: `z_ijk = 1 ⇒ L_k ≤ x_ijk ≤ U_k` (vínculo `x`–`z`).
- Requisito 2.4: a lo sumo un tramo por `(i, j)` (`Σ_k z_ijk ≤ 1`).
- Requisito 2.5: coeficiente objetivo `f_ijk = (1 + r_ijk)^(j/360) − 1`.
- Requisito 2.6: variante didáctica del objetivo lineal directo `Σ r_ijk·x_ijk`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import pulp

from data_loader import DatosCDT


# ---------------------------------------------------------------------------
# Resultado de la construcción del modelo
# ---------------------------------------------------------------------------
@dataclass
class ModeloCDT:
    """Agrupa el problema PuLP y sus variables para inspección y crecimiento.

    Atributos
    ---------
    problema:
        El `LpProblem` (sentido maximizar). Las subtareas 4.2/4.3 añaden
        restricciones directamente sobre este objeto.
    x:
        Variables continuas de monto `x_ijk ≥ 0`, indexadas por `(i, j, k)`.
    z:
        Variables binarias de activación de tramo `z_ijk ∈ {0,1}`, indexadas
        por `(i, j, k)`. Solo existen para combinaciones disponibles.
    s0:
        Holgura de no-inversión `s_0 ≥ 0` (capital que queda sin colocar).
    objetivo_f:
        Expresión lineal del objetivo de producción `Σ f_ijk·x_ijk`. Es la que
        se fija como objetivo del problema (Requisito 2.5).
    objetivo_r:
        Expresión lineal de la variante didáctica `Σ r_ijk·x_ijk`, expuesta
        para contraste pero NO fijada como objetivo (Requisito 2.6).
    datos:
        Referencia al `DatosCDT` de origen, para que las subtareas siguientes
        consulten parámetros (`tramos_limites`, `m`, `p`, `A`, `liquidez`).
    """

    problema: pulp.LpProblem
    x: dict[tuple[str, int, int], pulp.LpVariable]
    z: dict[tuple[str, int, int], pulp.LpVariable]
    s0: pulp.LpVariable
    objetivo_f: pulp.LpAffineExpression
    objetivo_r: pulp.LpAffineExpression
    datos: DatosCDT = field(repr=False)


# ---------------------------------------------------------------------------
# Utilidad de nombres de variable seguros para PuLP
# ---------------------------------------------------------------------------
def _nombre_var(prefijo: str, clave: tuple[str, int, int]) -> str:
    """Genera un nombre de variable PuLP válido a partir de la clave `(i,j,k)`.

    PuLP/los solvers LP rechazan ciertos caracteres (espacios, etc.) en los
    nombres. Se sanea el nombre del banco para obtener identificadores estables
    del tipo `x_Banco_de_Bogota_360_2`.
    """
    banco, plazo, tramo = clave
    banco_seguro = (
        banco.replace(" ", "_")
        .replace("-", "_")
        .replace("(", "")
        .replace(")", "")
    )
    return f"{prefijo}_{banco_seguro}_{plazo}_{tramo}"


# ---------------------------------------------------------------------------
# Construcción del modelo (Tarea 4.1: variables + objetivo)
# ---------------------------------------------------------------------------
def construir_modelo(datos: DatosCDT, nombre: str = "CDT_Inversion") -> ModeloCDT:
    """Crea el `LpProblem`, las variables de decisión y la función objetivo.

    Esta función cubre la Tarea 4.1. NO añade todavía las restricciones de
    tramos (4.2) ni las de capital/concentración/mínimos/liquidez (4.3); esas
    se incorporan sobre el `ModeloCDT` devuelto en las subtareas siguientes.

    Parámetros
    ----------
    datos:
        Estructuras validadas de `cargar_datos`. Solo contienen combinaciones
        disponibles y con tasa utilizable (`datos.combinaciones`).
    nombre:
        Nombre del `LpProblem`.

    Retorna
    -------
    ModeloCDT con el problema (sentido maximizar), los diccionarios `x` y `z`,
    la holgura `s_0` y las expresiones de objetivo `objetivo_f`/`objetivo_r`.
    """
    problema = pulp.LpProblem(nombre, sense=pulp.LpMaximize)

    # --- Variables de decisión (solo combinaciones disponibles) ------------
    # x_ijk ≥ 0 (continua): monto asignado a (i, j, k).
    x: dict[tuple[str, int, int], pulp.LpVariable] = {
        clave: pulp.LpVariable(_nombre_var("x", clave), lowBound=0, cat="Continuous")
        for clave in datos.combinaciones
    }

    # z_ijk ∈ {0,1} (binaria): activa el tramo k del producto (i, j) (Req. 2.1).
    z: dict[tuple[str, int, int], pulp.LpVariable] = {
        clave: pulp.LpVariable(_nombre_var("z", clave), cat="Binary")
        for clave in datos.combinaciones
    }

    # s_0 ≥ 0: holgura de no-inversión (capital sin colocar). Permite modelar la
    # restricción de capital como igualdad sin arriesgar infactibilidad (4.3).
    s0 = pulp.LpVariable("s_0", lowBound=0, cat="Continuous")

    # --- Función objetivo ---------------------------------------------------
    # Producción (Req. 2.5): max Σ f_ijk·x_ijk, con f_ijk el factor de
    # rendimiento efectivo del periodo (ya precalculado en data_loader).
    objetivo_f = pulp.lpSum(datos.f[clave] * x[clave] for clave in datos.combinaciones)

    # Variante didáctica (Req. 2.6): Σ r_ijk·x_ijk. Se expone para contraste en
    # la sección de metodología/resultados, pero NO se fija como objetivo.
    objetivo_r = pulp.lpSum(datos.r[clave] * x[clave] for clave in datos.combinaciones)

    # El objetivo de producción es el que optimiza el solver.
    problema += objetivo_f, "Objetivo_rendimiento_efectivo_f"

    return ModeloCDT(
        problema=problema,
        x=x,
        z=z,
        s0=s0,
        objetivo_f=objetivo_f,
        objetivo_r=objetivo_r,
        datos=datos,
    )


# ---------------------------------------------------------------------------
# Restricciones de tramos escalonados (Tarea 4.2)
# ---------------------------------------------------------------------------
def agregar_restricciones_tramos(modelo: ModeloCDT) -> ModeloCDT:
    """Añade las restricciones de tramos escalonados al `modelo.problema`.

    Esta función cubre la Tarea 4.2 y mutila (muta) el `LpProblem` que vive en
    `modelo.problema`, añadiendo dos familias de restricciones. Devuelve el
    mismo `ModeloCDT` para permitir encadenar llamadas (la Tarea 4.3 sigue este
    mismo patrón: recibe el modelo y agrega sus restricciones).

    Familia 1 — Vínculo `x`–`z` (Restricción 3 del diseño; Req. 2.2 y 2.3)
    ----------------------------------------------------------------------
    Para cada combinación disponible `(i, j, k)` se impone:

        L_k · z_ijk ≤ x_ijk ≤ U_k · z_ijk

    Se modela como dos desigualdades lineales:
        - Cota inferior: `x_ijk ≥ L_k · z_ijk`  ⟺  `x_ijk − L_k·z_ijk ≥ 0`.
        - Cota superior: `x_ijk ≤ U_k · z_ijk`  ⟺  `x_ijk − U_k·z_ijk ≤ 0`.

    Efecto lógico:
        - Si `z_ijk = 0` ⇒ `0 ≤ x_ijk ≤ 0` ⇒ `x_ijk = 0` (Req. 2.2: tramo
          inactivo obliga a monto cero).
        - Si `z_ijk = 1` ⇒ `L_k ≤ x_ijk ≤ U_k` (Req. 2.3: el monto respeta las
          cotas inferior y superior del tramo activado).

    Tramo 3 con cota superior infinita (`U_3 = None`)
    -------------------------------------------------
    El tramo 3 es `(> 50.000.000)` sin cota superior (`U_k = None` en
    `datos.tramos_limites`). PuLP no admite un coeficiente `None`, así que se
    sustituye por un **big-M seguro**: el capital total `A`. La elección es
    rigurosa, no arbitraria: por la restricción de capital `Σ x_ijk + s_0 = A`
    con `s_0 ≥ 0` (Tarea 4.3), ningún `x_ijk` puede exceder `A`. Usar `U = A`
    como cota superior cuando `z_ijk = 1` por tanto **no recorta** ninguna
    solución factible (no es una cota activa espuria), pero sí preserva el
    acoplamiento `z_ijk = 0 ⇒ x_ijk = 0`. Es el big-M más ajustado disponible
    sin introducir parámetros inventados.

    Familia 2 — A lo sumo un tramo por `(i, j)` (Restricción 5; Req. 2.4)
    --------------------------------------------------------------------
    Para cada producto `(i, j)` presente en las combinaciones:

        Σ_k z_ijk ≤ 1

    Evita activar dos tramos del mismo producto a la vez (no contar un mismo
    monto en dos tramos solapados).

    Parámetros
    ----------
    modelo:
        El `ModeloCDT` devuelto por `construir_modelo` (Tarea 4.1).

    Retorna
    -------
    El mismo `ModeloCDT`, ya con las restricciones de tramos incorporadas.
    """
    datos = modelo.datos

    # --- Familia 1: vínculo x–z (L_k·z ≤ x ≤ U_k·z) ------------------------
    for clave in datos.combinaciones:
        _banco, _plazo, tramo = clave
        limite = datos.tramos_limites.get(tramo)
        if limite is None:
            # Tramo sin límites definidos en configuración: incoherencia de
            # datos que el loader debería haber detectado; se falla claro.
            raise ValueError(
                f"No hay límites de tramo definidos para el tramo {tramo} "
                f"(combinación {clave})."
            )
        limite_inferior, limite_superior = limite

        # Cota superior: si U_k es None (tramo 3, infinito) se usa big-M = A.
        cota_superior = datos.A if limite_superior is None else limite_superior

        # x_ijk ≥ L_k · z_ijk  (si z=0 ⇒ x≥0; si z=1 ⇒ x≥L_k)  [Req. 2.3]
        modelo.problema += (
            modelo.x[clave] >= limite_inferior * modelo.z[clave],
            _nombre_var("tramo_inf", clave),
        )
        # x_ijk ≤ U_k · z_ijk  (si z=0 ⇒ x≤0 ⇒ x=0; si z=1 ⇒ x≤U_k) [Req. 2.2/2.3]
        modelo.problema += (
            modelo.x[clave] <= cota_superior * modelo.z[clave],
            _nombre_var("tramo_sup", clave),
        )

    # --- Familia 2: a lo sumo un tramo por (i, j) (Σ_k z_ijk ≤ 1) [Req. 2.4] -
    # Se agrupan las claves por producto (banco, plazo), preservando el orden
    # de aparición para nombres de restricción estables.
    productos: dict[tuple[str, int], list[tuple[str, int, int]]] = {}
    for clave in datos.combinaciones:
        banco, plazo, _tramo = clave
        productos.setdefault((banco, plazo), []).append(clave)

    for (banco, plazo), claves in productos.items():
        banco_seguro = (
            banco.replace(" ", "_")
            .replace("-", "_")
            .replace("(", "")
            .replace(")", "")
        )
        modelo.problema += (
            pulp.lpSum(modelo.z[clave] for clave in claves) <= 1,
            f"un_tramo_{banco_seguro}_{plazo}",
        )

    return modelo


# ---------------------------------------------------------------------------
# Restricciones multibanco, riesgo y liquidez (Tarea 4.3)
# ---------------------------------------------------------------------------
def agregar_restricciones_riesgo(modelo: ModeloCDT) -> ModeloCDT:
    """Añade las restricciones de capital, concentración, mínimos y liquidez.

    Esta función cubre la Tarea 4.3 y, siguiendo el mismo patrón que
    `agregar_restricciones_tramos` (4.2), muta el `LpProblem` de
    `modelo.problema` y devuelve el mismo `ModeloCDT` para encadenar llamadas.
    Implementa las restricciones 1, 2, 4 y 6 del diseño.

    Familia 1 — Inversión total del capital (Restricción 1; Req. 3.1)
    -----------------------------------------------------------------
    Igualdad con holgura de no-inversión:

        Σ_i Σ_j Σ_k x_ijk + s_0 = A,   con s_0 ≥ 0

    La igualdad modela la intención real de colocar todo el capital `A` y da al
    precio sombra `λ` su interpretación económica más rica (retorno marginal de
    un peso adicional de capital). La holgura `s_0` (ya ≥ 0 por construcción en
    4.1) garantiza factibilidad: si los mínimos de apertura y la concentración
    impiden sumar exacto `A`, `s_0` absorbe el capital no colocado (Req. 3.2,
    que el reporte destacará cuando `s_0 > 0`). Esta igualdad reemplaza la cota
    temporal de capital que el humo de 4.2 usaba para acotar el problema.

    Familia 2 — Concentración máxima por banco (Restricción 2; Req. 3.3)
    -------------------------------------------------------------------
    Diversificación: para cada banco `i` presente en las combinaciones,

        Σ_j Σ_k x_ijk ≤ p_i · A

    donde `p_i = datos.p[i]` es la fracción máxima de concentración del banco.

    Familia 3 — Monto mínimo de apertura (Restricción 4; Req. 3.4)
    -------------------------------------------------------------
    Para cada combinación `(i, j, k)`:

        x_ijk ≥ m_ij · z_ijk

    con `m_ij = datos.m[(i, j, k)]` (el loader indexa el mínimo por `(i,j,k)`).
    Si el tramo está activo (`z_ijk = 1`) el monto debe alcanzar el mínimo de
    apertura exigido por la entidad; si `z_ijk = 0` el término derecho es 0 y la
    restricción no obliga nada (coherente con `x_ijk = 0` de la Tarea 4.2).

    No negatividad (Req. 3.5)
    -------------------------
    No se añade aquí: `x_ijk ≥ 0` y `s_0 ≥ 0` ya están impuestas como cotas de
    las variables (`lowBound=0`) en `construir_modelo` (Tarea 4.1).

    Familia 4 — Liquidez corto/largo plazo (Restricción 6; Req. 3.7)
    ----------------------------------------------------------------
    Partición por plazo: `J_corto = {j ≤ 180}`, `J_largo = {j > 180}`.

        L_corto · A ≤ Σ_{j≤180} x_ijk ≤ U_corto · A
        L_largo · A ≤ Σ_{j>180} x_ijk ≤ U_largo · A

    Cada cota (`L_corto`, `U_corto`, `L_largo`, `U_largo`) es **política de
    tesorería parametrizada**: se añade SOLO si está definida (no es `None`).
    Una cota `None` queda desactivada, respetando el principio de cero
    invención de datos. Con la configuración actual las cuatro son `None`, por
    lo que NINGUNA restricción de liquidez se agrega.

    Parámetros
    ----------
    modelo:
        El `ModeloCDT` devuelto por `construir_modelo`, idealmente ya con las
        restricciones de tramos (4.2) incorporadas.

    Retorna
    -------
    El mismo `ModeloCDT`, ya con las restricciones de riesgo incorporadas.
    """
    datos = modelo.datos

    # --- Familia 1: capital total como igualdad con holgura (Req. 3.1) ------
    # Σ x_ijk + s_0 = A. La holgura s_0 (≥ 0) absorbe el capital no colocado.
    modelo.problema += (
        pulp.lpSum(modelo.x[clave] for clave in datos.combinaciones) + modelo.s0
        == datos.A,
        "capital_total",
    )

    # --- Familia 2: concentración máxima por banco (Req. 3.3) ---------------
    # Σ_{j,k} x_ijk ≤ p_i · A para cada banco i presente en las combinaciones.
    claves_por_banco: dict[str, list[tuple[str, int, int]]] = {}
    for clave in datos.combinaciones:
        banco, _plazo, _tramo = clave
        claves_por_banco.setdefault(banco, []).append(clave)

    for banco, claves in claves_por_banco.items():
        p_i = datos.p.get(banco)
        if p_i is None:
            # La configuración debería cubrir todos los bancos (lo valida el
            # loader); si falta, se falla claro en vez de ignorar el riesgo.
            raise ValueError(
                f"No hay concentración p_i definida para el banco '{banco}'."
            )
        banco_seguro = (
            banco.replace(" ", "_")
            .replace("-", "_")
            .replace("(", "")
            .replace(")", "")
        )
        modelo.problema += (
            pulp.lpSum(modelo.x[clave] for clave in claves) <= p_i * datos.A,
            f"concentracion_{banco_seguro}",
        )

    # --- Familia 3: monto mínimo de apertura (Req. 3.4) ---------------------
    # x_ijk ≥ m_ij · z_ijk. El mínimo se indexa por (i, j, k) en el loader.
    for clave in datos.combinaciones:
        m_ij = datos.m[clave]
        modelo.problema += (
            modelo.x[clave] >= m_ij * modelo.z[clave],
            _nombre_var("min_apertura", clave),
        )

    # --- Familia 4: liquidez corto/largo plazo (Req. 3.7) -------------------
    # Cada cota se activa SOLO si está definida (None = desactivada).
    liq = datos.liquidez
    corto = [c for c in datos.combinaciones if c[1] <= 180]
    largo = [c for c in datos.combinaciones if c[1] > 180]
    suma_corto = pulp.lpSum(modelo.x[c] for c in corto)
    suma_largo = pulp.lpSum(modelo.x[c] for c in largo)

    # (L_horizonte, U_horizonte, suma, etiqueta) para iterar sin repetir código.
    for l_clave, u_clave, suma, etiqueta in (
        ("L_corto", "U_corto", suma_corto, "corto"),
        ("L_largo", "U_largo", suma_largo, "largo"),
    ):
        l_val = liq.get(l_clave)
        u_val = liq.get(u_clave)
        # Cota inferior: L · A ≤ Σ x   (solo si L está definida).
        if l_val is not None:
            modelo.problema += (
                suma >= l_val * datos.A,
                f"liquidez_{etiqueta}_inf",
            )
        # Cota superior: Σ x ≤ U · A   (solo si U está definida).
        if u_val is not None:
            modelo.problema += (
                suma <= u_val * datos.A,
                f"liquidez_{etiqueta}_sup",
            )

    return modelo


# ---------------------------------------------------------------------------
# Fixture sintético mínimo (para humo/verificación sin depender de data/ real)
# ---------------------------------------------------------------------------
def _datos_sinteticos() -> DatosCDT:
    """Construye un `DatosCDT` pequeño de prueba (2 bancos × 1 plazo × 2 tramos).

    La matriz real deja las tasas vacías por el principio de cero invención de
    datos (ver `data_loader`), por lo que `cargar_datos` puede no devolver
    ninguna combinación utilizable. Este fixture permite verificar que la
    construcción de variables y objetivo funciona, sin inventar datos del
    problema real: son valores claramente ficticios para humo de software.
    """
    combinaciones = [
        ("Bancolombia", 360, 1),
        ("Bancolombia", 360, 2),
        ("Bancolombia", 360, 3),  # tramo 3 (U=∞) para ejercitar el big-M=A
        ("Davivienda", 360, 1),
    ]
    r = {
        ("Bancolombia", 360, 1): 0.10,
        ("Bancolombia", 360, 2): 0.11,
        ("Bancolombia", 360, 3): 0.12,
        ("Davivienda", 360, 1): 0.095,
    }
    # f_ijk = (1 + r)^(360/360) − 1 = r para plazo 360; válido como humo.
    f = {clave: (1.0 + tasa) ** (360 / 360.0) - 1.0 for clave, tasa in r.items()}
    m = {clave: 500_000.0 for clave in combinaciones}
    disp = {clave: 1 for clave in combinaciones}
    return DatosCDT(
        bancos=["Bancolombia", "Davivienda"],
        plazos=[360],
        tramos=[1, 2, 3],
        r=r,
        f=f,
        m=m,
        disp=disp,
        p={"Bancolombia": 0.5, "Davivienda": 0.5},
        A=100_000_000.0,
        tramos_limites={1: (50_000.0, 10_000_000.0), 2: (10_000_001.0, 50_000_000.0), 3: (50_000_001.0, None)},
        liquidez={"L_corto": None, "U_corto": None, "L_largo": None, "U_largo": None},
        combinaciones=combinaciones,
        info={"fixture": "sintetico"},
    )


def _resumen(modelo: ModeloCDT) -> None:
    """Imprime un resumen legible del modelo construido (humo)."""
    print("== Construcción del modelo MILP de CDT (Tareas 4.1 + 4.2) ==")
    print(f"Nombre problema    : {modelo.problema.name}")
    print(f"Sentido            : {pulp.LpSenses[modelo.problema.sense]}")
    print(f"Variables x_ijk    : {len(modelo.x)}")
    print(f"Variables z_ijk    : {len(modelo.z)}")
    print(f"Holgura s_0        : {modelo.s0.name} (lowBound={modelo.s0.lowBound})")
    print(f"Objetivo (f_ijk)   : {modelo.problema.objective}")
    print(f"Variante (r_ijk)   : {modelo.objetivo_r}")
    # Tipos de variable (para confirmar binaria vs continua):
    ejemplo = modelo.datos.combinaciones[0]
    print(
        f"Ejemplo {ejemplo}: "
        f"x.cat={modelo.x[ejemplo].cat}, z.cat={modelo.z[ejemplo].cat}"
    )


def _verificar_restricciones_tramos(modelo: ModeloCDT) -> None:
    """Verifica que las restricciones de tramos (Tarea 4.2) se agregaron bien.

    Comprueba el conteo esperado y muestra ejemplos de cada familia, incluido
    el uso del big-M `A` para el tramo 3 (cota superior infinita).
    """
    datos = modelo.datos
    combinaciones = datos.combinaciones

    # Productos (i, j) distintos presentes en las combinaciones.
    productos = {(banco, plazo) for banco, plazo, _tramo in combinaciones}

    restricciones = modelo.problema.constraints
    inf = {n: c for n, c in restricciones.items() if n.startswith("tramo_inf_")}
    sup = {n: c for n, c in restricciones.items() if n.startswith("tramo_sup_")}
    un_tramo = {n: c for n, c in restricciones.items() if n.startswith("un_tramo_")}

    # Esperado: 1 cota inferior + 1 cota superior por combinación; 1 "un tramo"
    # por producto (i, j).
    esperado_vinculo = len(combinaciones)
    esperado_un_tramo = len(productos)

    print("\n== Verificación restricciones de tramos (Tarea 4.2) ==")
    print(f"Combinaciones (i,j,k)       : {len(combinaciones)}")
    print(f"Productos (i,j)             : {len(productos)}")
    print(
        f"Cotas inferiores (x≥L·z)    : {len(inf)} "
        f"(esperado {esperado_vinculo}) -> {'OK' if len(inf) == esperado_vinculo else 'FALLO'}"
    )
    print(
        f"Cotas superiores (x≤U·z)    : {len(sup)} "
        f"(esperado {esperado_vinculo}) -> {'OK' if len(sup) == esperado_vinculo else 'FALLO'}"
    )
    print(
        f"A lo sumo un tramo (Σz≤1)   : {len(un_tramo)} "
        f"(esperado {esperado_un_tramo}) -> {'OK' if len(un_tramo) == esperado_un_tramo else 'FALLO'}"
    )

    assert len(inf) == esperado_vinculo, "Faltan cotas inferiores de tramo."
    assert len(sup) == esperado_vinculo, "Faltan cotas superiores de tramo."
    assert len(un_tramo) == esperado_un_tramo, "Faltan restricciones de un-tramo."

    # Ejemplos legibles de cada familia.
    ejemplo = combinaciones[0]
    print("\nEjemplos de restricciones generadas:")
    print(f"  inferior  {_nombre_var('tramo_inf', ejemplo)}: "
          f"{restricciones[_nombre_var('tramo_inf', ejemplo)]}")
    print(f"  superior  {_nombre_var('tramo_sup', ejemplo)}: "
          f"{restricciones[_nombre_var('tramo_sup', ejemplo)]}")
    nombre_un = next(iter(un_tramo))
    print(f"  un-tramo  {nombre_un}: {restricciones[nombre_un]}")

    # Confirmar el big-M = A para el tramo 3 (U_3 = None), si existe alguna
    # combinación de tramo 3 en las combinaciones.
    claves_tramo3 = [c for c in combinaciones if c[2] == 3]
    if claves_tramo3:
        clave3 = claves_tramo3[0]
        print(
            f"\nTramo 3 (U=∞) usa big-M = A = {datos.A:,.0f} en "
            f"{_nombre_var('tramo_sup', clave3)}:"
        )
        print(f"  {restricciones[_nombre_var('tramo_sup', clave3)]}")
    else:
        print("\n(Fixture sin tramo 3; big-M=A no ejercitado aquí.)")

    print("\nVerificación OK: restricciones de tramos añadidas correctamente.")


def _verificar_restricciones_riesgo(modelo: ModeloCDT) -> None:
    """Verifica que las restricciones de riesgo (Tarea 4.3) se agregaron bien.

    Comprueba el conteo esperado de cada familia (capital, concentración,
    mínimos de apertura y liquidez) y que las cotas de liquidez `None` NO
    generan restricciones.
    """
    datos = modelo.datos
    combinaciones = datos.combinaciones
    bancos = {banco for banco, _plazo, _tramo in combinaciones}

    restricciones = modelo.problema.constraints
    capital = {n: c for n, c in restricciones.items() if n == "capital_total"}
    concentracion = {n: c for n, c in restricciones.items() if n.startswith("concentracion_")}
    minimos = {n: c for n, c in restricciones.items() if n.startswith("min_apertura_")}
    liquidez = {n: c for n, c in restricciones.items() if n.startswith("liquidez_")}

    # Cotas de liquidez activas esperadas (solo las definidas, None = off).
    liq = datos.liquidez
    cotas_definidas = sum(
        1 for clave in ("L_corto", "U_corto", "L_largo", "U_largo")
        if liq.get(clave) is not None
    )

    print("\n== Verificación restricciones de riesgo (Tarea 4.3) ==")
    print(f"Capital total (Σx+s_0=A)    : {len(capital)} (esperado 1) "
          f"-> {'OK' if len(capital) == 1 else 'FALLO'}")
    print(f"Concentración por banco     : {len(concentracion)} (esperado {len(bancos)}) "
          f"-> {'OK' if len(concentracion) == len(bancos) else 'FALLO'}")
    print(f"Mínimo de apertura (x≥m·z)  : {len(minimos)} (esperado {len(combinaciones)}) "
          f"-> {'OK' if len(minimos) == len(combinaciones) else 'FALLO'}")
    print(f"Liquidez (cotas definidas)  : {len(liquidez)} (esperado {cotas_definidas}) "
          f"-> {'OK' if len(liquidez) == cotas_definidas else 'FALLO'}")

    assert len(capital) == 1, "Falta la igualdad de capital total."
    assert len(concentracion) == len(bancos), "Faltan restricciones de concentración."
    assert len(minimos) == len(combinaciones), "Faltan restricciones de mínimo de apertura."
    assert len(liquidez) == cotas_definidas, (
        "El número de restricciones de liquidez no coincide con las cotas definidas "
        "(las cotas None no deben generar restricción)."
    )

    print("\nEjemplos de restricciones generadas:")
    print(f"  capital   capital_total: {restricciones['capital_total']}")
    nombre_conc = next(iter(concentracion))
    print(f"  concentr. {nombre_conc}: {restricciones[nombre_conc]}")
    ejemplo = combinaciones[0]
    print(f"  mínimo    {_nombre_var('min_apertura', ejemplo)}: "
          f"{restricciones[_nombre_var('min_apertura', ejemplo)]}")

    print("\nVerificación OK: restricciones de riesgo añadidas correctamente.")


def _verificar_comportamiento_solver(modelo: ModeloCDT) -> None:
    """Resuelve el MILP completo para confirmar el comportamiento del modelo.

    Con todas las restricciones ya incorporadas (tramos 4.2 + riesgo 4.3), el
    problema está acotado por la igualdad de capital real `Σ x + s_0 = A`; ya no
    hace falta la cota temporal de humo que usaba la Tarea 4.2. Sobre la
    solución óptima comprueba:

      (a) a lo sumo un tramo por producto `(i, j)` (Req. 2.4);
      (b) `z=0 ⇒ x=0` (Req. 2.2) y `z=1 ⇒ L_k ≤ x ≤ U_k` (Req. 2.3);
      (c) la igualdad de capital `Σ x + s_0 = A` se cumple (Req. 3.1);
      (d) la concentración por banco `Σ_{j,k} x_ijk ≤ p_i·A` se respeta (Req. 3.3);
      (e) el mínimo de apertura `x_ijk ≥ m_ij` cuando `z=1` (Req. 3.4).
    """
    datos = modelo.datos
    modelo.problema.solve(pulp.PULP_CBC_CMD(msg=False))

    print("\n== Comprobación de comportamiento del solver (humo) ==")
    print(f"Estado: {pulp.LpStatus[modelo.problema.status]}")

    tol = 1e-4  # tolerancia absoluta para comparaciones de punto flotante

    # (a) A lo sumo un tramo por (i, j).
    productos: dict[tuple[str, int], int] = {}
    for (banco, plazo, _tramo) in datos.combinaciones:
        productos[(banco, plazo)] = 0
    for clave in datos.combinaciones:
        banco, plazo, _tramo = clave
        if (modelo.z[clave].value() or 0) > 0.5:
            productos[(banco, plazo)] += 1
    assert all(v <= 1 for v in productos.values()), "Se activó más de un tramo."

    # (b) consistencia x–z y (e) mínimo de apertura sobre cada combinación.
    for clave in datos.combinaciones:
        xv = modelo.x[clave].value() or 0.0
        zv = modelo.z[clave].value() or 0.0
        _b, _p, tramo = clave
        li, ls = datos.tramos_limites[tramo]
        ls = datos.A if ls is None else ls
        if zv < 0.5:
            assert abs(xv) <= tol, f"z=0 pero x≠0 en {clave}: x={xv}"
        else:
            assert xv >= li - tol, f"z=1 y x<L_k en {clave}: x={xv} < {li}"
            assert xv <= ls + tol, f"z=1 y x>U_k en {clave}: x={xv} > {ls}"
            # (e) mínimo de apertura: x ≥ m_ij cuando el tramo está activo.
            assert xv >= datos.m[clave] - tol, (
                f"z=1 pero x<m_ij en {clave}: x={xv} < m={datos.m[clave]}"
            )

    # (c) igualdad de capital: Σ x + s_0 = A.
    suma_x = sum(modelo.x[c].value() or 0.0 for c in datos.combinaciones)
    s0_val = modelo.s0.value() or 0.0
    assert abs((suma_x + s0_val) - datos.A) <= tol * max(1.0, datos.A), (
        f"Capital no balanceado: Σx+s_0={suma_x + s0_val:,.2f} ≠ A={datos.A:,.2f}"
    )

    # (d) concentración por banco: Σ_{j,k} x_ijk ≤ p_i·A.
    por_banco: dict[str, float] = {}
    for clave in datos.combinaciones:
        banco = clave[0]
        por_banco[banco] = por_banco.get(banco, 0.0) + (modelo.x[clave].value() or 0.0)
    for banco, total in por_banco.items():
        limite = datos.p[banco] * datos.A
        assert total <= limite + tol * max(1.0, datos.A), (
            f"Concentración excedida en '{banco}': {total:,.2f} > p·A={limite:,.2f}"
        )

    activas = [
        (c, round(modelo.x[c].value() or 0.0, 2))
        for c in datos.combinaciones
        if (modelo.z[c].value() or 0) > 0.5
    ]
    print(f"Valor objetivo       : {pulp.value(modelo.problema.objective):,.4f}")
    print(f"Capital colocado Σx  : {suma_x:,.2f}")
    print(f"Holgura s_0          : {s0_val:,.2f}")
    print(f"Σx + s_0             : {suma_x + s0_val:,.2f} (A = {datos.A:,.2f})")
    print(f"Concentración/banco  : "
          f"{ {b: round(v, 2) for b, v in por_banco.items()} }")
    print(f"Tramos activos (z=1) : {activas}")
    print("Comprobación OK: capital, concentración, mínimos y vínculo x–z se respetan.")


if __name__ == "__main__":
    import sys

    # La consola por defecto de Windows (cp1252) no puede codificar los
    # símbolos del resumen (Σ, ·, ≤). Forzar UTF-8 en stdout evita un
    # UnicodeEncodeError al ejecutar la autocomprobación en PowerShell.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    modelo = construir_modelo(_datos_sinteticos())
    agregar_restricciones_tramos(modelo)
    agregar_restricciones_riesgo(modelo)
    _resumen(modelo)
    _verificar_restricciones_tramos(modelo)
    _verificar_restricciones_riesgo(modelo)
    _verificar_comportamiento_solver(modelo)
