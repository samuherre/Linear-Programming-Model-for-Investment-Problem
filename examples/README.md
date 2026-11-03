# Ejemplos del modelo de inversión en CDT

Scripts de ejemplo que **reutilizan** los módulos de `src/` (no reimplementan el
modelo) para ilustrar casos de uso concretos.

## `simulacion_liquidez.py` — Escalera de CDT (liquidez vs rendimiento)

Caso de clase: un inversionista coloca **10 millones** en **julio** pero quiere
poder **rescatar 2 millones por anticipado** (hacia **diciembre**) y dejar el
resto invertido más tiempo para **seguir ganando con el mismo capital**. Al
vencer el tramo corto se reinvierte (estrategia de escalera/*rolling*).

Como el modelo usa el plazo en **días** (no fechas), "de julio a diciembre"
(~5-6 meses) corresponde al **bucket corto** `j ≤ 180`. La exigencia "2 de los 10
millones disponibles pronto" se expresa con la **cota de liquidez**
`L_corto`/`U_corto`. El script barre varios niveles de liquidez (0 %, 10 %, 20 %,
30 %, 40 % a corto) y muestra:

- una **tabla comparativa** (ganancia `Z*`, rendimiento efectivo y reparto
  corto/largo) con el **costo de oportunidad** de exigir más liquidez;
- el **detalle de asignación** del caso de clase (20 % a corto / 80 % a largo);
- los **precios sombra** (dualidad) del LP restringido: `λ*` (capital),
  `σ*` (liquidez) y `μ*` (concentración por banco).

Los parámetros (capital `A`, concentración y los escenarios del barrido) son
**constantes editables** al inicio del archivo: cambie los números y vuelva a
correr para explorar diferentes variantes del mismo problema.

### Ejecución

```powershell
# Desde la raíz del proyecto, con el entorno virtual activado (ver README principal)
python examples/simulacion_liquidez.py
```

Usa el escenario ilustrativo `data/escenario_supuesto.csv` (tasas completas por
`(banco, plazo, tramo)`), apropiado para un ejemplo reproducible.
