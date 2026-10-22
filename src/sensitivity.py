"""Dualidad y análisis de sensibilidad del modelo de CDT — `sensitivity.py`.

Este módulo implementa la **Estrategia MILP + LP** descrita en `design.md`:

    ┌─────────────────────┐     fija z* = z*_ijk    ┌──────────────────────┐
    │  MILP (asignación)   │ ──────────────────────► │  LP restringido       │
    │  x_ijk, z_ijk        │                         │  solo x_ijk activas   │
    │  → solución óptima    │                         │  → dual / sensibilidad │
    └─────────────────────┘                         └──────────────────────┘

¿Por qué un LP restringido y no el MILP? (Requisito 4.7)
--------------------------------------------------------
En un MILP las variables binarias rompen la convexidad, por lo que los
**precios sombra y los rangos de sensibilidad del dual NO están formalmente
definidos** sobre el MILP original. La teoría de dualidad fuerte solo es válida
para un LP. La salida académicamente correcta —y la que exige el curso— es:

1. Resolver el MILP (Tarea 5, `solver.resolver`) y obtener `z* = z*_ijk`.
2. **Fijar** las binarias en su valor óptimo `z*` y quedarse SOLO con las
   `x_ijk` activas (aquellas con `z* = 1`) más la holgura `s_0`.
3. Reconstruir sobre ese subconjunto un `LpProblem` **puramente lineal** (sin
   binarias): sobre él la teoría dual es válida y la interpretación económica
   de los precios sombra es rigurosa.

Toda la sensibilidad y los precios sombra que calculen las Tareas 6.2 y 6.3 se
refieren a ESTE LP restringido, NO al MILP. El informe (Tarea 7) debe advertirlo
explícitamente (Requisito 4.7).

Alcance de este archivo (Tarea 6.1)
-----------------------------------
`construir_lp_restringido`: construye el LP restringido (Requisitos 4.1 y 4.7).
NO extrae todavía valores duales/precios sombra (Tarea 6.2) ni verifica holgura
complementaria o calcula rangos de sensibilidad (Tarea 6.3). Esas etapas
consumirán el `LPRestringido` que aquí se devuelve (con sus variables `x`/`s_0`
y sus restricciones con nombre).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import pulp

from data_loader import DatosCDT
from solver import ResultadoCDT


# Umbral para decidir que una binaria está "activa" (z* = 1). El solver puede
# devolver 0.9999…; coherente con `_TOL_BINARIA` de solver.py.
_TOL_BINARIA = 0.5


# ---------------------------------------------------------------------------
# Estructura de resultado: el LP restringido y sus asideros
# ---------------------------------------------------------------------------
@dataclass
class LPRestringido:
    """LP lineal que resulta de fijar `z = z*` sobre el MILP resuelto.

    Esta estructura es el **contrato** que consumen las Tareas 6.2 (dual /
    precios sombra) y 6.3 (holgura complementaria y rangos). Conserva asideros
    directos a las variables y a las restricciones con nombre para poder leer
    `constraint.pi` y `constraint.slack` tras resolver el LP.

    ADVERTENCIA (Requisito 4.7): este LP es la base para dualidad y
    sensibilidad; NO es el MILP original. Cualquier precio sombra o rango
    derivado de él aplica al LP restringido con las binarias fijadas en `z*`.

    Atributos
    ---------
    problema:
        El `LpProblem` lineal (sentido maximizar), sin variables binarias.
    x:
        `{(i, j, k): LpVariable}` SOLO para las combinaciones activas
        (`z* = 1`). Son continuas con las cotas del tramo activado.
    s0:
        Holgura de no-inversión `s_0 ≥ 0` (capital sin colocar), como en el MILP.
    z_estrella:
        `{(i, j, k): 0/1}` de la solución MILP que se fijó. Se conserva para
        trazabilidad e interpretación.
    activas:
        Lista ordenada de las claves `(i, j, k)` activas incluidas en el LP.
    objetivo_f:
        Expresión del objetivo de producción `Σ f_ijk·x_ijk` restringido a las
        activas (idéntico coeficiente `f_ijk` que el MILP).
    restr_capital:
        Restricción con nombre de capital `Σ x + s_0 = A` (igualdad). Su `pi`
        dará el precio sombra `λ` del capital (Tarea 6.2).
    restr_concentracion:
        `{banco: restricción}` de concentración `Σ_{j,k} x_ijk ≤ p_i·A`. Sus
        `pi` darán los `μ_i` (Tarea 6.2).
    restr_liquidez:
        `{etiqueta: restricción}` de liquidez activa (solo las cotas definidas).
        Vacío si la configuración deja las cuatro cotas en `None`.
    datos:
        Referencia al `DatosCDT` de origen (parámetros para 6.2/6.3).
    """

    problema: pulp.LpProblem
    x: dict[tuple[str, int, int], pulp.LpVariable]
    s0: pulp.LpVariable
    z_estrella: dict[tuple[str, int, int], int]
    activas: list[tuple[str, int, int]]
    objetivo_f: pulp.LpAffineExpression
    restr_capital: pulp.LpConstraint
    restr_concentracion: dict[str, pulp.LpConstraint] = field(default_factory=dict)
    restr_liquidez: dict[str, pulp.LpConstraint] = field(default_factory=dict)
    datos: DatosCDT = field(default=None, repr=False)  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Utilidad de nombres (coherente con model.py)
# ---------------------------------------------------------------------------
def _banco_seguro(banco: str) -> str:
    """Sanea el nombre del banco para identificadores PuLP estables."""
    return (
        banco.replace(" ", "_")
        .replace("-", "_")
        .replace("(", "")
        .replace(")", "")
    )


def _nombre_var(prefijo: str, clave: tuple[str, int, int]) -> str:
    """Nombre de variable PuLP a partir de la clave `(i, j, k)`."""
    banco, plazo, tramo = clave
    return f"{prefijo}_{_banco_seguro(banco)}_{plazo}_{tramo}"


# ---------------------------------------------------------------------------
# Construcción del LP restringido (Tarea 6.1)
# ---------------------------------------------------------------------------
def construir_lp_restringido(
    datos: DatosCDT,
    resultado: ResultadoCDT,
    nombre: str = "CDT_LP_restringido",
) -> LPRestringido:
    """Construye el LP lineal fijando `z = z*` (Requisitos 4.1 y 4.7).

    A partir de la solución óptima del MILP (`resultado`, que trae `z*`), arma un
    `LpProblem` **puramente lineal** que conserva solo las `x_ijk` activas
    (`z* = 1`) y la holgura `s_0`. Al fijar las binarias como constantes, cada
    familia de restricciones del MILP que dependía de `z` se transforma en una
    cota lineal constante sobre las `x` activas:

    - Vínculo de tramo `L_k·z ≤ x ≤ U_k·z`  →  para `z* = 1`: `L_k ≤ x ≤ U_k`
      (se impone como `lowBound`/`upBound` de la variable continua activa). Para
      `z* = 0` la variable simplemente no se crea (su `x*` es 0).
    - Mínimo de apertura `x ≥ m_ij·z`      →  para `z* = 1`: `x ≥ m_ij`
      (se combina con `L_k` tomando el mayor: `lowBound = max(L_k, m_ij)`).
    - A lo sumo un tramo `Σ_k z ≤ 1`        →  constante (ya satisfecha por `z*`);
      no aporta restricción al LP.
    - Disponibilidad `z ≤ disp`             →  constante; no aporta restricción.

    Las restricciones que NO dependen de `z` se reconstruyen en forma lineal
    sobre las activas:

    - Capital total (igualdad):   `Σ x_activas + s_0 = A`.
    - Concentración por banco:    `Σ_{j,k activos} x_ijk ≤ p_i·A`  (por banco i).
    - Liquidez corto/largo:       `L·A ≤ Σ x ≤ U·A`  (solo cotas definidas).

    El objetivo es el mismo de producción `Σ f_ijk·x_ijk`, ahora sobre las
    activas. Si el MILP es óptimo, resolver este LP debe **reproducir** el valor
    objetivo y la asignación del MILP (verificación de que la fijación es
    correcta; ver la autocomprobación al final del módulo).

    Parámetros
    ----------
    datos:
        `DatosCDT` de origen (los mismos parámetros usados para el MILP).
    resultado:
        `ResultadoCDT` del MILP resuelto (`solver.resolver`). Debe traer `z*`.
    nombre:
        Nombre del `LpProblem` lineal.

    Retorna
    -------
    `LPRestringido` con el problema lineal, las variables `x` activas y `s_0`, y
    los asideros a las restricciones con nombre para las Tareas 6.2 y 6.3.

    Lanza
    -----
    ValueError si el MILP no alcanzó óptimo (`resultado.es_optimo` es `False`):
    sin solución entera no hay `z*` que fijar.
    """
    if not resultado.es_optimo:
        raise ValueError(
            "No se puede construir el LP restringido: el MILP no alcanzó una "
            f"solución óptima (estado: {resultado.estado}). Se necesita z* para "
            "fijar las binarias (Requisito 4.1)."
        )

    # Claves activas en el óptimo (z* = 1), en orden estable.
    activas = [
        clave
        for clave in datos.combinaciones
        if resultado.z.get(clave, 0) >= _TOL_BINARIA
    ]

    problema = pulp.LpProblem(nombre, sense=pulp.LpMaximize)

    # --- Variables x_ijk activas (continuas) con cotas del tramo fijado -----
    # Fijar z* = 1 convierte el vínculo L_k·z ≤ x ≤ U_k·z y el mínimo de
    # apertura x ≥ m_ij·z en cotas constantes de la variable continua:
    #   lowBound = max(L_k, m_ij)   (cota inferior del tramo + mínimo apertura)
    #   upBound  = U_k   (A si el tramo es abierto por arriba, big-M = A)
    x: dict[tuple[str, int, int], pulp.LpVariable] = {}
    for clave in activas:
        _banco, _plazo, tramo = clave
        limite = datos.tramos_limites.get(tramo)
        if limite is None:
            raise ValueError(
                f"No hay límites de tramo definidos para el tramo {tramo} "
                f"(combinación activa {clave})."
            )
        limite_inferior, limite_superior = limite
        cota_superior = datos.A if limite_superior is None else limite_superior
        cota_inferior = max(limite_inferior, datos.m[clave])
        x[clave] = pulp.LpVariable(
            _nombre_var("x", clave),
            lowBound=cota_inferior,
            upBound=cota_superior,
            cat="Continuous",
        )

    # s_0 ≥ 0: holgura de no-inversión (igual que en el MILP).
    s0 = pulp.LpVariable("s_0", lowBound=0, cat="Continuous")

    # --- Objetivo lineal de producción Σ f_ijk·x_ijk (sobre activas) --------
    objetivo_f = pulp.lpSum(datos.f[clave] * x[clave] for clave in activas)
    problema += objetivo_f, "Objetivo_rendimiento_efectivo_f"

    # --- Restricción de capital (igualdad): Σ x + s_0 = A -------------------
    # Igualdad ⇒ su variable dual λ es libre; es el precio sombra del capital.
    problema += (
        pulp.lpSum(x[clave] for clave in activas) + s0 == datos.A,
        "capital_total",
    )
    restr_capital = problema.constraints["capital_total"]

    # --- Concentración por banco: Σ_{j,k} x_ijk ≤ p_i·A ---------------------
    # Solo se incluye un banco si tiene alguna combinación activa; un banco sin
    # activas tendría Σ = 0 ≤ p_i·A trivialmente (no aporta dual informativo).
    claves_por_banco: dict[str, list[tuple[str, int, int]]] = {}
    for clave in activas:
        banco = clave[0]
        claves_por_banco.setdefault(banco, []).append(clave)

    restr_concentracion: dict[str, pulp.LpConstraint] = {}
    for banco, claves in claves_por_banco.items():
        p_i = datos.p.get(banco)
        if p_i is None:
            raise ValueError(
                f"No hay concentración p_i definida para el banco '{banco}'."
            )
        nombre_c = f"concentracion_{_banco_seguro(banco)}"
        problema += (
            pulp.lpSum(x[clave] for clave in claves) <= p_i * datos.A,
            nombre_c,
        )
        restr_concentracion[banco] = problema.constraints[nombre_c]

    # --- Liquidez corto/largo plazo (solo cotas definidas) ------------------
    liq = datos.liquidez
    corto = [c for c in activas if c[1] <= 180]
    largo = [c for c in activas if c[1] > 180]
    suma_corto = pulp.lpSum(x[c] for c in corto)
    suma_largo = pulp.lpSum(x[c] for c in largo)

    restr_liquidez: dict[str, pulp.LpConstraint] = {}
    for l_clave, u_clave, suma, etiqueta in (
        ("L_corto", "U_corto", suma_corto, "corto"),
        ("L_largo", "U_largo", suma_largo, "largo"),
    ):
        l_val = liq.get(l_clave)
        u_val = liq.get(u_clave)
        if l_val is not None:
            nombre_li = f"liquidez_{etiqueta}_inf"
            problema += (suma >= l_val * datos.A, nombre_li)
            restr_liquidez[nombre_li] = problema.constraints[nombre_li]
        if u_val is not None:
            nombre_ls = f"liquidez_{etiqueta}_sup"
            problema += (suma <= u_val * datos.A, nombre_ls)
            restr_liquidez[nombre_ls] = problema.constraints[nombre_ls]

    return LPRestringido(
        problema=problema,
        x=x,
        s0=s0,
        z_estrella=dict(resultado.z),
        activas=activas,
        objetivo_f=objetivo_f,
        restr_capital=restr_capital,
        restr_concentracion=restr_concentracion,
        restr_liquidez=restr_liquidez,
        datos=datos,
    )


# ---------------------------------------------------------------------------
# Dual del LP restringido y precios sombra (Tarea 6.2)
# ---------------------------------------------------------------------------
#
# FORMULACIÓN EXPLÍCITA DEL PRIMAL (P) Y DEL DUAL (D)  (Requisito 4.2)
# -------------------------------------------------------------------
# Trabajamos SIEMPRE sobre el LP restringido (binarias fijadas en z*). Sea
# `Act = {(i, j, k) : z*_ijk = 1}` el conjunto de combinaciones activas y
# `x = (x_ijk)_{(i,j,k)∈Act}` el vector de montos continuos, más la holgura de
# no-inversión `s_0 ≥ 0`. El PRIMAL es:
#
#     (P)  max   Σ_{(i,j,k)∈Act}  f_ijk · x_ijk
#          s.a.  (capital, =)        Σ x_ijk + s_0        =  A            → λ
#                (concentración, ≤)  Σ_{j,k} x_ijk        ≤  p_i · A      → μ_i ≥ 0
#                                     (una fila por banco i con activas)
#                (liquidez inf, ≥)   Σ_{corto/largo} x    ≥  L_· · A      → σ⁻ ≥ 0
#                (liquidez sup, ≤)   Σ_{corto/largo} x    ≤  U_· · A      → σ⁺ ≥ 0
#                (cotas de tramo)    cota_inf_ijk ≤ x_ijk ≤ cota_sup_ijk  → ν_ijk
#                                     (mínimo de apertura y tramo activo)
#                x_ijk ≥ 0,  s_0 ≥ 0
#
# Las cotas de tramo `L_k ≤ x ≤ U_k` y el mínimo de apertura `x ≥ m_ij` se
# imponen como `lowBound`/`upBound` de cada variable (ver 6.1), por lo que su
# precio sombra `ν_ijk` es el "reduced cost" que PuLP expone en `var.dj`.
#
# El DUAL (D) asocia una variable a cada restricción primal y minimiza el costo
# imputado de los recursos. Con `λ` libre (igualdad), `μ_i, σ⁺ ≥ 0`, `σ⁻ ≥ 0`:
#
#     (D)  min   A·λ + Σ_i (p_i·A)·μ_i + Σ (U_·A)·σ⁺ − Σ (L_·A)·σ⁻ + (cotas)
#          s.a.  para cada x_ijk activa:
#                    λ + μ_{i(ijk)} + [σ de su tramo liq.] + ν_ijk  ≥  f_ijk
#                para s_0:                       λ  ≥  0   (coef. de s_0 en P es 0)
#                μ_i ≥ 0,  σ⁺ ≥ 0,  σ⁻ ≥ 0,  λ libre
#
# Es decir, el dual exige que el "precio compuesto" de los recursos que consume
# cada peso colocado en `(i,j,k)` cubra al menos su rendimiento `f_ijk`; en la
# base óptima la desigualdad se vuelve igualdad para las variables básicas
# (holgura complementaria, que verifica la Tarea 6.3).
#
# INTERPRETACIÓN ECONÓMICA DE LOS PRECIOS SOMBRA  (Requisito 4.3)
# --------------------------------------------------------------
# - λ*  (capital): retorno marginal de UNA unidad monetaria adicional de capital
#        `A`. Cuánto crecería el objetivo `Σ f_ijk·x_ijk` si dispusiéramos de un
#        peso más para invertir, manteniendo óptima la base.
# - μ_i* (concentración banco i): costo de oportunidad del tope `p_i·A`. Cuánto
#        rendimiento adicional se ganaría si se permitiera concentrar un peso más
#        en el banco `i`. `μ_i* > 0` ⇒ el tope de ese banco está activo y limita.
# - σ*  (liquidez corto/largo): costo (o valor) marginal de las cotas de reparto
#        de liquidez. Mide cuánto cuesta en rendimiento la exigencia de mantener
#        cierta fracción de `A` en plazos cortos/largos.
#
# RELACIÓN s_0* ↔ λ* POR HOLGURA COMPLEMENTARIA  (Requisitos 4.3 y 4.2)
# --------------------------------------------------------------------
# `s_0` entra en la restricción de capital `Σ x + s_0 = A` con coeficiente 0 en
# el objetivo. Su condición dual es `λ ≥ 0` y la holgura complementaria exige
# `s_0* · λ* = 0`:
#   - Si `s_0* > 0` (sobró capital sin colocar): necesariamente `λ* = 0`, porque
#     tener más capital no agrega retorno cuando ni siquiera se colocó todo el
#     disponible (las restricciones activas, no la escasez de capital, limitan).
#   - Si `s_0* = 0` (capital agotado): `λ*` puede ser > 0 y revela el valor
#     marginal del capital: cada peso extra sí se colocaría y produciría `λ*`.
# Esta relación es la que `extraer_precios_sombra` comprueba y reporta.


@dataclass
class PreciosSombra:
    """Precios sombra (valores duales) del LP restringido y su lectura económica.

    Es el **contrato** que produce la Tarea 6.2 y que consumen el reporte
    (Tarea 7) y la verificación de holgura complementaria / rangos (Tarea 6.3).
    Todos los precios sombra se refieren al LP restringido con `z = z*`, NO al
    MILP original (Requisito 4.7).

    Atributos
    ---------
    estado:
        Estado del solver sobre el LP restringido (`Optimal`, etc.).
    es_optimo:
        `True` si el LP se resolvió a óptimo (condición para leer `pi`).
    objetivo:
        Valor óptimo del LP `Σ f_ijk·x_ijk` (debe coincidir con el del MILP).
    lambda_capital:
        `λ*`: precio sombra de la restricción de capital `Σ x + s_0 = A`.
        Libre de signo (la restricción es igualdad). Retorno marginal de `A`.
    mu_concentracion:
        `{banco: μ_i*}`: precio sombra del tope de concentración `≤ p_i·A`
        (≥ 0). Costo de oportunidad de diversificar en ese banco.
    sigma_liquidez:
        `{etiqueta: σ*}`: precio sombra de cada cota de liquidez activa (las
        etiquetas coinciden con `LPRestringido.restr_liquidez`). Vacío si no hay
        cotas de liquidez definidas.
    s0_valor:
        `s_0*`: holgura de no-inversión en el óptimo del LP (capital sin colocar).
    capital_agotado:
        `True` si `s_0* ≈ 0` (todo el capital se colocó). Determina la lectura
        de `λ*` por complementariedad.
    interpretacion:
        `{clave: texto}` con la interpretación económica en español de cada
        precio sombra y de la relación `s_0* ↔ λ*` (Requisito 4.3). Claves:
        `"lambda"`, `"mu:<banco>"`, `"sigma:<etiqueta>"`, `"s0_lambda"`.
    """

    estado: str
    es_optimo: bool
    objetivo: Optional[float]
    lambda_capital: Optional[float]
    mu_concentracion: dict[str, float] = field(default_factory=dict)
    sigma_liquidez: dict[str, float] = field(default_factory=dict)
    s0_valor: float = 0.0
    capital_agotado: bool = False
    interpretacion: dict[str, str] = field(default_factory=dict)


# Tolerancia para considerar que la holgura de no-inversión s_0 es nula.
_TOL_S0 = 1e-4
# Tolerancia para considerar que un precio sombra es prácticamente cero.
_TOL_PI = 1e-9


def extraer_precios_sombra(
    lp: LPRestringido,
    solver: Optional[pulp.LpSolver] = None,
    resolver_si_necesario: bool = True,
) -> PreciosSombra:
    """Resuelve el LP restringido (si hace falta) y extrae sus precios sombra.

    Implementa la Tarea 6.2: obtiene `λ*` (capital), `μ_i*` (concentración) y
    `σ*` (liquidez) del DUAL del LP restringido a través de `constraint.pi` de
    PuLP, y construye su interpretación económica (Requisitos 4.2 y 4.3),
    incluyendo la relación `s_0* ↔ λ*` por holgura complementaria.

    La formulación explícita del Primal (P) y del Dual (D) está documentada en
    el bloque de comentarios que precede a esta función (Requisito 4.2).

    NO verifica aún la condición global de holgura complementaria `(x*)^T s* = 0`
    ni calcula rangos de sensibilidad: eso corresponde a la Tarea 6.3.

    Parámetros
    ----------
    lp:
        El `LPRestringido` de la Tarea 6.1 (variables activas + restricciones
        con nombre). Si ya fue resuelto, se reutilizan sus valores duales.
    solver:
        Solver PuLP a usar si hay que resolver. Por defecto
        `PULP_CBC_CMD(msg=False)`, coherente con el resto del proyecto.
    resolver_si_necesario:
        Si `True` (por defecto) y el LP no está en estado óptimo, lo resuelve
        antes de leer los duales. Si `False`, asume que ya fue resuelto.

    Retorna
    -------
    `PreciosSombra` con `λ*`, `μ_i*`, `σ*`, `s_0*` y los textos de interpretación.

    Lanza
    -----
    ValueError si tras resolver el LP no se alcanza óptimo (sin óptimo no hay
    precios sombra válidos que interpretar).
    """
    problema = lp.problema

    # Resolver el LP si aún no tiene una solución óptima disponible.
    if resolver_si_necesario and problema.status != pulp.LpStatusOptimal:
        if solver is None:
            solver = pulp.PULP_CBC_CMD(msg=False)
        problema.solve(solver)

    estado = pulp.LpStatus[problema.status]
    es_optimo = problema.status == pulp.LpStatusOptimal
    if not es_optimo:
        raise ValueError(
            "No se pueden extraer precios sombra: el LP restringido no alcanzó "
            f"una solución óptima (estado: {estado}). Sin óptimo la dualidad no "
            "está definida (Requisito 4.2)."
        )

    objetivo = pulp.value(problema.objective)
    objetivo = None if objetivo is None else float(objetivo)

    # --- λ*: precio sombra del capital (igualdad ⇒ libre de signo) ----------
    lambda_capital = lp.restr_capital.pi
    lambda_capital = None if lambda_capital is None else float(lambda_capital)

    # --- μ_i*: precio sombra de concentración por banco (≥ 0) ---------------
    mu_concentracion: dict[str, float] = {}
    for banco, restr in lp.restr_concentracion.items():
        pi = restr.pi
        mu_concentracion[banco] = 0.0 if pi is None else float(pi)

    # --- σ*: precio sombra de cada cota de liquidez activa ------------------
    sigma_liquidez: dict[str, float] = {}
    for etiqueta, restr in lp.restr_liquidez.items():
        pi = restr.pi
        sigma_liquidez[etiqueta] = 0.0 if pi is None else float(pi)

    # --- s_0*: holgura de no-inversión y lectura de complementariedad -------
    s0_valor = lp.s0.value()
    s0_valor = 0.0 if s0_valor is None else float(s0_valor)
    capital_agotado = s0_valor <= _TOL_S0

    # --- Interpretación económica (Requisito 4.3) ---------------------------
    interpretacion: dict[str, str] = {}

    if lambda_capital is not None:
        interpretacion["lambda"] = (
            f"λ* = {lambda_capital:.8f}: retorno marginal de una unidad "
            "adicional de capital A. Es el incremento del objetivo "
            "Σ f_ijk·x_ijk por cada peso extra de capital disponible, "
            "manteniendo óptima la base del LP restringido."
        )

    for banco, mu in mu_concentracion.items():
        if abs(mu) > _TOL_PI:
            interpretacion[f"mu:{banco}"] = (
                f"μ_{banco}* = {mu:.8f} > 0: el tope de concentración "
                f"p·A del banco '{banco}' está ACTIVO. Es el costo de "
                "oportunidad de la diversificación: cuánto rendimiento extra se "
                "ganaría si se permitiera colocar un peso más en ese banco."
            )
        else:
            interpretacion[f"mu:{banco}"] = (
                f"μ_{banco}* ≈ 0: el tope de concentración del banco "
                f"'{banco}' NO está activo (hay holgura); relajarlo no "
                "mejoraría el objetivo."
            )

    for etiqueta, sigma in sigma_liquidez.items():
        if abs(sigma) > _TOL_PI:
            interpretacion[f"sigma:{etiqueta}"] = (
                f"σ_{etiqueta}* = {sigma:.8f}: la cota de liquidez "
                f"'{etiqueta}' está activa; es el costo/valor marginal en "
                "rendimiento de exigir ese reparto de capital entre plazos "
                "cortos y largos."
            )
        else:
            interpretacion[f"sigma:{etiqueta}"] = (
                f"σ_{etiqueta}* ≈ 0: la cota de liquidez '{etiqueta}' no "
                "está activa; no restringe la solución óptima."
            )

    # Relación s_0* ↔ λ* por holgura complementaria (s_0*·λ* = 0).
    if not capital_agotado:
        interpretacion["s0_lambda"] = (
            f"s_0* = {s0_valor:,.2f} > 0 (sobró capital): por holgura "
            "complementaria s_0*·λ* = 0 ⇒ λ* = 0. Tener más capital no agrega "
            "retorno, pues ni siquiera se colocó todo el disponible; son las "
            "otras restricciones activas (concentración/liquidez/tramos), no la "
            "escasez de capital, las que limitan."
        )
    else:
        interpretacion["s0_lambda"] = (
            f"s_0* ≈ 0 (capital agotado): λ* = "
            f"{lambda_capital if lambda_capital is not None else float('nan'):.8f} "
            "revela el valor marginal del capital: cada peso adicional sí se "
            "colocaría y produciría ese rendimiento extra."
        )

    return PreciosSombra(
        estado=estado,
        es_optimo=es_optimo,
        objetivo=objetivo,
        lambda_capital=lambda_capital,
        mu_concentracion=mu_concentracion,
        sigma_liquidez=sigma_liquidez,
        s0_valor=s0_valor,
        capital_agotado=capital_agotado,
        interpretacion=interpretacion,
    )


# ---------------------------------------------------------------------------
# Holgura complementaria y rangos de sensibilidad (Tarea 6.3)
# ---------------------------------------------------------------------------
#
# TEOREMA DE HOLGURA COMPLEMENTARIA  (Requisito 4.4)
# -------------------------------------------------
# En el óptimo de un par primal–dual, el producto de cada variable por la
# holgura de su restricción complementaria es nulo. Sobre el LP restringido se
# comprueba la condición global `(x*)^T s* = 0` descomponiéndola en dos familias
# que, sumadas, cubren todos los términos del producto escalar:
#
#   (a) Por RESTRICCIÓN primal:  slack_c · π_c = 0  para toda restricción `c`.
#       Si una restricción NO está activa (tiene holgura `slack_c ≠ 0`), su
#       precio sombra debe ser nulo (`π_c = 0`); si está activa (`slack_c = 0`),
#       su `π_c` puede ser no nulo. (Para la igualdad de capital `slack ≈ 0`
#       siempre, luego su término es ≈ 0 cualquiera sea `λ*`.)
#
#   (b) Por VARIABLE primal:     dj_v · (v − cota_activa) = 0  para toda `x_ijk`.
#       El "reduced cost" `dj_v` (PuLP: `var.dj`) es el dual de las cotas de la
#       variable. Si `v` está estrictamente dentro de sus cotas (básica), su
#       `dj_v` debe ser nulo; si `v` está pegada a una cota (no básica), su
#       `dj_v` puede ser no nulo pero entonces `(v − cota)` es ≈ 0. En ambos
#       casos el producto es ≈ 0. La holgura `s_0` entra aquí como una variable
#       más: `dj_{s_0} · s_0 = 0` reproduce la relación `s_0*·λ* = 0`.
#
# La verificación reporta el MÁXIMO valor absoluto de todos esos productos (la
# "violación") y lo compara contra una tolerancia (p. ej. `1e-6`). Si el máximo
# queda por debajo de la tolerancia, la holgura complementaria se cumple.
#
# RANGOS DE SENSIBILIDAD  (Requisitos 4.5 y 4.6)
# ----------------------------------------------
# CBC (el solver de PuLP) NO expone directamente el "ranging" clásico del
# símplex (allowable increase/decrease). Se adopta un enfoque PRAGMÁTICO y
# transparente, documentado con sus límites:
#
#   - Coeficientes objetivo `f_ijk` (Req. 4.5): para cada variable activa se
#     perturba su coeficiente `f_ijk` hacia arriba y hacia abajo, se re-resuelve
#     el LP y se detecta el punto donde cambia la BASE óptima (el conjunto de
#     variables activas con monto > 0, o un cambio de asignación mayor que una
#     tolerancia). El rango `[f_min, f_max]` es el intervalo de estabilidad de
#     la base para ese coeficiente, manteniendo los demás fijos (análisis
#     "un coeficiente a la vez"). Para variables NO básicas (pegadas a cota con
#     `dj ≠ 0`) el reduced cost da además la holgura disponible antes de que
#     entren a la base.
#
#   - Lado derecho `b` (Req. 4.6): se perturba cada RHS —capital `A` y cada tope
#     de concentración `p_i·A`— y se re-resuelve para hallar el intervalo en que
#     se mantiene la base óptima (mismo conjunto de restricciones activas y mismo
#     signo de los duales). Dentro de ese intervalo el precio sombra es constante
#     y la variación del objetivo es lineal: `Δobjetivo = π · Δb`.
#
# LIMITACIONES (se reportan explícitamente):
#   * El método es numérico (perturbación + re-solución), no un ranging exacto
#     del símplex; la resolución del intervalo depende del paso de búsqueda.
#   * Es válido "un parámetro a la vez" (ceteris paribus); no cubre cambios
#     simultáneos (regla del 100%).
#   * Si el LP restringido es DEGENERADO, los rangos pueden NO ser únicos y el
#     precio sombra puede no ser una derivada bien definida; se advierte en el
#     informe (ver `design.md`, "Manejo de errores").


@dataclass
class TerminoComplementariedad:
    """Un término individual del producto `(x*)^T s* = 0` y su violación.

    Atributos
    ---------
    tipo:
        `"restriccion"` (slack·π) o `"variable"` (dj·holgura de cota).
    nombre:
        Identificador legible del término (nombre de la restricción o variable).
    factor_a, factor_b:
        Los dos factores cuyo producto debería ser nulo. Para restricciones:
        `(slack, π)`. Para variables: `(dj, distancia_a_la_cota_activa)`.
    producto:
        `factor_a · factor_b`; su valor absoluto es la violación de este término.
    """

    tipo: str
    nombre: str
    factor_a: float
    factor_b: float
    producto: float


@dataclass
class HolguraComplementaria:
    """Resultado de verificar `(x*)^T s* = 0` sobre el LP restringido (Req. 4.4).

    Atributos
    ---------
    cumple:
        `True` si la máxima violación queda dentro de la tolerancia.
    max_violacion:
        Mayor valor absoluto de los productos complementarios (slack·π y
        dj·distancia). Es la "distancia" numérica a la complementariedad exacta.
    tolerancia:
        Umbral usado para decidir `cumple` (p. ej. `1e-6`).
    producto_global:
        Suma de los productos por variable `Σ dj_v·(v−cota)`, una lectura directa
        del escalar `(x*)^T s*` por el lado de las variables.
    terminos:
        Lista de `TerminoComplementariedad` (restricciones y variables), ordenada
        por violación descendente, para el reporte.
    interpretacion:
        Texto en español con el veredicto y el término más crítico (Req. 4.4).
    """

    cumple: bool
    max_violacion: float
    tolerancia: float
    producto_global: float
    terminos: list[TerminoComplementariedad] = field(default_factory=list)
    interpretacion: str = ""


# Tolerancia por defecto para la holgura complementaria (design.md: ~1e-6).
_TOL_COMPLEMENTARIEDAD = 1e-6


def verificar_holgura_complementaria(
    lp: LPRestringido,
    tolerancia: float = _TOL_COMPLEMENTARIEDAD,
) -> HolguraComplementaria:
    """Comprueba el Teorema de Holgura Complementaria `(x*)^T s* = 0` (Req. 4.4).

    Descompone el producto escalar en términos por restricción (`slack·π`) y por
    variable (`dj·distancia_a_la_cota`), calcula el máximo valor absoluto de esos
    productos y lo compara con `tolerancia`. Requiere que el LP ya esté resuelto a
    óptimo (p. ej. tras `extraer_precios_sombra`); de lo contrario lo resuelve.

    La teoría que sustenta la descomposición está en el bloque de comentarios que
    precede a esta función (familias (a) restricciones y (b) variables).

    Parámetros
    ----------
    lp:
        El `LPRestringido` (Tarea 6.1) ya resuelto o resoluble.
    tolerancia:
        Umbral numérico para aceptar la complementariedad (por defecto `1e-6`).

    Retorna
    -------
    `HolguraComplementaria` con el veredicto, la máxima violación, el detalle por
    término y una interpretación en español.

    Lanza
    -----
    ValueError si el LP no alcanza óptimo (sin óptimo no hay dual que verificar).
    """
    problema = lp.problema
    if problema.status != pulp.LpStatusOptimal:
        problema.solve(pulp.PULP_CBC_CMD(msg=False))
    if problema.status != pulp.LpStatusOptimal:
        raise ValueError(
            "No se puede verificar holgura complementaria: el LP restringido no "
            f"alcanzó óptimo (estado: {pulp.LpStatus[problema.status]})."
        )

    terminos: list[TerminoComplementariedad] = []

    # (a) Por restricción: slack_c · π_c debe ser ≈ 0.
    for nombre, restr in problema.constraints.items():
        slack = restr.slack
        pi = restr.pi
        slack = 0.0 if slack is None else float(slack)
        pi = 0.0 if pi is None else float(pi)
        terminos.append(
            TerminoComplementariedad(
                tipo="restriccion",
                nombre=nombre,
                factor_a=slack,
                factor_b=pi,
                producto=slack * pi,
            )
        )

    # (b) Por variable: dj_v · (distancia a la cota activa) debe ser ≈ 0.
    # La distancia se toma a la cota más cercana (inferior o superior): si la
    # variable es básica (interior) la distancia es grande pero dj ≈ 0; si es no
    # básica (pegada a una cota) la distancia es ≈ 0 aunque dj ≠ 0.
    producto_global = 0.0
    variables = list(lp.x.values()) + [lp.s0]
    for var in variables:
        valor = var.value()
        valor = 0.0 if valor is None else float(valor)
        dj = getattr(var, "dj", None)
        dj = 0.0 if dj is None else float(dj)

        low = var.lowBound if var.lowBound is not None else float("-inf")
        up = var.upBound if var.upBound is not None else float("inf")
        dist_low = abs(valor - low) if low != float("-inf") else float("inf")
        dist_up = abs(up - valor) if up != float("inf") else float("inf")
        distancia = min(dist_low, dist_up)

        producto = dj * distancia
        producto_global += producto
        terminos.append(
            TerminoComplementariedad(
                tipo="variable",
                nombre=var.name,
                factor_a=dj,
                factor_b=distancia,
                producto=producto,
            )
        )

    terminos.sort(key=lambda t: abs(t.producto), reverse=True)
    max_violacion = abs(terminos[0].producto) if terminos else 0.0
    cumple = max_violacion <= tolerancia

    if cumple:
        peor = terminos[0] if terminos else None
        detalle_peor = (
            f" Término más holgado: '{peor.nombre}' "
            f"(|producto| = {abs(peor.producto):.2e})."
            if peor is not None
            else ""
        )
        interpretacion = (
            f"Holgura complementaria VERIFICADA: la máxima violación "
            f"({max_violacion:.2e}) está por debajo de la tolerancia "
            f"({tolerancia:.0e}). El óptimo primal y el dual son coherentes: "
            f"toda restricción no activa tiene precio sombra nulo y toda "
            f"variable interior tiene reduced cost nulo.{detalle_peor}"
        )
    else:
        peor = terminos[0]
        interpretacion = (
            f"Holgura complementaria NO verificada: la máxima violación "
            f"({max_violacion:.2e}) supera la tolerancia ({tolerancia:.0e}). "
            f"Término crítico: '{peor.nombre}' ({peor.tipo}) con factores "
            f"({peor.factor_a:.6g}, {peor.factor_b:.6g}). Puede deberse a "
            f"degeneración del LP o a tolerancias del solver."
        )

    return HolguraComplementaria(
        cumple=cumple,
        max_violacion=max_violacion,
        tolerancia=tolerancia,
        producto_global=producto_global,
        terminos=terminos,
        interpretacion=interpretacion,
    )


# ---------------------------------------------------------------------------
# Rangos de sensibilidad por perturbación (Requisitos 4.5 y 4.6)
# ---------------------------------------------------------------------------
@dataclass
class RangoSensibilidad:
    """Intervalo de estabilidad de la base para un parámetro (Req. 4.5/4.6).

    Atributos
    ---------
    parametro:
        Identificador del parámetro analizado (p. ej. `f:(Banco,180,2)` o
        `A`, `concentracion:Banco`).
    valor_base:
        Valor actual del parámetro en el óptimo.
    limite_inferior, limite_superior:
        Extremos del intervalo `[valor_min, valor_max]` dentro del cual la base
        óptima (conjunto de variables básicas / restricciones activas) se
        mantiene. `-inf`/`+inf` indican que no se halló cambio en el rango de
        búsqueda explorado.
    permitido_bajar, permitido_subir:
        Holguras `valor_base − limite_inferior` y `limite_superior − valor_base`
        (allowable decrease / increase), en las unidades del parámetro.
    interpretacion:
        Texto en español con la lectura económica del rango.
    """

    parametro: str
    valor_base: float
    limite_inferior: float
    limite_superior: float
    permitido_bajar: float
    permitido_subir: float
    interpretacion: str = ""


@dataclass
class RangosSensibilidad:
    """Conjunto de rangos de coeficientes objetivo y de RHS (Req. 4.5 y 4.6).

    Atributos
    ---------
    objetivo_f:
        `{clave (i,j,k): RangoSensibilidad}` para los coeficientes `f_ijk`.
    rhs:
        `{nombre_recurso: RangoSensibilidad}` para `A` y los topes `p_i·A`.
    degenerado:
        `True` si se detectó degeneración (alguna variable básica en su cota o
        restricción activa con holgura nula y dual nulo); en tal caso los rangos
        pueden NO ser únicos (design.md).
    metodo:
        Descripción del método usado (perturbación + re-solución) y sus límites.
    advertencia_degeneracion:
        Texto en español que se incluye si `degenerado` es `True`.
    """

    objetivo_f: dict[tuple[str, int, int], RangoSensibilidad] = field(
        default_factory=dict
    )
    rhs: dict[str, RangoSensibilidad] = field(default_factory=dict)
    degenerado: bool = False
    metodo: str = ""
    advertencia_degeneracion: str = ""


# Tolerancia para considerar que la asignación óptima "cambió de base".
_TOL_BASE = 1e-4


def _solver_silencioso() -> pulp.LpSolver:
    """Devuelve el solver CBC en modo silencioso (coherente con el proyecto)."""
    return pulp.PULP_CBC_CMD(msg=False)


def _firma_base(lp: LPRestringido) -> frozenset[str]:
    """Firma de la base óptima: estructura de variables y restricciones activas.

    Caracteriza la base del símplex por su ESTADO de actividad, no solo por qué
    variables son positivas. Un cambio en esta firma indica que la base óptima
    cambió (una variable entró/salió o una restricción pasó a estar activa). La
    firma combina:

    - Para cada variable `x_ijk` y `s_0`: si está en su cota inferior
      (`@low`), en su cota superior (`@up`) o es básica/interior (`@basic`).
      Capturar la cota pegada es clave: en este modelo muchas `x` quedan topadas
      por el límite del tramo `U_k`, y ese es precisamente el estado que define
      la base aunque el monto sea positivo.
    - Para cada restricción: si está activa (holgura ≈ 0, `=act`) o con holgura
      (`=slack`).

    Es una aproximación operativa a la base del símplex, suficiente para
    delimitar por perturbación el intervalo de estabilidad.
    """
    firma: set[str] = set()
    for nombre, var in [(clave_a_texto(c), v) for c, v in lp.x.items()] + [
        ("s_0", lp.s0)
    ]:
        valor = var.value() or 0.0
        low = var.lowBound if var.lowBound is not None else float("-inf")
        up = var.upBound if var.upBound is not None else float("inf")
        if low != float("-inf") and abs(valor - low) <= _TOL_BASE:
            firma.add(f"{nombre}@low")
        elif up != float("inf") and abs(up - valor) <= _TOL_BASE:
            firma.add(f"{nombre}@up")
        else:
            firma.add(f"{nombre}@basic")
    for nombre, restr in lp.problema.constraints.items():
        slack = restr.slack
        slack = 0.0 if slack is None else float(slack)
        firma.add(f"{nombre}={'act' if abs(slack) <= _TOL_BASE else 'slack'}")
    return frozenset(firma)


def clave_a_texto(clave: tuple[str, int, int]) -> str:
    """Convierte la clave `(i, j, k)` en un identificador textual estable."""
    banco, plazo, tramo = clave
    return f"{banco}|{plazo}|{tramo}"


def _detectar_degeneracion(lp: LPRestringido) -> bool:
    """Heurística de degeneración sobre el LP ya resuelto.

    Señala degeneración si alguna variable básica (interior) queda pegada a una
    cota, o si alguna restricción activa (holgura ≈ 0) tiene dual nulo. En esos
    casos los rangos de sensibilidad pueden no ser únicos (design.md).
    """
    for var in list(lp.x.values()) + [lp.s0]:
        valor = var.value() or 0.0
        low = var.lowBound if var.lowBound is not None else float("-inf")
        up = var.upBound if var.upBound is not None else float("inf")
        dj = getattr(var, "dj", None) or 0.0
        pegada = (low != float("-inf") and abs(valor - low) <= _TOL_BASE) or (
            up != float("inf") and abs(up - valor) <= _TOL_BASE
        )
        # Variable pegada a una cota pero con reduced cost nulo => degeneración.
        if pegada and abs(dj) <= 1e-9:
            return True
    for restr in lp.problema.constraints.values():
        slack = restr.slack or 0.0
        pi = restr.pi or 0.0
        if abs(slack) <= _TOL_BASE and abs(pi) <= 1e-9:
            return True
    return False


def _resolver_y_firma(
    lp: LPRestringido, solver: pulp.LpSolver
) -> tuple[bool, frozenset[str]]:
    """Re-resuelve el LP y devuelve `(es_optimo, firma_base)`."""
    lp.problema.solve(solver)
    optimo = lp.problema.status == pulp.LpStatusOptimal
    return optimo, (_firma_base(lp) if optimo else frozenset())


def _rango_coeficiente_f(
    lp: LPRestringido,
    clave: tuple[str, int, int],
    base_ref: frozenset[str],
    solver: pulp.LpSolver,
    pasos: int = 60,
    factor_max: float = 2.0,
) -> RangoSensibilidad:
    """Rango de estabilidad del coeficiente objetivo `f_ijk` de una variable.

    Perturba el coeficiente de `x[clave]` en el objetivo (hacia arriba y hacia
    abajo) re-resolviendo hasta que la base óptima cambia. Restaura el objetivo
    original al terminar. Método "un coeficiente a la vez" (Req. 4.5).
    """
    datos = lp.datos
    f_base = float(datos.f[clave])
    objetivo_original = lp.problema.objective

    # Rango de búsqueda simétrico alrededor de f_base (acotado y en magnitud).
    amplitud = max(abs(f_base), 1e-3) * factor_max
    paso = amplitud / pasos

    def _fijar_coeficiente(nuevo_f: float) -> None:
        nuevo = pulp.lpSum(
            (nuevo_f if c == clave else datos.f[c]) * lp.x[c] for c in lp.activas
        )
        lp.problema.setObjective(nuevo)

    # Hacia arriba: mayor f hasta que la base cambie.
    limite_superior = float("inf")
    for n in range(1, pasos + 1):
        _fijar_coeficiente(f_base + n * paso)
        optimo, firma = _resolver_y_firma(lp, solver)
        if (not optimo) or firma != base_ref:
            limite_superior = f_base + n * paso
            break

    # Hacia abajo: menor f hasta que la base cambie.
    limite_inferior = float("-inf")
    for n in range(1, pasos + 1):
        _fijar_coeficiente(f_base - n * paso)
        optimo, firma = _resolver_y_firma(lp, solver)
        if (not optimo) or firma != base_ref:
            limite_inferior = f_base - n * paso
            break

    # Restaurar el objetivo original y re-resolver para dejar el LP como estaba.
    lp.problema.setObjective(objetivo_original)
    lp.problema.solve(solver)

    permitido_subir = (
        float("inf") if limite_superior == float("inf") else limite_superior - f_base
    )
    permitido_bajar = (
        float("inf") if limite_inferior == float("-inf") else f_base - limite_inferior
    )

    banco, plazo, tramo = clave
    interpretacion = (
        f"f para ({banco}, {plazo}d, tramo {tramo}) = {f_base:.6f}. La base "
        f"óptima se mantiene aproximadamente en "
        f"[{limite_inferior:.6f}, {limite_superior:.6f}] "
        f"(baja ≤ {permitido_bajar:.6f}, sube ≤ {permitido_subir:.6f}). Fuera de "
        "ese intervalo conviene reasignar el capital (cambia la base)."
    )

    return RangoSensibilidad(
        parametro=f"f:{clave}",
        valor_base=f_base,
        limite_inferior=limite_inferior,
        limite_superior=limite_superior,
        permitido_bajar=permitido_bajar,
        permitido_subir=permitido_subir,
        interpretacion=interpretacion,
    )


def _rango_rhs(
    lp: LPRestringido,
    nombre: str,
    restr: pulp.LpConstraint,
    base_ref: frozenset[str],
    solver: pulp.LpSolver,
    pasos: int = 60,
    fraccion_max: float = 0.6,
) -> RangoSensibilidad:
    """Rango de estabilidad del lado derecho `b` de una restricción (Req. 4.6).

    Perturba el término independiente de `restr` (capital `A` o un tope `p_i·A`)
    re-resolviendo hasta que la base cambia. El RHS en PuLP es `-constant` de la
    restricción; se restaura al terminar. Método "un RHS a la vez".
    """
    b_base = -float(restr.constant)
    amplitud = max(abs(b_base), 1.0) * fraccion_max
    paso = amplitud / pasos
    constant_original = restr.constant

    def _fijar_rhs(nuevo_b: float) -> None:
        restr.constant = -nuevo_b

    limite_superior = float("inf")
    for n in range(1, pasos + 1):
        _fijar_rhs(b_base + n * paso)
        optimo, firma = _resolver_y_firma(lp, solver)
        if (not optimo) or firma != base_ref:
            limite_superior = b_base + n * paso
            break

    limite_inferior = float("-inf")
    for n in range(1, pasos + 1):
        candidato = b_base - n * paso
        if candidato < 0:  # un RHS negativo no tiene sentido (capital/topes ≥ 0)
            limite_inferior = max(candidato + paso, 0.0)
            break
        _fijar_rhs(candidato)
        optimo, firma = _resolver_y_firma(lp, solver)
        if (not optimo) or firma != base_ref:
            limite_inferior = candidato
            break

    # Restaurar el RHS original y re-resolver.
    restr.constant = constant_original
    lp.problema.solve(solver)

    permitido_subir = (
        float("inf") if limite_superior == float("inf") else limite_superior - b_base
    )
    permitido_bajar = (
        float("inf") if limite_inferior == float("-inf") else b_base - limite_inferior
    )

    interpretacion = (
        f"RHS de '{nombre}' = {b_base:,.2f}. La base óptima (y por tanto el "
        f"precio sombra) se mantiene aproximadamente en "
        f"[{limite_inferior:,.2f}, {limite_superior:,.2f}] "
        f"(baja ≤ {permitido_bajar:,.2f}, sube ≤ {permitido_subir:,.2f}). Dentro "
        "de ese intervalo la variación del objetivo es lineal: Δobjetivo = π·Δb."
    )

    return RangoSensibilidad(
        parametro=f"rhs:{nombre}",
        valor_base=b_base,
        limite_inferior=limite_inferior,
        limite_superior=limite_superior,
        permitido_bajar=permitido_bajar,
        permitido_subir=permitido_subir,
        interpretacion=interpretacion,
    )


def calcular_rangos_sensibilidad(
    lp: LPRestringido,
    solver: Optional[pulp.LpSolver] = None,
    incluir_rhs: bool = True,
) -> RangosSensibilidad:
    """Calcula rangos de coeficientes objetivo `f_ijk` y de RHS (Req. 4.5 y 4.6).

    Sobre el LP restringido ya resuelto, halla por perturbación + re-solución el
    intervalo de estabilidad de la base óptima para:

    - cada coeficiente objetivo `f_ijk` de las variables activas (Req. 4.5), y
    - cada RHS de recurso: capital `A` y cada tope de concentración `p_i·A`
      (Req. 4.6).

    Detecta degeneración y, de haberla, advierte que los rangos pueden no ser
    únicos (design.md). El método y sus límites quedan documentados en el campo
    `metodo` del resultado.

    Parámetros
    ----------
    lp:
        El `LPRestringido` (Tarea 6.1). Se resuelve si aún no está en óptimo.
    solver:
        Solver PuLP; por defecto CBC silencioso.
    incluir_rhs:
        Si `True` (por defecto) calcula también los rangos de RHS (Req. 4.6).

    Retorna
    -------
    `RangosSensibilidad` con los rangos de `f_ijk` y de RHS, la marca de
    degeneración y la descripción del método.

    Lanza
    -----
    ValueError si el LP no alcanza óptimo.
    """
    if solver is None:
        solver = _solver_silencioso()

    if lp.problema.status != pulp.LpStatusOptimal:
        lp.problema.solve(solver)
    if lp.problema.status != pulp.LpStatusOptimal:
        raise ValueError(
            "No se pueden calcular rangos de sensibilidad: el LP restringido no "
            f"alcanzó óptimo (estado: {pulp.LpStatus[lp.problema.status]})."
        )

    base_ref = _firma_base(lp)
    degenerado = _detectar_degeneracion(lp)

    metodo = (
        "Rangos por PERTURBACIÓN + re-solución del LP restringido (un parámetro "
        "a la vez, ceteris paribus). CBC no expone el ranging exacto del símplex; "
        "los extremos son numéricos y dependen del paso de búsqueda. No cubre "
        "cambios simultáneos (regla del 100%). Válido solo para el LP restringido "
        "con z fijadas en z* (Req. 4.7)."
    )

    # --- Rangos de coeficientes objetivo f_ijk (Req. 4.5) -------------------
    objetivo_f: dict[tuple[str, int, int], RangoSensibilidad] = {}
    for clave in lp.activas:
        objetivo_f[clave] = _rango_coeficiente_f(lp, clave, base_ref, solver)

    # --- Rangos de RHS: capital A y topes de concentración p_i·A (Req. 4.6) -
    rhs: dict[str, RangoSensibilidad] = {}
    if incluir_rhs:
        rhs["capital_A"] = _rango_rhs(
            lp, "capital_total (A)", lp.restr_capital, base_ref, solver
        )
        for banco, restr in lp.restr_concentracion.items():
            rhs[f"concentracion_{banco}"] = _rango_rhs(
                lp, f"concentracion {banco} (p·A)", restr, base_ref, solver
            )

    advertencia = ""
    if degenerado:
        advertencia = (
            "ADVERTENCIA: el LP restringido es DEGENERADO (alguna variable básica "
            "pegada a su cota o restricción activa con dual nulo). Los rangos de "
            "sensibilidad pueden NO ser únicos y el precio sombra puede no ser una "
            "derivada bien definida; interpretar con cautela (design.md)."
        )

    return RangosSensibilidad(
        objetivo_f=objetivo_f,
        rhs=rhs,
        degenerado=degenerado,
        metodo=metodo,
        advertencia_degeneracion=advertencia,
    )


# ---------------------------------------------------------------------------
# Autocomprobación de humo (sin framework): MILP → LP restringido → LP.
# Valida que fijar z* y resolver el LP reproduce el objetivo y la asignación del
# MILP (si no, la fijación de binarias estaría mal planteada). Usa el fixture
# sintético de model.py por el principio de cero invención de datos reales.
# Ejecutar con:  python src/sensitivity.py
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    from model import (
        _datos_sinteticos,
        agregar_restricciones_riesgo,
        agregar_restricciones_tramos,
        construir_modelo,
    )
    from solver import resolver

    datos = _datos_sinteticos()

    # 1) Resolver el MILP para obtener z*.
    modelo = construir_modelo(datos)
    agregar_restricciones_tramos(modelo)
    agregar_restricciones_riesgo(modelo)
    resultado_milp = resolver(modelo)

    print("== LP restringido fijando binarias (Tarea 6.1) ==")
    print(f"MILP estado        : {resultado_milp.estado}")
    print(f"MILP óptimo        : {resultado_milp.es_optimo}")
    print(f"MILP objetivo (f)  : {resultado_milp.objetivo:,.6f}")
    print(f"MILP Σx*           : {resultado_milp.capital_colocado:,.2f}")
    print(f"MILP s_0*          : {resultado_milp.s0:,.2f}")
    activas_milp = sorted(resultado_milp.x.items())
    print(f"MILP activas       : {activas_milp}")

    # 2) Construir el LP restringido fijando z*.
    lp = construir_lp_restringido(datos, resultado_milp)
    print(f"\nLP variables x     : {len(lp.x)} (activas z*=1)")
    print(f"LP restr capital   : {lp.restr_capital.name}")
    print(f"LP restr concentr. : {list(lp.restr_concentracion)}")
    print(f"LP restr liquidez  : {list(lp.restr_liquidez)}")
    print("Nota (Req. 4.7): la sensibilidad aplica a ESTE LP, no al MILP.")

    # 3) Resolver el LP y comprobar que reproduce el MILP (valida la fijación).
    lp.problema.solve(pulp.PULP_CBC_CMD(msg=False))
    estado_lp = pulp.LpStatus[lp.problema.status]
    objetivo_lp = pulp.value(lp.problema.objective) or 0.0
    s0_lp = lp.s0.value() or 0.0
    x_lp = {
        clave: round(var.value() or 0.0, 2)
        for clave, var in lp.x.items()
        if (var.value() or 0.0) > 1e-4
    }

    print(f"\nLP estado          : {estado_lp}")
    print(f"LP objetivo (f)    : {objetivo_lp:,.6f}")
    print(f"LP s_0             : {s0_lp:,.2f}")
    print(f"LP activas         : {sorted(x_lp.items())}")

    # --- Verificación: el LP restringido reproduce el MILP ------------------
    tol = 1e-4
    assert estado_lp == "Optimal", f"El LP restringido no fue óptimo: {estado_lp}"

    assert abs(objetivo_lp - (resultado_milp.objetivo or 0.0)) <= tol * max(
        1.0, abs(resultado_milp.objetivo or 1.0)
    ), (
        f"El objetivo del LP ({objetivo_lp:,.6f}) no reproduce el del MILP "
        f"({resultado_milp.objetivo:,.6f})."
    )

    assert abs(s0_lp - resultado_milp.s0) <= tol * max(1.0, datos.A), (
        f"La holgura s_0 del LP ({s0_lp:,.2f}) no reproduce la del MILP "
        f"({resultado_milp.s0:,.2f})."
    )

    # La asignación activa debe coincidir monto a monto con la del MILP.
    milp_dict = dict(resultado_milp.x)
    assert set(x_lp) == set(milp_dict), (
        "Las combinaciones activas del LP no coinciden con las del MILP: "
        f"LP={sorted(x_lp)} vs MILP={sorted(milp_dict)}."
    )
    for clave, monto_lp in x_lp.items():
        monto_milp = milp_dict[clave]
        assert abs(monto_lp - monto_milp) <= tol * max(1.0, abs(monto_milp)), (
            f"Monto distinto en {clave}: LP={monto_lp:,.2f} vs MILP={monto_milp:,.2f}."
        )

    print(
        "\nVerificación OK: el LP restringido (z fijadas en z*) reproduce el "
        "objetivo y la asignación del MILP. La fijación de binarias es correcta "
        "y el LP es base válida para dualidad/sensibilidad (Tareas 6.2/6.3)."
    )

    # ------------------------------------------------------------------
    # 4) Dual y precios sombra (Tarea 6.2): extraer λ*, μ_i*, σ* e interpretar.
    # ------------------------------------------------------------------
    print("\n== Dual del LP restringido y precios sombra (Tarea 6.2) ==")
    precios = extraer_precios_sombra(lp, resolver_si_necesario=False)

    print(f"Estado dual        : {precios.estado}")
    print(f"Objetivo LP (f)    : {precios.objetivo:,.6f}")
    lam = precios.lambda_capital
    print(f"λ* (capital)       : {lam:.8f}" if lam is not None else "λ* (capital)       : N/D")
    print(f"μ_i* (concentr.)   : "
          f"{ {b: round(v, 8) for b, v in precios.mu_concentracion.items()} }")
    print(f"σ* (liquidez)      : "
          f"{ {e: round(v, 8) for e, v in precios.sigma_liquidez.items()} }")
    print(f"s_0*               : {precios.s0_valor:,.2f} "
          f"(capital agotado: {precios.capital_agotado})")

    print("\nInterpretación económica (Req. 4.3):")
    for clave in ("lambda",):
        if clave in precios.interpretacion:
            print(f"  - {precios.interpretacion[clave]}")
    for banco in precios.mu_concentracion:
        print(f"  - {precios.interpretacion[f'mu:{banco}']}")
    for etiqueta in precios.sigma_liquidez:
        print(f"  - {precios.interpretacion[f'sigma:{etiqueta}']}")
    print(f"  - {precios.interpretacion['s0_lambda']}")

    # --- Verificación de precios sombra (Tarea 6.2) ------------------------
    # Objetivo del dual debe coincidir con el del LP primal (dualidad fuerte).
    assert precios.es_optimo, "El LP restringido no fue óptimo al leer el dual."
    assert precios.objetivo is not None and abs(
        precios.objetivo - objetivo_lp
    ) <= tol * max(1.0, abs(objetivo_lp)), (
        f"El objetivo leído por el dual ({precios.objetivo:,.6f}) no coincide "
        f"con el del LP primal ({objetivo_lp:,.6f})."
    )

    # μ_i* ≥ 0 (restricciones de concentración son ≤): el signo debe ser válido.
    for banco, mu in precios.mu_concentracion.items():
        assert mu >= -tol, (
            f"μ_{banco}* = {mu:.8f} es negativo; viola el signo del dual de una "
            "restricción ≤ (concentración)."
        )

    # Relación s_0* ↔ λ* por holgura complementaria: s_0*·λ* ≈ 0.
    if lam is not None:
        assert abs(precios.s0_valor * lam) <= tol * max(1.0, datos.A), (
            f"Falla la complementariedad s_0*·λ* = {precios.s0_valor * lam:.6e} "
            "(debería ser ≈ 0)."
        )

    # Sanity check del fixture: con s_0* > 0 (sobró capital), λ* debe ser ≈ 0.
    if not precios.capital_agotado:
        assert lam is not None and abs(lam) <= 1e-6, (
            f"Con s_0* = {precios.s0_valor:,.2f} > 0 se esperaba λ* ≈ 0, pero "
            f"λ* = {lam:.8f}. Rompe la lectura de complementariedad."
        )
        print(
            f"\nSanity check OK: s_0* = {precios.s0_valor:,.2f} > 0 ⇒ λ* ≈ 0 "
            f"(λ* = {lam:.8f}). Sobró capital, luego el capital adicional no "
            "agrega retorno (complementariedad)."
        )
    else:
        print(
            f"\nSanity check OK: s_0* ≈ 0 (capital agotado) ⇒ λ* = {lam:.8f} "
            "revela el valor marginal del capital."
        )

    print(
        "\nVerificación OK (Tarea 6.2): el dual del LP restringido se resolvió, "
        "se extrajeron λ* (capital), μ_i* (concentración) y σ* (liquidez), su "
        "interpretación económica quedó documentada y la relación s_0*↔λ* por "
        "holgura complementaria se cumple. (Rangos y verificación global de "
        "holgura complementaria: Tarea 6.3.)"
    )

    # ------------------------------------------------------------------
    # 5) Holgura complementaria (Tarea 6.3, Req. 4.4): (x*)^T s* = 0.
    # ------------------------------------------------------------------
    print("\n== Holgura complementaria (Tarea 6.3, Req. 4.4) ==")
    hc = verificar_holgura_complementaria(lp)
    print(f"Cumple             : {hc.cumple}")
    print(f"Máx. violación     : {hc.max_violacion:.2e} (tol {hc.tolerancia:.0e})")
    print(f"Σ dj_v·(v−cota)    : {hc.producto_global:.2e}")
    print("Términos más holgados (top 3):")
    for t in hc.terminos[:3]:
        print(
            f"  - [{t.tipo}] {t.nombre}: "
            f"({t.factor_a:.4g})·({t.factor_b:.4g}) = {t.producto:.2e}"
        )
    print(f"Interpretación     : {hc.interpretacion}")

    assert hc.cumple, (
        f"La holgura complementaria no se cumple: máx. violación "
        f"{hc.max_violacion:.2e} > tol {hc.tolerancia:.0e}."
    )

    # ------------------------------------------------------------------
    # 6) Rangos de sensibilidad (Tarea 6.3, Req. 4.5 y 4.6).
    # ------------------------------------------------------------------
    print("\n== Rangos de sensibilidad (Tarea 6.3, Req. 4.5 y 4.6) ==")
    rangos = calcular_rangos_sensibilidad(lp)
    print(f"Degenerado         : {rangos.degenerado}")
    if rangos.advertencia_degeneracion:
        print(f"  {rangos.advertencia_degeneracion}")
    print(f"Método             : {rangos.metodo}")

    print("\nRangos de coeficientes objetivo f_ijk (Req. 4.5):")
    for clave, rango in rangos.objetivo_f.items():
        print(
            f"  - {clave}: f = {rango.valor_base:.6f} | "
            f"rango [{rango.limite_inferior:.6f}, {rango.limite_superior:.6f}] | "
            f"baja≤{rango.permitido_bajar:.6f}, sube≤{rango.permitido_subir:.6f}"
        )

    print("\nRangos de RHS b (A y p_i·A) (Req. 4.6):")
    for nombre, rango in rangos.rhs.items():
        print(
            f"  - {nombre}: b = {rango.valor_base:,.2f} | "
            f"rango [{rango.limite_inferior:,.2f}, {rango.limite_superior:,.2f}] | "
            f"baja≤{rango.permitido_bajar:,.2f}, sube≤{rango.permitido_subir:,.2f}"
        )

    # --- Verificación de rangos: no vacíos y coherentes -------------------
    assert rangos.objetivo_f, "No se calculó ningún rango de coeficiente objetivo."
    assert rangos.rhs, "No se calculó ningún rango de RHS."
    for clave, rango in rangos.objetivo_f.items():
        assert rango.limite_inferior <= rango.valor_base <= rango.limite_superior, (
            f"El valor base de f{clave} queda fuera de su rango "
            f"[{rango.limite_inferior}, {rango.limite_superior}]."
        )
        assert rango.permitido_bajar >= -1e-9 and rango.permitido_subir >= -1e-9, (
            f"Holguras de f{clave} con signo inválido."
        )
    for nombre, rango in rangos.rhs.items():
        assert rango.limite_inferior <= rango.valor_base <= rango.limite_superior, (
            f"El valor base del RHS '{nombre}' queda fuera de su rango."
        )

    # El LP quedó re-resuelto a óptimo tras restaurar objetivo y RHS.
    assert lp.problema.status == pulp.LpStatusOptimal, (
        "El LP no quedó en óptimo tras restaurar los parámetros perturbados."
    )

    print(
        "\nVerificación OK (Tarea 6.3): (x*)^T s* = 0 se cumple dentro de "
        "tolerancia, y se calcularon los rangos de estabilidad de los "
        "coeficientes f_ijk y del RHS (A y p_i·A). Esto completa sensitivity.py "
        "(dualidad, precios sombra, holgura complementaria y rangos)."
    )
