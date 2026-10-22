"""Orquestación del flujo completo del modelo de CDT — `main.py` (Tarea 8).

Este script encadena, de principio a fin y sin pasos manuales ocultos, las
cinco etapas del pipeline descrito en `design.md`:

    carga → modelo → solución → sensibilidad → reporte

Cada etapa reutiliza, sin duplicar lógica, los módulos ya implementados:

- `data_loader.cargar_datos`     → lee `data/cdt_productos.csv` + `data/config.py`
  y entrega un `DatosCDT` validado (Req. 6.1).
- `model.construir_modelo` + `agregar_restricciones_tramos` +
  `agregar_restricciones_riesgo` → arma el MILP con PuLP.
- `solver.resolver`              → resuelve el MILP y reporta solver/estado
  (Req. 6.2).
- `report.imprimir_reporte_asignacion` → tabla de asignación óptima (Req. 6.3).
- `sensitivity.*` + `report.exportar_informe_dualidad_sensibilidad` → informe de
  dualidad y sensibilidad exportado a `results/` (Req. 6.4).

Objetivo de ejecución reproducible (Req. 6.5)
---------------------------------------------
Se puede correr tal cual en Windows/PowerShell con Python 3.12:

    python src\\main.py

No hay argumentos obligatorios: toma los datos reales de `data/` por defecto.

Manejo de errores (design.md, sección "Manejo de errores")
----------------------------------------------------------
`main` convierte cada situación anómala en un mensaje claro y un código de
salida distinto de cero, en lugar de dejar que una excepción aborte el proceso:

1. **Datos faltantes/inconsistentes:** `data_loader` lanza `DataLoaderError`;
   se captura y se informa la causa (Req. 6.1).
2. **Sin combinaciones utilizables:** la matriz real deja `tasa_ea` vacía en
   todas las filas (principio de cero invención de datos), por lo que
   `datos.combinaciones` queda VACÍO. En ese caso no hay modelo que resolver:
   se imprime un mensaje accionable indicando al equipo que fije tasas
   supuestas explícitas en `data/cdt_productos.csv` (apoyándose en
   `info["excluidos_sin_tasa"]`) y se termina con elegancia, sin rastrear una
   excepción.
3. **Estados no óptimos del solver (infeasible/unbounded/no resuelto):** no se
   fuerza un resultado; se informa el estado y la causa probable y se omiten la
   sensibilidad y la exportación (que requieren `z*` de un óptimo).

Codificación UTF-8 en Windows/PowerShell (Req. 6.5)
---------------------------------------------------
La consola por defecto de Windows (cp1252) no puede codificar los símbolos del
reporte (`Σ`, `≈`, `·`, `≤`, `λ`, `μ`, `σ`). Se reconfigura `stdout`/`stderr` a
UTF-8 al inicio para evitar `UnicodeEncodeError`, el mismo patrón ya usado en
`solver.py` y `report.py`.
"""

from __future__ import annotations

import sys

# ---------------------------------------------------------------------------
# Codificación UTF-8 de la consola ANTES de cualquier impresión (Req. 6.5).
# La consola por defecto de Windows (cp1252) no puede codificar los símbolos
# del reporte (Σ, ≈, ·, ≤, λ, μ, σ); reconfigurar evita UnicodeEncodeError.
# ---------------------------------------------------------------------------
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from data_loader import DataLoaderError, DatosCDT, cargar_datos
from model import (
    agregar_restricciones_riesgo,
    agregar_restricciones_tramos,
    construir_modelo,
)
from report import (
    exportar_informe_dualidad_sensibilidad,
    imprimir_reporte_asignacion,
)
from sensitivity import (
    calcular_rangos_sensibilidad,
    construir_lp_restringido,
    extraer_precios_sombra,
    verificar_holgura_complementaria,
)
from solver import resolver


# Códigos de salida: 0 = éxito; distintos de 0 = distintas causas de parada.
EXIT_OK = 0
EXIT_ERROR_DATOS = 1          # DataLoaderError u otra inconsistencia de carga.
EXIT_SIN_COMBINACIONES = 2    # Matriz sin tasas utilizables (cero invención).
EXIT_SOLVER_NO_OPTIMO = 3     # El MILP no alcanzó una solución óptima.


