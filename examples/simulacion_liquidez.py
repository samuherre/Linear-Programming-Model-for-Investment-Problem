"""Simulación de escenarios de liquidez ("escalera" de CDT) — ejemplo didáctico.

Caso de estudio planteado en clase
----------------------------------
Un inversionista coloca **10 millones** de COP en **julio** pero necesita poder
**rescatar una parte por anticipado** (p. ej. **2 millones hacia diciembre**) y
dejar el resto invertido más tiempo para **seguir ganando con el mismo capital**.
Cuando el tramo corto vence, se reinvierte (estrategia de "escalera"/rolling),
de modo que los 10 millones siguen trabajando.

Cómo se traduce al modelo
-------------------------
El modelo MILP no maneja fechas de calendario: el plazo `j` está en **días**
({30, 60, 90, 180, 360, 540, 720}). "De julio a diciembre" son ~5-6 meses, es
decir el **bucket corto** del modelo (`j ≤ 180`). La exigencia "quiero 2 de los
10 millones disponibles pronto" se expresa con la **cota de liquidez**
`L_corto`/`U_corto` (fracción del capital en plazos ≤180 días). El resto queda en
plazos largos (`j > 180`), donde el rendimiento del periodo es mayor.

Este script NO reimplementa el modelo: reutiliza `data_loader`, `model`,
`solver` y `sensitivity` de `src/`, igual que `src/main.py` y la API. Usa el
escenario ilustrativo `data/escenario_supuesto.csv` (tasas completas por
`(banco, plazo, tramo)`), apropiado para un ejemplo reproducible.

Ejecución
---------
    python examples/simulacion_liquidez.py

Los parámetros del caso (capital, concentración y los escenarios del barrido)
están al inicio como constantes editables: cambie los números y vuelva a correr
para explorar "diferentes caras" del mismo problema.
"""

from __future__ import annotations

import os
import sys

# UTF-8 en consola de Windows (mismo patrón que src/main.py).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Insertar src/ y data/ en el path, igual que api/app.py (imports planos).
_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _ruta in (os.path.join(_RAIZ, "src"), os.path.join(_RAIZ, "data")):
    if _ruta not in sys.path:
        sys.path.insert(0, _ruta)

import config as config_modulo  # noqa: E402
from data_loader import cargar_datos  # noqa: E402
from model import (  # noqa: E402
    agregar_restricciones_riesgo,
    agregar_restricciones_tramos,
    construir_modelo,
)
from sensitivity import (  # noqa: E402
    construir_lp_restringido,
    extraer_precios_sombra,
)
from solver import resolver  # noqa: E402


# ---------------------------------------------------------------------------
# Parámetros editables del caso de estudio
# ---------------------------------------------------------------------------
ARCHIVO_DATOS = "escenario_supuesto.csv"  # tasas completas (dato ilustrativo)
A = 10_000_000          # capital total a invertir (COP)
CONCENTRACION = 0.40    # fracción máxima por banco (diversificación)

# Barrido de escenarios: (etiqueta, fracción mínima a corto, fracción máxima a
# corto). None desactiva la cota. Fijar L=U "ancla" un monto exacto en el bucket
# corto (≤180 días); el optimizador decide el banco/plazo corto que más rinde.
ESCENARIOS = [
    ("Libre (sin exigencia de liquidez)", None, None),
    ("1M a corto (10%)",                   0.10, 0.10),
    ("2M a corto (20%)  <- caso de clase", 0.20, 0.20),
    ("3M a corto (30%)",                   0.30, 0.30),
    ("4M a corto (40%)",                   0.40, 0.40),
]

# Escenario "protagonista" cuyo detalle y precios sombra se imprimen.
FRAC_CORTO_FLAGSHIP = 0.20


def _config(frac_corto_min, frac_corto_max, concentracion=CONCENTRACION, capital=A):
    """Arma un config override (parte de data/config.py y cambia A/conc/liquidez)."""
    base = config_modulo.get_config()
    return {
        "A": capital,
        "tramos": base["tramos"],
        "concentracion_max": {b: concentracion for b in base["concentracion_max"]},
        "liquidez": {
            "L_corto": frac_corto_min,
            "U_corto": frac_corto_max,
            "L_largo": None,
            "U_largo": None,
        },
    }


def _resolver_escenario(frac_corto_min, frac_corto_max):
    """Carga, construye y resuelve el MILP para una exigencia de liquidez dada."""
    cfg = _config(frac_corto_min, frac_corto_max)
    datos = cargar_datos(archivo_datos=ARCHIVO_DATOS, config=cfg)
    modelo = construir_modelo(datos)
    agregar_restricciones_tramos(modelo)
    agregar_restricciones_riesgo(modelo)
    resultado = resolver(modelo)
    corto = sum(v for c, v in resultado.x.items() if c[1] <= 180)
    largo = sum(v for c, v in resultado.x.items() if c[1] > 180)
    return datos, resultado, corto, largo


