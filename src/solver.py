"""Resolución del MILP de inversión en CDT — `solver.py` (Tarea 5).

Este módulo toma el `ModeloCDT` ya construido por `model.py` (variables,
objetivo y las ocho familias de restricciones) y lo **resuelve** con PuLP,
reportando el solver empleado y el estado de la optimización, y extrayendo la
solución óptima a una estructura de resultados cómoda de inspeccionar y de
pasar a `report.py`.

¿Por qué un módulo aparte y no una función en `model.py`?
---------------------------------------------------------
`model.py` tiene una única responsabilidad: **construir** el problema
(variables, objetivo, restricciones). La resolución y la extracción de la
solución son una etapa distinta del flujo (`carga → modelo → solución →
sensibilidad → reporte`, ver `design.md`). Separar `solver.py` mantiene cada
módulo enfocado, evita que `model.py` dependa del ciclo de vida del solver y
permite que `sensitivity.py` (Tarea 6) reutilice `construir_modelo` sin arrastrar
lógica de resolución. La estructura de resultados (`ResultadoCDT`) es el
contrato estable entre la resolución y el reporte.

Qué extrae (Requisitos 3.2, 6.2, 6.3)
-------------------------------------
- `x*`   : monto óptimo por combinación `(i, j, k)` (solo las activas, `x>0`).
- `z*`   : binarias de activación de tramo en el óptimo.
- `s_0*` : holgura de no-inversión (capital que quedó sin colocar, Req. 3.2).
- `Z*`   : valor de la función objetivo de producción `Σ f_ijk·x_ijk`.
- estado y nombre del solver, para trazabilidad del resultado (Req. 6.2).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import pulp

from model import ModeloCDT


# ---------------------------------------------------------------------------
# Estructura de resultados (contrato con report.py / sensitivity.py)
# ---------------------------------------------------------------------------
@dataclass
class ResultadoCDT:
    """Solución óptima del MILP extraída del `ModeloCDT` resuelto.

    Atributos
    ---------
    estado:
        Estado del solver en texto (`pulp.LpStatus[...]`): `Optimal`,
        `Infeasible`, `Unbounded`, `Not Solved`, `Undefined`.
    estado_codigo:
        Código numérico del estado (`problema.status`), por si el llamador
        necesita comparar programáticamente.
    es_optimo:
        `True` solo si el solver alcanzó una solución óptima.
    solver:
        Nombre del solver realmente usado (p. ej. `PULP_CBC_CMD`), para dejar
        trazabilidad del resultado (Req. 6.2).
    objetivo:
        Valor de la función objetivo de producción `Z* = Σ f_ijk·x_ijk`.
    objetivo_r:
        Valor de la variante didáctica `Σ r_ijk·x_ijk` evaluada en `x*`
        (contraste, Req. 2.6). No es lo que se optimiza.
    x:
        `{(i, j, k): x*_ijk}` SOLO para las combinaciones con monto > 0 (las
        activas). Las no colocadas se omiten para una lectura limpia.
    z:
        `{(i, j, k): 0/1}` para todas las combinaciones del modelo.
    s0:
        Holgura de no-inversión `s_0*` (capital sin colocar, Req. 3.2).
    capital_colocado:
        Σ x*_ijk (capital efectivamente invertido).
    """

    estado: str
    estado_codigo: int
    es_optimo: bool
    solver: str
    objetivo: Optional[float]
    objetivo_r: Optional[float]
    x: dict[tuple[str, int, int], float] = field(default_factory=dict)
    z: dict[tuple[str, int, int], int] = field(default_factory=dict)
    s0: float = 0.0
    capital_colocado: float = 0.0


# Tolerancias de extracción (coherentes con las verificaciones de model.py).
_TOL_MONTO = 1e-4   # por debajo de esto, se considera x = 0
_TOL_BINARIA = 0.5  # umbral para redondear z continua del relajado a {0,1}


def resolver(
    modelo: ModeloCDT,
    solver: Optional[pulp.LpSolver] = None,
) -> ResultadoCDT:
    """Resuelve el MILP y extrae la solución óptima a un `ResultadoCDT`.

    Parámetros
    ----------
    modelo:
        El `ModeloCDT` ya construido con todas sus restricciones
        (`construir_modelo` + `agregar_restricciones_tramos` +
        `agregar_restricciones_riesgo`).
    solver:
        Solver de PuLP a usar. Por defecto `PULP_CBC_CMD(msg=False)` (el solver
        CBC que viene con PuLP), coherente con las verificaciones de `model.py`.

    Retorna
    -------
    `ResultadoCDT` con estado, solver, valor objetivo y `x*`, `z*`, `s_0*`.

    Notas
    -----
    No lanza excepción si el problema no es óptimo: deja el estado en el
    resultado (`es_optimo=False`) para que el llamador (`main`/`report`) decida
    cómo informarlo. Esto respeta el principio de "no forzar un resultado": si
    el solver no encuentra óptimo, se reporta el estado tal cual (Req. 6.2).
    """
    if solver is None:
        solver = pulp.PULP_CBC_CMD(msg=False)

    modelo.problema.solve(solver)

    estado_codigo = modelo.problema.status
    estado = pulp.LpStatus[estado_codigo]
    es_optimo = estado == "Optimal"

    # Nombre del solver realmente empleado (trazabilidad, Req. 6.2).
    nombre_solver = type(solver).__name__

    datos = modelo.datos

    # --- Extracción de la solución -----------------------------------------
    # Si no hay óptimo, los .value() pueden ser None; se gestiona con 0.0 y se
    # deja claro el estado para que el reporte no invente una asignación.
    x_opt: dict[tuple[str, int, int], float] = {}
    z_opt: dict[tuple[str, int, int], int] = {}
    capital_colocado = 0.0

    for clave in datos.combinaciones:
        xv = modelo.x[clave].value()
        zv = modelo.z[clave].value()
        xv = 0.0 if xv is None else float(xv)
        zv = 0.0 if zv is None else float(zv)

        z_opt[clave] = 1 if zv > _TOL_BINARIA else 0
        # Solo se guardan los montos efectivamente colocados (x > 0).
        if xv > _TOL_MONTO:
            x_opt[clave] = xv
            capital_colocado += xv

    s0_val = modelo.s0.value()
    s0_val = 0.0 if s0_val is None else float(s0_val)

    # Valor objetivo de producción (f_ijk) y la variante r_ijk para contraste.
    objetivo = pulp.value(modelo.problema.objective)
    objetivo = None if objetivo is None else float(objetivo)
    objetivo_r = pulp.value(modelo.objetivo_r)
    objetivo_r = None if objetivo_r is None else float(objetivo_r)

    return ResultadoCDT(
        estado=estado,
        estado_codigo=estado_codigo,
        es_optimo=es_optimo,
        solver=nombre_solver,
        objetivo=objetivo,
        objetivo_r=objetivo_r,
        x=x_opt,
        z=z_opt,
        s0=s0_val,
        capital_colocado=capital_colocado,
    )


# ---------------------------------------------------------------------------
# Autocomprobación de humo (sin framework): resuelve el fixture sintético.
# El fixture vive en model.py porque los datos reales dejan las tasas vacías
# (principio de cero invención); así se verifica el solve de punta a punta sin
# inventar tasas del problema real. Ejecutar con:  python src/solver.py
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    # La consola por defecto de Windows (cp1252) no puede codificar los
    # símbolos del resumen (Σ, ·). Forzar UTF-8 en stdout evita un
    # UnicodeEncodeError al ejecutar la autocomprobación en PowerShell.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    from model import (
        _datos_sinteticos,
        agregar_restricciones_riesgo,
        agregar_restricciones_tramos,
        construir_modelo,
    )

    modelo = construir_modelo(_datos_sinteticos())
    agregar_restricciones_tramos(modelo)
    agregar_restricciones_riesgo(modelo)

    resultado = resolver(modelo)

    print("== Resolución del MILP de CDT (Tarea 5) ==")
    print(f"Solver   : {resultado.solver}")
    print(f"Estado   : {resultado.estado} (código {resultado.estado_codigo})")
    print(f"Óptimo   : {resultado.es_optimo}")
    print(f"Objetivo : {resultado.objetivo:,.4f}" if resultado.objetivo is not None else "Objetivo : N/D")
    print(f"Σx*      : {resultado.capital_colocado:,.2f}")
    print(f"s_0*     : {resultado.s0:,.2f}")
    print(f"Activas  : {sorted(resultado.x.items())}")