def _clave_a_texto(clave: tuple[str, int, int]) -> str:
    """Formatea una clave `(banco, plazo, tramo)` para mensajes legibles."""
    banco, plazo, tramo = clave
    return f"{banco} / plazo {plazo}d / tramo {tramo}"


def _imprimir_encabezado_carga(datos: DatosCDT) -> None:
    """Imprime un resumen de la carga de datos (trazabilidad de la etapa 1)."""
    info = datos.info
    print("=" * 68)
    print("  MODELO DE OPTIMIZACIÓN DE INVERSIÓN EN CDT (Colombia)")
    print("=" * 68)
    print("ETAPA 1/5 — Carga y validación de datos")
    print(f"  Archivo de datos        : {info.get('archivo_datos')}")
    print(f"  Capital A               : {datos.A:,.0f}")
    print(f"  Filas totales           : {info.get('total_filas')}")
    print(f"  No disponibles          : {len(info.get('excluidos_no_disponibles', []))}")
    print(f"  Disponibles sin tasa    : {len(info.get('excluidos_sin_tasa', []))}")
    print(f"  Marcadas como supuesto  : {len(info.get('supuestos', []))}")
    print(f"  Combinaciones utilizables: {info.get('combinaciones_utilizables')}")


def _mensaje_sin_combinaciones(datos: DatosCDT) -> None:
    """Explica, de forma accionable, por qué no hay nada que optimizar.

    La matriz real deja `tasa_ea` vacía en todas las filas por el principio de
    cero invención de datos (ver `data_loader`), por lo que ninguna combinación
    `(i, j, k)` es utilizable. En vez de construir un modelo vacío (que no tiene
    solución significativa), se guía al equipo para fijar tasas supuestas.
    """
    excluidos = datos.info.get("excluidos_sin_tasa", [])
    print("\n" + "!" * 68)
    print("  NO HAY COMBINACIONES UTILIZABLES: no se puede construir el modelo.")
    print("!" * 68)
    print(
        "\nTodas las filas disponibles tienen la tasa (tasa_ea) VACÍA. Por el\n"
        "principio de cero invención de datos, el cargador NO inventa tasas y\n"
        "excluye esas filas del modelo. Sin ninguna tasa utilizable no hay\n"
        "función objetivo que optimizar."
    )
    print(
        f"\nFilas disponibles excluidas por falta de tasa: {len(excluidos)}."
    )
    if excluidos:
        print("Ejemplos de combinaciones sin tasa (primeras 5):")
        for clave in excluidos[:5]:
            print(f"  - {_clave_a_texto(clave)}")
    print(
        "\nACCIÓN REQUERIDA:\n"
        "  1. Abra data/cdt_productos.csv.\n"
        "  2. Para las combinaciones (banco, plazo, tramo) que desee modelar,\n"
        "     fije una tasa efectiva anual supuesta en la columna 'tasa_ea'\n"
        "     (fracción, p. ej. 0.11 para 11% E.A.) y mantenga es_supuesto=True\n"
        "     para que el informe la señale como supuesta.\n"
        "  3. Vuelva a ejecutar:  python src\\main.py"
    )


def _mensaje_solver_no_optimo(estado: str) -> None:
    """Informa un estado no óptimo del solver y su causa probable (Req. 6.2).

    Sigue la sección "Manejo de errores" de design.md: no se fuerza un
    resultado; se reporta el estado tal cual y se apunta a las restricciones
    que suelen provocarlo.
    """
    print("\n" + "!" * 68)
    print(f"  EL SOLVER NO ALCANZÓ UNA SOLUCIÓN ÓPTIMA (estado: {estado}).")
    print("!" * 68)
    if estado == "Infeasible":
        print(
            "\nEl modelo es INFACTIBLE. La holgura de no-inversión s_0 absorbe el\n"
            "capital no colocable, así que la restricción de capital por sí sola\n"
            "no genera infactibilidad. La causa probable son restricciones\n"
            "incompatibles entre sí, típicamente:\n"
            "  - cotas de liquidez (L_corto/U_corto/L_largo/U_largo) que no se\n"
            "    pueden satisfacer junto con la concentración máxima por banco;\n"
            "  - mínimos de apertura demasiado altos frente a los topes p_i·A.\n"
            "Revise data/config.py (liquidez, concentracion_max) y los mínimos\n"
            "de apertura de data/cdt_productos.csv."
        )
    elif estado == "Unbounded":
        print(
            "\nEl modelo es NO ACOTADO. Esto no debería ocurrir con la igualdad de\n"
            "capital Σx + s_0 = A, que acota el total colocado. Revise que las\n"
            "cotas de tramo y la restricción de capital estén presentes."
        )
    else:
        print(
            "\nEstado no concluyente (p. ej. 'Not Solved' o 'Undefined'). Revise\n"
            "la instalación del solver (CBC viene con PuLP) y los datos de entrada."
        )
    print(
        "\nNo se ejecutan la sensibilidad ni la exportación: ambas requieren la\n"
        "solución óptima (z*) del MILP para fijar las binarias (Req. 4.1)."
    )


