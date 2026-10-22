"""Reporte de la asignación óptima de CDT — `report.py` (Tarea 5).

Este módulo presenta la solución del MILP (la que extrae `solver.resolver` en
un `ResultadoCDT`) de forma legible para el usuario:

- Una **tabla de asignación** agrupada por banco, plazo y tramo, con el monto
  colocado `x*_ijk`, la tasa `r_ijk` y el rendimiento efectivo del periodo
  (`f_ijk·x*_ijk`, el aporte de esa línea al objetivo).
- Un **resumen** del estado del solver y del valor objetivo (Req. 6.2, 6.3).
- El **destaque de capital no colocado** cuando `s_0* > 0` (Req. 3.2): se
  reporta explícitamente cuánto capital quedó sin invertir y qué fracción de
  `A` representa.

Se usa pandas para construir la tabla (está en `requirements.txt`): facilita el
ordenamiento por banco/plazo/tramo, el formateo de columnas y una posible
exportación posterior a CSV/Markdown en la Tarea 7. El renglón de totales se
añade para cuadrar visualmente `Σx* + s_0* = A`.

Este módulo crece en la Tarea 7 (exportar el informe de dualidad/sensibilidad a
`results/`). Aquí solo se cubre la tabla de asignación y el destaque de `s_0`.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

import pandas as pd

from model import ModeloCDT
from sensitivity import (
    HolguraComplementaria,
    PreciosSombra,
    RangosSensibilidad,
    clave_a_texto,
)
from solver import ResultadoCDT


# Tolerancia para considerar que s_0 es estrictamente positivo (capital sin
# colocar). Coherente con la tolerancia de montos del solver.
_TOL_S0 = 1e-4

# Carpeta de salida del informe (Requisito 6.4): se exporta a `results/` en la
# raíz del proyecto, no dentro de `src/`.
_DIR_RESULTS = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results")
)


def construir_tabla_asignacion(
    resultado: ResultadoCDT,
    modelo: ModeloCDT,
) -> pd.DataFrame:
    """Arma el `DataFrame` de asignación por banco, plazo y tramo.

    Incluye SOLO las combinaciones con monto colocado (`x* > 0`, las activas),
    ordenadas por banco, plazo y tramo. Para cada línea calcula:

    - `tasa_ea`     : la tasa efectiva anual `r_ijk` del producto.
    - `f_ijk`       : el factor de rendimiento efectivo del periodo.
    - `monto`       : el capital asignado `x*_ijk`.
    - `rendimiento` : `f_ijk · x*_ijk`, el aporte de la línea al objetivo `Z*`.
    - `pct_capital` : fracción del capital total `A` colocada en esa línea.

    Parámetros
    ----------
    resultado:
        `ResultadoCDT` con la solución óptima (de `solver.resolver`).
    modelo:
        `ModeloCDT` de origen, del que se leen los parámetros `r`, `f` y `A`.

    Retorna
    -------
    `pd.DataFrame` con una fila por combinación activa. Si no hay ninguna
    (p. ej. todo quedó en `s_0`), devuelve un DataFrame vacío con las columnas
    esperadas.
    """
    datos = modelo.datos
    columnas = [
        "banco",
        "plazo_dias",
        "tramo",
        "monto",
        "tasa_ea",
        "f_ijk",
        "rendimiento",
        "pct_capital",
    ]

    filas: list[dict[str, object]] = []
    for clave in sorted(resultado.x):
        banco, plazo, tramo = clave
        monto = resultado.x[clave]
        r_ijk = datos.r[clave]
        f_ijk = datos.f[clave]
        filas.append(
            {
                "banco": banco,
                "plazo_dias": plazo,
                "tramo": tramo,
                "monto": monto,
                "tasa_ea": r_ijk,
                "f_ijk": f_ijk,
                "rendimiento": f_ijk * monto,
                "pct_capital": (monto / datos.A) if datos.A else 0.0,
            }
        )

    df = pd.DataFrame(filas, columns=columnas)
    if not df.empty:
        df = df.sort_values(
            ["banco", "plazo_dias", "tramo"], ignore_index=True
        )
    return df


def _formatear_tabla(df: pd.DataFrame) -> str:
    """Devuelve una representación de texto legible de la tabla de asignación.

    Formatea montos con separador de miles y las tasas/porcentajes como
    porcentaje, sin alterar el DataFrame original (se formatea una copia).
    """
    if df.empty:
        return "(sin combinaciones activas: todo el capital quedó sin colocar)"

    vista = df.copy()
    vista["monto"] = vista["monto"].map(lambda v: f"{v:,.2f}")
    vista["tasa_ea"] = vista["tasa_ea"].map(lambda v: f"{v * 100:.2f}%")
    vista["f_ijk"] = vista["f_ijk"].map(lambda v: f"{v * 100:.4f}%")
    vista["rendimiento"] = vista["rendimiento"].map(lambda v: f"{v:,.2f}")
    vista["pct_capital"] = vista["pct_capital"].map(lambda v: f"{v * 100:.2f}%")
    return vista.to_string(index=False)


def imprimir_reporte_asignacion(
    resultado: ResultadoCDT,
    modelo: ModeloCDT,
) -> pd.DataFrame:
    """Imprime el reporte completo de la asignación óptima y lo devuelve.

    Secciones impresas:
      1. Encabezado con solver, estado y valor objetivo (Req. 6.2, 6.3).
      2. Tabla de asignación por banco/plazo/tramo (Req. 6.3).
      3. Totales: capital colocado, `s_0*` y verificación `Σx* + s_0* = A`.
      4. Destaque de capital no colocado si `s_0* > 0` (Req. 3.2).

    Si el solver no alcanzó un óptimo, lo informa y NO fabrica una asignación
    (coherente con el principio de no forzar resultados).

    Retorna
    -------
    El `DataFrame` de asignación (por si el llamador quiere exportarlo).
    """
    datos = modelo.datos

    print("=" * 68)
    print("  ASIGNACIÓN ÓPTIMA DE INVERSIÓN EN CDT")
    print("=" * 68)
    print(f"Solver            : {resultado.solver}")
    print(f"Estado            : {resultado.estado}")

    # Si no hay óptimo, se informa y se detiene el reporte de asignación.
    if not resultado.es_optimo:
        print(
            "\nEl solver NO alcanzó una solución óptima; no se reporta "
            "asignación. Revise los datos y las restricciones del modelo."
        )
        return construir_tabla_asignacion(resultado, modelo)

    if resultado.objetivo is not None:
        print(f"Valor objetivo Z* : {resultado.objetivo:,.2f}  (Σ f_ijk·x*_ijk)")
    if resultado.objetivo_r is not None:
        print(
            f"Variante Σr·x*    : {resultado.objetivo_r:,.2f}  "
            "(contraste didáctico, no optimizado)"
        )
    print(f"Capital total A   : {datos.A:,.2f}")

    # --- Tabla de asignación ------------------------------------------------
    df = construir_tabla_asignacion(resultado, modelo)
    print("\n-- Asignación por banco / plazo / tramo " + "-" * 28)
    print(_formatear_tabla(df))

    # --- Totales y verificación de capital ---------------------------------
    colocado = resultado.capital_colocado
    s0 = resultado.s0
    print("\n-- Totales " + "-" * 57)
    print(f"Capital colocado Σx*  : {colocado:,.2f}")
    print(f"Capital no colocado s_0* : {s0:,.2f}")
    print(f"Σx* + s_0*            : {colocado + s0:,.2f}  (A = {datos.A:,.2f})")

    # --- Destaque de capital no colocado (Req. 3.2) ------------------------
    if s0 > _TOL_S0:
        pct = (s0 / datos.A * 100) if datos.A else 0.0
        print("\n" + "!" * 68)
        print(
            f"  CAPITAL NO COLOCADO: {s0:,.2f} "
            f"({pct:.2f}% de A) quedó sin invertir (s_0* > 0)."
        )
        print(
            "  Las restricciones activas (mínimos de apertura, concentración\n"
            "  o cotas de liquidez) impiden colocar más capital con retorno."
        )
        print("!" * 68)
    else:
        print("\nTodo el capital fue colocado (s_0* ≈ 0).")

    return df


# ---------------------------------------------------------------------------
# Exportación del informe de dualidad y sensibilidad (Tarea 7, Req. 6.4)
# ---------------------------------------------------------------------------
#
# Esta sección exporta a `results/` el análisis dual y de sensibilidad que
# producen las Tareas 6.2 y 6.3 de `sensitivity.py`:
#
#   - precios sombra λ* (capital), μ_i* (concentración) y σ* (liquidez),
#   - su interpretación económica (Req. 4.3),
#   - los rangos de sensibilidad de los coeficientes objetivo `f_ijk` y de los
#     RHS (capital `A` y topes `p_i·A`) (Req. 4.5 y 4.6),
#   - la verificación de la holgura complementaria `(x*)^T s* = 0` (Req. 4.4).
#
# ADVERTENCIA TRANSVERSAL (Req. 4.7): TODO el análisis aquí exportado se refiere
# al LP RESTRINGIDO (binarias fijadas en z*), NO al MILP original. El encabezado
# del informe lo deja explícito y, si el LP es degenerado, se añade la
# advertencia correspondiente (design.md).


def _fmt_num(valor: Optional[float], decimales: int = 8) -> str:
    """Formatea un número para el informe, tratando `None` e infinitos."""
    if valor is None:
        return "N/D"
    if valor == float("inf"):
        return "+∞"
    if valor == float("-inf"):
        return "−∞"
    return f"{valor:.{decimales}f}"


def _fmt_money(valor: Optional[float]) -> str:
    """Formatea un monto con separador de miles (o `None`/∞)."""
    if valor is None:
        return "N/D"
    if valor == float("inf"):
        return "+∞"
    if valor == float("-inf"):
        return "−∞"
    return f"{valor:,.2f}"


def construir_markdown_dualidad_sensibilidad(
    precios: PreciosSombra,
    holgura: HolguraComplementaria,
    rangos: RangosSensibilidad,
    titulo: str = "Informe de dualidad y análisis de sensibilidad",
) -> str:
    """Construye el texto Markdown del informe de dualidad y sensibilidad.

    Ensambla, a partir de los contratos de `sensitivity.py`, un documento
    Markdown con las secciones: advertencia del LP restringido (Req. 4.7),
    precios sombra con interpretación (Req. 4.2/4.3), rangos de sensibilidad
    (Req. 4.5/4.6) y verificación de holgura complementaria (Req. 4.4).

    Esta función NO toca disco (solo arma el texto): la escritura la hace
    `exportar_informe_dualidad_sensibilidad`. Separarlas facilita probar el
    contenido sin efectos secundarios.

    Parámetros
    ----------
    precios:
        `PreciosSombra` de `extraer_precios_sombra` (Tarea 6.2).
    holgura:
        `HolguraComplementaria` de `verificar_holgura_complementaria` (6.3).
    rangos:
        `RangosSensibilidad` de `calcular_rangos_sensibilidad` (6.3).
    titulo:
        Título del documento.

    Retorna
    -------
    El informe completo como cadena Markdown.
    """
    sello = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lineas: list[str] = []

    # --- Encabezado y advertencia del LP restringido (Req. 4.7) ------------
    lineas.append(f"# {titulo}")
    lineas.append("")
    lineas.append(f"_Generado: {sello}_")
    lineas.append("")
    lineas.append("> **ADVERTENCIA (Requisito 4.7).** Todo el análisis de este")
    lineas.append("> informe —precios sombra, interpretación económica, rangos de")
    lineas.append("> sensibilidad y holgura complementaria— se refiere al **LP")
    lineas.append("> restringido** que resulta de fijar las variables binarias en")
    lineas.append("> su valor óptimo `z = z*`, **NO al MILP original**. En un MILP")
    lineas.append("> las binarias rompen la convexidad y la dualidad fuerte no está")
    lineas.append("> definida; los precios sombra y rangos son rigurosos solo sobre")
    lineas.append("> este LP (binarias fijadas). Interpretar los resultados en ese")
    lineas.append("> marco.")
    lineas.append("")

    if rangos.degenerado and rangos.advertencia_degeneracion:
        lineas.append(f"> **DEGENERACIÓN.** {rangos.advertencia_degeneracion}")
        lineas.append("")

    # --- 1. Resumen del LP restringido -------------------------------------
    lineas.append("## 1. Estado del LP restringido")
    lineas.append("")
    lineas.append(f"- Estado del solver: `{precios.estado}`")
    lineas.append(f"- Óptimo alcanzado: `{precios.es_optimo}`")
    lineas.append(
        f"- Valor objetivo `Z* = Σ f_ijk·x*_ijk`: "
        f"**{_fmt_money(precios.objetivo)}**"
    )
    lineas.append(
        f"- Capital sin colocar `s_0*`: **{_fmt_money(precios.s0_valor)}** "
        f"(capital agotado: `{precios.capital_agotado}`)"
    )
    lineas.append("")

    # --- 2. Precios sombra (Req. 4.2) --------------------------------------
    lineas.append("## 2. Precios sombra (valores duales)")
    lineas.append("")
    lineas.append("| Recurso | Símbolo | Precio sombra |")
    lineas.append("| --- | --- | --- |")
    lineas.append(
        f"| Capital `Σx + s_0 = A` | `λ*` | {_fmt_num(precios.lambda_capital)} |"
    )
    for banco, mu in sorted(precios.mu_concentracion.items()):
        lineas.append(
            f"| Concentración banco {banco} `≤ p_i·A` | `μ_{banco}*` | "
            f"{_fmt_num(mu)} |"
        )
    for etiqueta, sigma in sorted(precios.sigma_liquidez.items()):
        lineas.append(
            f"| Liquidez `{etiqueta}` | `σ_{etiqueta}*` | {_fmt_num(sigma)} |"
        )
    if not precios.mu_concentracion and not precios.sigma_liquidez:
        lineas.append(
            "| _(sin topes de concentración/liquidez activos)_ | | |"
        )
    lineas.append("")

    # --- 3. Interpretación económica (Req. 4.3) ----------------------------
    lineas.append("## 3. Interpretación económica (Req. 4.3)")
    lineas.append("")
    # Orden estable: λ, luego μ por banco, luego σ por etiqueta, luego s0↔λ.
    orden: list[str] = ["lambda"]
    orden += [f"mu:{b}" for b in sorted(precios.mu_concentracion)]
    orden += [f"sigma:{e}" for e in sorted(precios.sigma_liquidez)]
    orden += ["s0_lambda"]
    for clave in orden:
        texto = precios.interpretacion.get(clave)
        if texto:
            lineas.append(f"- {texto}")
    lineas.append("")

    # --- 4. Rangos de sensibilidad (Req. 4.5 y 4.6) ------------------------
    lineas.append("## 4. Rangos de sensibilidad")
    lineas.append("")
    lineas.append(f"**Método.** {rangos.metodo}")
    lineas.append("")

    # 4.1 Coeficientes objetivo f_ijk (Req. 4.5)
    lineas.append("### 4.1 Coeficientes objetivo `f_ijk` (Req. 4.5)")
    lineas.append("")
    lineas.append(
        "| Combinación (i,j,k) | `f` base | Límite inferior | Límite superior "
        "| Baja ≤ | Sube ≤ |"
    )
    lineas.append("| --- | --- | --- | --- | --- | --- |")
    for clave, rango in sorted(
        rangos.objetivo_f.items(), key=lambda kv: clave_a_texto(kv[0])
    ):
        lineas.append(
            f"| `{clave_a_texto(clave)}` | {_fmt_num(rango.valor_base, 6)} | "
            f"{_fmt_num(rango.limite_inferior, 6)} | "
            f"{_fmt_num(rango.limite_superior, 6)} | "
            f"{_fmt_num(rango.permitido_bajar, 6)} | "
            f"{_fmt_num(rango.permitido_subir, 6)} |"
        )
    if not rangos.objetivo_f:
        lineas.append("| _(sin variables activas)_ | | | | | |")
    lineas.append("")

    # 4.2 Lado derecho (RHS): capital A y topes p_i·A (Req. 4.6)
    lineas.append("### 4.2 Lado derecho RHS: capital `A` y topes `p_i·A` (Req. 4.6)")
    lineas.append("")
    lineas.append(
        "| Recurso | RHS base | Límite inferior | Límite superior | Baja ≤ "
        "| Sube ≤ |"
    )
    lineas.append("| --- | --- | --- | --- | --- | --- |")
    for nombre, rango in rangos.rhs.items():
        lineas.append(
            f"| `{nombre}` | {_fmt_money(rango.valor_base)} | "
            f"{_fmt_money(rango.limite_inferior)} | "
            f"{_fmt_money(rango.limite_superior)} | "
            f"{_fmt_money(rango.permitido_bajar)} | "
            f"{_fmt_money(rango.permitido_subir)} |"
        )
    if not rangos.rhs:
        lineas.append("| _(no se calcularon rangos de RHS)_ | | | | | |")
    lineas.append("")
    lineas.append(
        "Dentro de cada intervalo la base óptima (y el precio sombra) se "
        "mantiene y la variación del objetivo es lineal: `Δobjetivo = π·Δb`."
    )
    lineas.append("")

    # --- 5. Holgura complementaria (Req. 4.4) ------------------------------
    lineas.append("## 5. Verificación de holgura complementaria (Req. 4.4)")
    lineas.append("")
    lineas.append(f"- Condición `(x*)^T s* = 0` verificada: **{holgura.cumple}**")
    lineas.append(
        f"- Máxima violación: `{holgura.max_violacion:.2e}` "
        f"(tolerancia `{holgura.tolerancia:.0e}`)"
    )
    lineas.append(
        f"- Producto global `Σ dj_v·(v−cota)`: `{holgura.producto_global:.2e}`"
    )
    lineas.append("")
    lineas.append(f"{holgura.interpretacion}")
    lineas.append("")
    lineas.append("Términos más holgados (mayor |producto| primero):")
    lineas.append("")
    lineas.append("| Tipo | Nombre | Factor A | Factor B | Producto |")
    lineas.append("| --- | --- | --- | --- | --- |")
    for termino in holgura.terminos[:10]:
        lineas.append(
            f"| {termino.tipo} | `{termino.nombre}` | "
            f"{termino.factor_a:.6g} | {termino.factor_b:.6g} | "
            f"{termino.producto:.2e} |"
        )
    lineas.append("")

    return "\n".join(lineas)


def _dataframe_precios_sombra(precios: PreciosSombra) -> pd.DataFrame:
    """Arma un `DataFrame` con los precios sombra (para exportación CSV)."""
    filas: list[dict[str, object]] = [
        {
            "recurso": "capital",
            "simbolo": "lambda",
            "etiqueta": "A",
            "precio_sombra": precios.lambda_capital,
        }
    ]
    for banco, mu in sorted(precios.mu_concentracion.items()):
        filas.append(
            {
                "recurso": "concentracion",
                "simbolo": "mu",
                "etiqueta": banco,
                "precio_sombra": mu,
            }
        )
    for etiqueta, sigma in sorted(precios.sigma_liquidez.items()):
        filas.append(
            {
                "recurso": "liquidez",
                "simbolo": "sigma",
                "etiqueta": etiqueta,
                "precio_sombra": sigma,
            }
        )
    return pd.DataFrame(
        filas, columns=["recurso", "simbolo", "etiqueta", "precio_sombra"]
    )


def _dataframe_rangos(rangos: RangosSensibilidad) -> pd.DataFrame:
    """Arma un `DataFrame` con los rangos de `f_ijk` y de RHS (para CSV)."""
    columnas = [
        "tipo",
        "parametro",
        "valor_base",
        "limite_inferior",
        "limite_superior",
        "permitido_bajar",
        "permitido_subir",
    ]
    filas: list[dict[str, object]] = []
    for clave, rango in sorted(
        rangos.objetivo_f.items(), key=lambda kv: clave_a_texto(kv[0])
    ):
        filas.append(
            {
                "tipo": "objetivo_f",
                "parametro": clave_a_texto(clave),
                "valor_base": rango.valor_base,
                "limite_inferior": rango.limite_inferior,
                "limite_superior": rango.limite_superior,
                "permitido_bajar": rango.permitido_bajar,
                "permitido_subir": rango.permitido_subir,
            }
        )
    for nombre, rango in rangos.rhs.items():
        filas.append(
            {
                "tipo": "rhs",
                "parametro": nombre,
                "valor_base": rango.valor_base,
                "limite_inferior": rango.limite_inferior,
                "limite_superior": rango.limite_superior,
                "permitido_bajar": rango.permitido_bajar,
                "permitido_subir": rango.permitido_subir,
            }
        )
    return pd.DataFrame(filas, columns=columnas)


def exportar_informe_dualidad_sensibilidad(
    precios: PreciosSombra,
    holgura: HolguraComplementaria,
    rangos: RangosSensibilidad,
    directorio: Optional[str] = None,
    prefijo: str = "informe_dualidad_sensibilidad",
    exportar_csv: bool = True,
) -> dict[str, str]:
    """Exporta a `results/` el informe de dualidad y sensibilidad (Req. 6.4).

    Escribe un documento **Markdown** con todas las secciones del análisis
    (advertencia del LP restringido, precios sombra, interpretación, rangos de
    sensibilidad y verificación de holgura complementaria) y, opcionalmente, dos
    **CSV** de apoyo (precios sombra y rangos) para reusar los números.

    Parámetros
    ----------
    precios:
        `PreciosSombra` de `extraer_precios_sombra` (Tarea 6.2).
    holgura:
        `HolguraComplementaria` de `verificar_holgura_complementaria` (6.3).
    rangos:
        `RangosSensibilidad` de `calcular_rangos_sensibilidad` (6.3).
    directorio:
        Carpeta de salida. Por defecto `results/` en la raíz del proyecto. Se
        crea si no existe.
    prefijo:
        Prefijo de los nombres de archivo generados.
    exportar_csv:
        Si `True` (por defecto) escribe también los CSV de apoyo.

    Retorna
    -------
    `dict` con las rutas escritas, con claves `"markdown"`, y si aplica
    `"csv_precios"` y `"csv_rangos"`.
    """
    carpeta = _DIR_RESULTS if directorio is None else directorio
    os.makedirs(carpeta, exist_ok=True)

    rutas: dict[str, str] = {}

    # --- Markdown (documento principal del informe) ------------------------
    markdown = construir_markdown_dualidad_sensibilidad(precios, holgura, rangos)
    ruta_md = os.path.join(carpeta, f"{prefijo}.md")
    with open(ruta_md, "w", encoding="utf-8") as fh:
        fh.write(markdown)
    rutas["markdown"] = ruta_md

    # --- CSV de apoyo (precios sombra y rangos) ----------------------------
    if exportar_csv:
        ruta_precios = os.path.join(carpeta, f"{prefijo}_precios_sombra.csv")
        _dataframe_precios_sombra(precios).to_csv(
            ruta_precios, index=False, encoding="utf-8"
        )
        rutas["csv_precios"] = ruta_precios

        ruta_rangos = os.path.join(carpeta, f"{prefijo}_rangos.csv")
        _dataframe_rangos(rangos).to_csv(
            ruta_rangos, index=False, encoding="utf-8"
        )
        rutas["csv_rangos"] = ruta_rangos

    return rutas


# ---------------------------------------------------------------------------
# Autocomprobación de humo (sin framework): resuelve y reporta el fixture.
# Los datos reales dejan las tasas vacías (cero invención), así que se usa el
# fixture sintético de model.py. Ejecutar con:  python src/report.py
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    # La consola por defecto de Windows (cp1252) no puede codificar los
    # símbolos del reporte (Σ, ≈, ·). Forzar UTF-8 en stdout evita un
    # UnicodeEncodeError al ejecutar la autocomprobación en PowerShell.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    from model import (
        _datos_sinteticos,
        agregar_restricciones_riesgo,
        agregar_restricciones_tramos,
        construir_modelo,
    )
    from sensitivity import (
        calcular_rangos_sensibilidad,
        construir_lp_restringido,
        extraer_precios_sombra,
        verificar_holgura_complementaria,
    )
    from solver import resolver

    datos = _datos_sinteticos()
    modelo = construir_modelo(datos)
    agregar_restricciones_tramos(modelo)
    agregar_restricciones_riesgo(modelo)
    resultado = resolver(modelo)
    imprimir_reporte_asignacion(resultado, modelo)

    # --- Tarea 7: exportar el informe de dualidad y sensibilidad -----------
    # Pipeline completo: MILP → LP restringido → duales/holgura/rangos → export.
    print("\n== Exportación del informe de dualidad y sensibilidad (Tarea 7) ==")
    lp = construir_lp_restringido(datos, resultado)
    precios = extraer_precios_sombra(lp)
    holgura = verificar_holgura_complementaria(lp)
    rangos = calcular_rangos_sensibilidad(lp)

    rutas = exportar_informe_dualidad_sensibilidad(precios, holgura, rangos)
    for clave, ruta in rutas.items():
        print(f"  {clave:12s}: {ruta}")

    # Verificación mínima de la exportación: existencia y secciones esperadas.
    ruta_md = rutas["markdown"]
    assert os.path.exists(ruta_md), f"No se escribió el informe: {ruta_md}"
    with open(ruta_md, encoding="utf-8") as fh:
        contenido = fh.read()
    for seccion in (
        "Requisito 4.7",
        "## 2. Precios sombra",
        "## 3. Interpretación económica",
        "## 4. Rangos de sensibilidad",
        "holgura complementaria",
    ):
        assert seccion in contenido, f"Falta la sección '{seccion}' en el informe."
    print(
        "\nVerificación OK (Tarea 7): el informe se exportó a results/ con la "
        "advertencia del LP restringido (Req. 4.7), precios sombra, "
        "interpretación, rangos de sensibilidad y holgura complementaria."
    )