def tabla_comparativa():
    """Imprime la tabla de 'diferentes caras': liquidez exigida vs rendimiento."""
    print("=" * 112)
    print("  SIMULACIÓN DE LIQUIDEZ — ESCALERA DE CDT (julio: invertir 10M; parte rescatable ~diciembre)")
    print("=" * 112)
    print(
        f"Capital A = {A:,.0f} COP | concentración máx {CONCENTRACION:.0%}/banco | "
        f"datos: {ARCHIVO_DATOS} (ilustrativo)\n"
    )
    print(
        f"{'Escenario':38s} {'Estado':9s} {'Ganancia Z*':>14s} {'Rend.efec':>9s} "
        f"{'Corto(<=180)':>13s} {'Largo(>180)':>12s} {'#CDT':>5s}"
    )
    print("-" * 112)
    filas = []
    for nombre, lo, hi in ESCENARIOS:
        datos, res, corto, largo = _resolver_escenario(lo, hi)
        rend = (res.objetivo / A * 100) if res.objetivo else 0.0
        filas.append((nombre, lo, res.objetivo))
        print(
            f"{nombre:38s} {res.estado:9s} {res.objetivo:>14,.0f} {rend:>8.3f}% "
            f"{corto:>13,.0f} {largo:>12,.0f} {len(res.x):>5d}"
        )

    # Costo marginal de la liquidez (cuánto cuesta en Z* exigir más a corto).
    print("\nCosto de oportunidad de la liquidez (pérdida de ganancia vs 'Libre'):")
    z_libre = filas[0][2]
    for nombre, lo, z in filas[1:]:
        if z is not None and z_libre is not None:
            print(f"  {nombre:38s} -> renuncia a {z_libre - z:>12,.0f} COP de ganancia")


def detalle_flagship():
    """Detalle de asignación y precios sombra del caso protagonista (2M a corto)."""
    datos, res, corto, largo = _resolver_escenario(FRAC_CORTO_FLAGSHIP, FRAC_CORTO_FLAGSHIP)

    print("\n\n" + "=" * 90)
    print(f"  DETALLE DEL CASO DE CLASE: {FRAC_CORTO_FLAGSHIP:.0%} a corto (≤180 d) / resto a largo")
    print("=" * 90)
    print(
        f"Estado: {res.estado} | Ganancia total Z* = {res.objetivo:,.0f} COP "
        f"({res.objetivo / A * 100:.3f}% efectivo)"
    )
    print(f"Capital colocado: {res.capital_colocado:,.0f} | sin colocar s0: {res.s0:,.0f}\n")
    print(
        f"{'Banco':18s} {'Plazo(d)':>8s} {'Tramo':>5s} {'Monto':>14s} "
        f"{'Tasa EA':>8s} {'Rend.periodo':>13s} {'Bucket':>7s}"
    )
    print("-" * 90)
    for c, v in sorted(res.x.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        banco, plazo, tramo = c
        bucket = "CORTO" if plazo <= 180 else "LARGO"
        print(
            f"{banco:18s} {plazo:>8d} {tramo:>5d} {v:>14,.0f} "
            f"{datos.r[c] * 100:>7.2f}% {datos.f[c] * v:>13,.0f} {bucket:>7s}"
        )

    # --- Precios sombra sobre el LP restringido (tema de dualidad del proyecto) ---
    lp = construir_lp_restringido(datos, res)
    precios = extraer_precios_sombra(lp)
    TOL = 1e-7
    print("\nPrecios sombra (LP restringido con z = z*):")
    if precios.lambda_capital is not None:
        print(f"  λ* (capital)              = {precios.lambda_capital:.6f}")

    # Liquidez: mostrar solo las cotas activas (|σ| > 0).
    for etiqueta, sigma in precios.sigma_liquidez.items():
        if abs(sigma) > TOL:
            print(
                f"  σ* [{etiqueta:18s}] = {sigma:.6f}  "
                f"-> valor marginal, en rendimiento, de mover un peso esa cota de liquidez."
            )
    # Concentración: bancos cuyo tope p·A está ACTIVO (diversificación 'cuesta').
    for banco, mu in precios.mu_concentracion.items():
        if abs(mu) > TOL:
            print(
                f"  μ* [{banco:18s}] = {mu:.6f}  "
                f"-> tope del banco activo: ganaría eso por peso extra permitido ahí."
            )
    print(
        "\n  NOTA: la sensibilidad/dualidad aplica al LP restringido (binarias z\n"
        "  fijadas en z*), no al MILP original (Requisito 4.7 del proyecto)."
    )

    print(
        "\nLectura del caso: se anclan 2M en el CDT corto (≤180 d, que vence hacia\n"
        "diciembre); al vencer se reinvierte y los 10M siguen trabajando. Los 8M\n"
        "restantes van a plazos largos, que rinden más por periodo. La tabla de\n"
        "arriba muestra el precio de esa liquidez: a más exigencia de rescate\n"
        "anticipado, menor ganancia total."
    )


if __name__ == "__main__":
    tabla_comparativa()
    detalle_flagship()