def ejecutar() -> int:
    """Ejecuta el pipeline completo y devuelve un código de salida.

    Retorna
    -------
    int
        `EXIT_OK` (0) si todo el flujo terminó bien; un código distinto de cero
        describiendo la causa de parada en caso contrario (ver constantes
        `EXIT_*`).
    """
    # --- ETAPA 1/5: carga y validación de datos (Req. 6.1) -----------------
    try:
        datos = cargar_datos()
    except DataLoaderError as err:
        print("=" * 68)
        print("  ERROR DE CARGA DE DATOS")
        print("=" * 68)
        print(f"\n{err}")
        print(
            "\nRevise data/cdt_productos.csv y data/config.py (columnas, tipos,\n"
            "rangos y coherencia de los límites de tramo) y vuelva a ejecutar."
        )
        return EXIT_ERROR_DATOS

    _imprimir_encabezado_carga(datos)

    # Sin combinaciones utilizables: parada elegante y accionable (no es error
    # de datos, es un estado esperado con la matriz real de tasas vacías).
    if not datos.combinaciones:
        _mensaje_sin_combinaciones(datos)
        return EXIT_SIN_COMBINACIONES

    # --- ETAPA 2/5: construcción del modelo MILP ---------------------------
    print("\nETAPA 2/5 — Construcción del modelo MILP (PuLP)")
    modelo = construir_modelo(datos)
    agregar_restricciones_tramos(modelo)
    agregar_restricciones_riesgo(modelo)
    print(
        f"  Variables x_ijk: {len(modelo.x)} | z_ijk: {len(modelo.z)} | "
        f"restricciones: {len(modelo.problema.constraints)}"
    )

    # --- ETAPA 3/5: resolución del MILP (Req. 6.2) -------------------------
    print("\nETAPA 3/5 — Resolución del MILP")
    resultado = resolver(modelo)
    print(f"  Solver: {resultado.solver} | Estado: {resultado.estado}")

    # Estado no óptimo: se informa y se detiene antes de sensibilidad/export.
    if not resultado.es_optimo:
        _mensaje_solver_no_optimo(resultado.estado)
        # Se imprime igualmente el encabezado del reporte (que indica que no
        # hubo óptimo) para dejar constancia en consola.
        print()
        imprimir_reporte_asignacion(resultado, modelo)
        return EXIT_SOLVER_NO_OPTIMO

    # --- ETAPA 4/5: reporte de la asignación óptima (Req. 6.3) -------------
    print("\nETAPA 4/5 — Asignación óptima\n")
    imprimir_reporte_asignacion(resultado, modelo)

    # --- ETAPA 5/5: dualidad, sensibilidad y exportación (Req. 6.4) --------
    print("\nETAPA 5/5 — Dualidad, sensibilidad y exportación a results/")
    lp = construir_lp_restringido(datos, resultado)
    precios = extraer_precios_sombra(lp)
    holgura = verificar_holgura_complementaria(lp)
    rangos = calcular_rangos_sensibilidad(lp)

    rutas = exportar_informe_dualidad_sensibilidad(precios, holgura, rangos)
    print("  Informe exportado:")
    for clave, ruta in rutas.items():
        print(f"    {clave:12s}: {ruta}")

    print("\n" + "=" * 68)
    print("  FLUJO COMPLETADO: carga → modelo → solución → sensibilidad → reporte")
    print("=" * 68)
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(ejecutar())
