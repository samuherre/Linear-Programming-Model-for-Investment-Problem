# Optimización de la Inversión en Certificados de Depósito a Término (CDT) mediante Programación Lineal Entera Mixta

**Autores:** Samuel Herrera Galvis, Emanuell Torres López, Francis Henry León Rojas

**Institución:** Universidad EAFIT — Curso Optimización 1

<!--
ESTRUCTURA DEL ARTÍCULO (Requisito 5.1)
Orden exigido de las 8 secciones:
  1. Resumen
  2. Introducción
  3. Revisión de Literatura
  4. Metodología
  5. Resultados
  6. Discusión y Análisis de Sensibilidad
  7. Conclusiones
  8. Referencias

ESTADO DE REDACCIÓN POR SUB-TAREA:
  - 9.1: esqueleto con las 8 secciones en orden. [HECHO]
  - 9.2: redactar Introducción y Revisión de Literatura. [HECHO]
  - 9.3: redactar Metodología con ecuaciones explícitas. [HECHO]
  - 9.4: redactar Resultados y Discusión con salidas de Python; completar
         Resumen y Conclusiones. [HECHO]
  - ACTUALIZACIÓN (datos reales + liquidez por fecha): el artículo se
    actualizó para reflejar el estado actual de `main`. (a) Los datos ya no
    son "tasas supuestas": `data/cdt_productos.csv` contiene 90 combinaciones
    (i, j, k) REALES y trazables a entidades colombianas vigiladas (tasa SFC /
    tarifarios digitales, corte oct-2026) y solo 15 combinaciones marcadas
    `es_supuesto = True` por NO ofrecerse el producto en ese plazo. (b) Se
    formalizó la nueva familia de restricciones de LIQUIDEZ POR FECHA (reglas
    por umbral de plazo) y la de CONCENTRACIÓN MÁXIMA POR PLAZO, respuesta a la
    retroalimentación de la profesora. (c) Se reemplazaron los Resultados y la
    Sensibilidad por las cifras del escenario base vigente. (d) Se mejoró el
    formato (tabla de contenidos, numeración consistente, tablas alineadas,
    ecuaciones en bloques LaTeX). [HECHO]
-->

---

## Tabla de contenidos

1. [Resumen](#1-resumen)
2. [Introducción](#2-introducción)
3. [Revisión de Literatura](#3-revisión-de-literatura)
   - [3.1 Modelos de selección de portafolios](#31-modelos-de-selección-de-portafolios)
   - [3.2 La notación `R||A_max` y su analogía](#32-la-notación-ramax-de-secuenciación-y-su-analogía-con-el-problema)
   - [3.3 Programación entera mixta y estructuras por tramos](#33-programación-entera-mixta-y-estructuras-por-tramos-piecewise)
4. [Metodología](#4-metodología)
   - [4.1 Conjuntos e índices](#41-conjuntos-e-índices)
   - [4.2 Parámetros](#42-parámetros)
   - [4.3 Variables de decisión](#43-variables-de-decisión)
   - [4.4 Función objetivo](#44-función-objetivo)
   - [4.5 Restricciones](#45-restricciones)
   - [4.6 Estrategia MILP + LP restringido](#46-estrategia-milp--lp-restringido-para-dualidad-y-sensibilidad)
   - [4.7 Primal del LP restringido](#47-primal-del-lp-restringido-p)
   - [4.8 Dual del LP restringido](#48-dual-del-lp-restringido-d)
   - [4.9 Holgura complementaria](#49-holgura-complementaria-y-relación-s_0--lambda)
5. [Resultados](#5-resultados)
   - [5.1 Datos de entrada: 90 combinaciones reales](#51-datos-de-entrada-90-combinaciones-reales-trazables)
   - [5.2 Reproducibilidad](#52-reproducibilidad)
   - [5.3 Escenario base y solución óptima](#53-escenario-base-y-solución-óptima)
   - [5.4 Costo de oportunidad de la liquidez](#54-costo-de-oportunidad-de-la-liquidez-comparación-con-y-sin-exigencia)
6. [Discusión y Análisis de Sensibilidad](#6-discusión-y-análisis-de-sensibilidad)
   - [6.1 Precios sombra del escenario base](#61-precios-sombra-del-escenario-base)
   - [6.2 Interpretación económica de las restricciones activas](#62-interpretación-económica-de-las-restricciones-activas)
   - [6.3 Verificación del Teorema de Holgura Complementaria](#63-verificación-del-teorema-de-holgura-complementaria)
   - [6.4 Rangos de estabilidad de la base óptima](#64-rangos-de-estabilidad-de-la-base-óptima)
   - [6.5 Limitaciones del análisis](#65-limitaciones-del-análisis)
7. [Conclusiones](#7-conclusiones)
8. [Referencias](#8-referencias)

---

## 1. Resumen

La asignación de excedentes de tesorería entre Certificados de Depósito a
Término (CDT) de distintos bancos, plazos y tramos de monto es un problema de
decisión combinatorio que difícilmente se resuelve "a ojo". Este trabajo
formula esa asignación como un modelo de Programación Lineal Entera Mixta
(MILP) que maximiza el rendimiento efectivo total de un capital $A$ colocado en
CDT de cinco entidades colombianas, usando como coeficiente objetivo el factor
de rendimiento del periodo de tenencia $f_{ijk} = (1 + r_{ijk})^{j/360} - 1$
para comparar correctamente plazos heterogéneos. El modelo incorpora tasas
escalonadas por monto mediante variables binarias de activación de tramo y
restricciones realistas de presupuesto, diversificación por banco, montos
mínimos de apertura, **liquidez por fecha** (una fracción del capital debe
vencer antes de un umbral de días dado) y **concentración máxima por plazo**.
Sobre la solución entera se construye un Programa Lineal (LP) restringido
—fijando las binarias en su valor óptimo— que habilita un análisis riguroso de
dualidad y sensibilidad, tal como exige el curso. El modelo se implementó en
Python con PuLP (solver CBC) en módulos separados de carga de datos, modelo,
resolución, sensibilidad y reporte.

A diferencia de versiones previas de este trabajo, **los resultados se generan
ahora sobre datos reales y trazables**: la matriz `data/cdt_productos.csv`
contiene 90 combinaciones $(i, j, k)$ con tasas E.A. reales de entidades
vigiladas por la Superintendencia Financiera (corte octubre de 2026), y solo 15
combinaciones quedan marcadas como no disponibles porque el banco no ofrece ese
plazo. Sobre esas tasas reales, el óptimo del escenario base ya **no concentra
el capital en un solo plazo**: lo reparte entre 180, 360 y 720 días para
cumplir exactamente las reglas de liquidez por fecha (al menos 30 % vence en
$\le 180$ días y al menos 60 % en $\le 360$ días) y el tope de 40 % por plazo.
El rendimiento efectivo total es $Z^* = 15.405.781{,}00$ COP, y la comparación
con un escenario sin exigencia de liquidez ($Z^* = 24.832.031{,}60$ COP con todo
a 720 días) cuantifica el **costo de oportunidad de la liquidez** en
$9.426.250{,}60$ COP. El análisis dual reporta un precio sombra del capital de
$\lambda^* = 0{,}1201$, identifica como activas la regla de liquidez a 180 días
y el tope del plazo de 720 días, verifica la holgura complementaria
($(x^*)^{\mathsf T} s^* = 0$) y acota la robustez de la cartera mediante rangos
de estabilidad.

**Palabras clave:** optimización de inversiones; CDT; programación lineal entera
mixta; dualidad; análisis de sensibilidad; liquidez; gestión de tesorería.

---

## 2. Introducción

La gestión de tesorería es una de las funciones financieras más sensibles de cualquier organización: consiste en decidir cómo colocar el capital disponible de modo que conserve valor, mantenga la liquidez necesaria para la operación y, al mismo tiempo, genere el mayor rendimiento posible dentro de un nivel de riesgo tolerable. En el contexto colombiano, uno de los instrumentos más utilizados para la colocación de excedentes de caja es el Certificado de Depósito a Término (CDT), un título de renta fija emitido por una entidad financiera a cambio de un depósito de dinero por un plazo previamente pactado, con una tasa de interés fijada desde la apertura [1]. El CDT ofrece una rentabilidad conocida de antemano, no está expuesto a riesgo de mercado durante su vigencia y, cuando la entidad emisora está inscrita en el Fondo de Garantías de Instituciones Financieras (Fogafín), cuenta con un seguro de depósito que protege al ahorrador hasta cierto monto por depositante y por entidad [2]. Estas características lo convierten en una alternativa natural para la administración de excedentes de tesorería que buscan rentabilidad superior a la de una cuenta de ahorros sin asumir volatilidad de precios.

El mercado colombiano de CDT es amplio y heterogéneo. Las entidades vigiladas por la Superintendencia Financiera de Colombia ofrecen productos a distintos plazos —típicamente de 30, 60, 90, 180 y 360 días, con opciones a mayor horizonte— y el Banco de la República calcula y publica las tasas de captación como promedio ponderado por monto de las operaciones transadas [3][4]. En la práctica, la tasa ofrecida a un inversionista no es única: depende de la entidad y del plazo y, en ciertos rangos, del monto depositado. Esta estructura, sumada a la diversidad de emisores y plazos, genera un espacio de decisión combinatorio en el que elegir "a ojo" la mejor colocación es, en el mejor de los casos, subóptimo.

El problema que aborda este trabajo es, por tanto, el de **asignar un capital total $A$ entre un conjunto de productos CDT ofrecidos por varias entidades, a distintos plazos y con tasas escalonadas por tramos de monto, de forma que se maximice el rendimiento total al vencimiento sujeto a restricciones realistas de riesgo y liquidez**. Las restricciones recogen límites de diversificación por entidad (evitar concentrar el capital en un solo banco), montos mínimos de apertura, la lógica de que cada producto activa a lo sumo un tramo de tasa, y —como aporte de esta versión— exigencias de **liquidez por fecha** (disponer de parte del capital en una fecha intermedia, por ejemplo a los seis meses) y de **diversificación por plazo** (no concentrar todo el dinero en un único horizonte). La presencia de tramos escalonados y de montos mínimos introduce decisiones de tipo "todo o nada" que exigen variables binarias, de modo que el problema se formula de forma natural como un modelo de Programación Lineal Entera Mixta (MILP).

Los objetivos concretos de este trabajo son: (i) formular un modelo MILP que maximice el rendimiento efectivo total del capital colocado en CDT, usando como coeficiente objetivo el factor de rendimiento del periodo de tenencia $f_{ijk} = (1 + r_{ijk})^{j/360} - 1$ para comparar correctamente plazos heterogéneos a partir de la Tasa Efectiva Anual $r_{ijk}$; (ii) incorporar la lógica de tasas escalonadas por tramos mediante variables binarias de activación y las restricciones de riesgo y liquidez antes descritas, incluida la liquidez por fecha y la concentración por plazo; (iii) resolver el modelo con herramientas de código abierto en Python sobre tasas reales de bancos colombianos y presentar la asignación óptima de capital por banco, plazo y tramo; y (iv) realizar un análisis de dualidad y sensibilidad —sobre el LP que resulta de fijar las binarias en su valor óptimo— para interpretar económicamente los precios sombra del capital, de los topes de concentración y de las nuevas exigencias de liquidez, verificar el teorema de holgura complementaria y calcular los rangos de estabilidad de la base óptima. Con ello, el trabajo articula un problema aplicado de tesorería con los contenidos de dualidad y sensibilidad del curso de Optimización 1.

---

## 3. Revisión de Literatura

### 3.1 Modelos de selección de portafolios

El estudio formal de la asignación de capital entre activos arranca con el trabajo seminal de Markowitz sobre selección de portafolios, que plantea el problema como un balance entre el rendimiento esperado y el riesgo medido por la varianza del portafolio [5]. El modelo media-varianza de Markowitz es un problema de optimización cuadrática: maximizar el rendimiento esperado para un nivel de varianza dado, o minimizar la varianza para un rendimiento objetivo, sujeto a que los pesos de inversión sumen la unidad. De este enfoque se derivan la frontera eficiente y buena parte de la teoría moderna de portafolios.

Para instrumentos de renta fija como los CDT, donde la tasa se pacta al inicio y no hay riesgo de precio durante la vigencia del título, la componente de varianza del retorno pierde protagonismo frente a restricciones operativas y de política: diversificación por emisor, montos mínimos, cupos y horizontes de liquidez. En estos contextos es habitual sustituir o aproximar el término cuadrático por formulaciones lineales o lineales enteras mixtas, que resultan más tratables y permiten incorporar directamente decisiones discretas. La literatura de optimización para selección de portafolios con restricciones de cardinalidad, lotes mínimos (minimum buy-in) y umbrales de inversión muestra precisamente esta transición: dichas condiciones se modelan con variables binarias, convirtiendo el problema en un MILP [7]. El modelo propuesto en este trabajo se inscribe en esa línea: conserva la idea de diversificación de Markowitz a través de cotas de concentración por banco y por plazo, pero prescinde del término de varianza —innecesario para un portafolio de CDT de rentabilidad pactada— y sitúa el énfasis en la estructura entera de las decisiones.

### 3.2 La notación `R||A_max` de secuenciación y su analogía con el problema

En la teoría de secuenciación y programación de tareas (scheduling) se emplea la notación de tres campos $\alpha \mid \beta \mid \gamma$ introducida por Graham, Lawler, Lenstra y Rinnooy Kan para clasificar problemas según el entorno de máquinas ($\alpha$), las restricciones del proceso ($\beta$) y el criterio de optimización ($\gamma$) [8]. En esa taxonomía, $R$ denota máquinas paralelas no relacionadas (unrelated parallel machines), es decir, máquinas en las que el tiempo de procesamiento de una tarea depende de la máquina a la que se asigne; el campo $\gamma$ especifica la función objetivo, como el makespan $C_{\max}$ (minimizar el instante de finalización máximo) [9]. La variante referida en el enunciado del curso como $R \mid\mid A_{\max}$ corresponde conceptualmente a un entorno de máquinas paralelas no relacionadas en el que se controla una magnitud máxima del campo de optimización.

La analogía con el problema de inversión en CDT es ilustrativa y motiva el encuadre del curso. Los "bancos" (o las combinaciones banco–plazo) hacen las veces de **máquinas no relacionadas**: una misma porción de capital produce un rendimiento distinto según la entidad y el plazo al que se asigne, igual que una tarea toma tiempos distintos en máquinas distintas. Asignar capital a productos es, estructuralmente, el mismo tipo de problema de asignación de un recurso divisible entre alternativas con coeficientes dependientes de la alternativa. La diferencia esencial está en el objetivo y el signo: la secuenciación $R \mid\mid \ldots$ típicamente **minimiza** un máximo (por ejemplo, el makespan), mientras que el problema de tesorería **maximiza** un rendimiento agregado. Aun así, el paralelismo justifica por qué el problema se puede leer con las herramientas de asignación óptima sobre máquinas no relacionadas y refuerza su naturaleza combinatoria. Un tratamiento sistemático de estos modelos y de la notación de tres campos se encuentra en Pinedo [9].

### 3.3 Programación entera mixta y estructuras por tramos (piecewise)

La programación lineal, cuyo desarrollo algorítmico moderno se asocia al método simplex de Dantzig, es el marco natural para problemas de asignación de recursos con objetivo y restricciones lineales [6]. Cuando algunas decisiones son indivisibles o condicionales —activar o no un producto, respetar un monto mínimo, elegir un único tramo de tasa— se requieren variables enteras o binarias, dando lugar a la Programación Lineal Entera Mixta (MILP), cuyo tratamiento teórico y algorítmico (ramificación y acotamiento, planos de corte, formulaciones fuertes) se expone de forma estándar en Wolsey [10] y en Nemhauser y Wolsey [11].

Un recurso de modelado central para este trabajo es la representación de funciones y relaciones **por tramos (piecewise)**. Las tasas escalonadas por monto de los CDT definen, de hecho, una relación rendimiento–monto que cambia por segmentos: cada tramo $k$ tiene una cota inferior $L_k$ y superior $U_k$ y una tasa asociada $r_{ijk}$. Esta estructura se modela con una variable binaria de activación $z_{ijk}$ por tramo y restricciones de vínculo del tipo $L_k \cdot z_{ijk} \le x_{ijk} \le U_k \cdot z_{ijk}$, junto con la condición de que a lo sumo un tramo quede activo por producto $(i, j)$. Estas son las técnicas clásicas de linealización de funciones por tramos y de modelado de disyunciones y costos fijos con binarias documentadas en la literatura de MILP [10][11], y en textos aplicados de modelado como Williams [12]. El modelo de este trabajo combina los tres hilos revisados: la lógica de diversificación heredada de la selección de portafolios, el encuadre de asignación sobre alternativas no relacionadas afín a $R \mid\mid A_{\max}$, y la maquinaria de MILP por tramos para representar fielmente las tasas escalonadas del mercado colombiano de CDT.

---

## 4. Metodología

La metodología formaliza el problema de asignación de capital en CDT como un modelo de Programación Lineal Entera Mixta (MILP) y, sobre su solución entera, construye un Programa Lineal (LP) restringido que habilita el análisis riguroso de dualidad y sensibilidad. Esta sección presenta, en orden, los conjuntos e índices, los parámetros, las variables de decisión, la función objetivo, las familias de restricciones y, finalmente, la formulación explícita del Primal y del Dual del LP restringido con sus condiciones de holgura complementaria.

### 4.1 Conjuntos e índices

- $I$: conjunto de **bancos** emisores, con índice $i \in I$.
- $J$: conjunto de **plazos** en días, con índice $j \in J$. En este trabajo $J = \{30, 60, 90, 180, 360, 540, 720\}$.
- $K$: conjunto de **tramos de monto**, con índice $k \in K = \{1, 2, 3\}$.

Cada combinación $(i, j, k)$ representa un producto concreto: un CDT del banco $i$, al plazo $j$, en el tramo de monto $k$.

### 4.2 Parámetros

- $A$: capital total disponible para invertir.
- $r_{ijk}$: **Tasa Efectiva Anual** (E.A.) de la combinación $(i, j, k)$.
- $f_{ijk}$: **factor de rendimiento efectivo del periodo de tenencia** (coeficiente objetivo), derivado de la tasa E.A. y del plazo $j$:

$$
f_{ijk} = (1 + r_{ijk})^{\,j/360} - 1 .
$$

- $L_k,\ U_k$: cota inferior y superior del tramo $k$. El último tramo es abierto por arriba, $U_3 = \infty$ (se modela sin cota superior o con un valor grande, p. ej. $A$).
- $m_{ij}$: monto **mínimo de apertura** del banco $i$ al plazo $j$.
- $p_i$: fracción **máxima de concentración** del capital admisible en el banco $i$, con $0 < p_i \le 1$.
- $disp_{ijk} \in \{0, 1\}$: indicador de **disponibilidad**; vale 1 si el producto $(i, j, k)$ se ofrece efectivamente.
- **Reglas de liquidez por fecha.** Cada regla se define por un umbral de plazo $D$ (días) y dos fracciones $\ell_D, u_D \in [0, 1]$ (mínima y máxima) del capital que debe o puede colocarse en CDT que vencen en $\le D$ días. El conjunto de combinaciones que cumplen el umbral es
$$
S_D = \{\, (i, j, k) : j \le D \,\}.
$$
Cada cota ($\ell_D$ o $u_D$) se añade solo si está definida; una cota nula desactiva esa desigualdad. En notación matricial, cada regla es una restricción lineal sobre la fracción del capital que vence antes de la fecha asociada a $D$.
- $q_j$: fracción **máxima de concentración por plazo** admisible en el plazo $j$ (diversificación por horizonte). Se define una cota global $q_{\text{default}}$ aplicable a todo plazo, afinable por plazo específico; una cota nula desactiva la restricción para ese plazo.

> **Nota sobre las políticas $\ell_D$, $u_D$ y $q_j$ (supuestos del equipo, no datos de mercado).** Las reglas de liquidez por fecha y el tope por plazo son **política de tesorería del equipo**, no cifras de mercado. El escenario base vigente en `data/config.py` fija dos reglas de liquidez por fecha —regla 1: $\{\text{hasta\_dias}=180,\ \ell_{180}=0{,}30\}$; regla 2: $\{\text{hasta\_dias}=360,\ \ell_{360}=0{,}60\}$— y un tope por plazo uniforme $q_{\text{default}} = 0{,}40$. Estos valores son supuestos declarados, trazables al archivo de configuración, y responden a la retroalimentación de la profesora sobre exigir liquidez en una fecha intermedia sin forzar que todos los CDT compartan plazo.

**Justificación del coeficiente $f_{ijk}$.** La tasa $r_{ijk}$ es una Tasa Efectiva Anual, de modo que usar directamente $\sum r_{ijk}\,x_{ijk}$ valoraría igual un peso inmovilizado 30 días y uno inmovilizado 720 días, sesgando la solución hacia plazos cortos de alta tasa sin reconocer el tiempo real de inmovilización del capital. El factor $f_{ijk}$ convierte la tasa E.A. al rendimiento efectivo del periodo de tenencia, que es la magnitud correcta para sumar retornos entre plazos heterogéneos. Como $f_{ijk}$ es una constante **precalculada**, el objetivo sigue siendo **lineal en $x_{ijk}$** y la teoría dual conserva plena validez sobre el LP restringido.

### 4.3 Variables de decisión

- $x_{ijk} \ge 0$: **monto** de capital asignado a la combinación $(i, j, k)$ (variable continua).
- $z_{ijk} \in \{0, 1\}$: variable **binaria** de activación; vale 1 si se activa el tramo $k$ del producto $(i, j)$. (En el enunciado del curso esta binaria figura como $y_{ijk}$; es la misma variable.)
- $s_0 \ge 0$: **holgura de no-inversión**; capital que queda sin colocar. Permite mantener la restricción de capital como igualdad sin arriesgar la infactibilidad del modelo.

### 4.4 Función objetivo

Se maximiza el **valor efectivo al vencimiento** del capital colocado. El coeficiente de cada producto es el factor de rendimiento efectivo $f_{ijk}$:

$$
\max\ Z \;=\; \sum_{i \in I} \sum_{j \in J} \sum_{k \in K} f_{ijk}\, x_{ijk} .
$$

> **Variante didáctica.** Para contraste puede reportarse también el objetivo lineal directo $\sum_{i}\sum_{j}\sum_{k} r_{ijk}\, x_{ijk}$, que acumula la tasa E.A. sin ajustar por plazo. El modelo expone ambos coeficientes; el de producción es $f_{ijk}$, por la justificación de la subsección 4.2.

### 4.5 Restricciones

El modelo incorpora **diez** familias de restricciones. Las familias (1)–(8) estaban presentes en versiones previas; las familias (9) y (10) —**liquidez por fecha** y **concentración máxima por plazo**— son el aporte de esta versión y responden a la retroalimentación de la profesora.

**(1) Inversión total del capital (igualdad con holgura de no-inversión).**

$$
\sum_{i \in I} \sum_{j \in J} \sum_{k \in K} x_{ijk} + s_0 = A, \qquad s_0 \ge 0 .
$$

La igualdad modela la intención real de la tesorería —colocar todo el capital $A$— y dota al precio sombra $\lambda$ de esta restricción de su interpretación económica más rica (el retorno marginal de un peso adicional de capital). La holgura $s_0$ garantiza factibilidad: si los mínimos de apertura y las demás restricciones impiden sumar exactamente $A$, $s_0$ absorbe y reporta el capital no colocado.

**(2) Concentración máxima por banco (diversificación por emisor).**

$$
\sum_{j \in J} \sum_{k \in K} x_{ijk} \le p_i \cdot A, \qquad \forall\, i \in I .
$$

**(3) Activación de tramo (vínculo $x$–$z$).**

$$
L_k \cdot z_{ijk} \le x_{ijk} \le U_k \cdot z_{ijk}, \qquad \forall\, (i, j, k) .
$$

Si $z_{ijk} = 0$, el vínculo fuerza $x_{ijk} = 0$; si $z_{ijk} = 1$, el monto queda confinado al rango $[L_k, U_k]$ del tramo.

**(4) Monto mínimo de apertura.**

$$
x_{ijk} \ge m_{ij} \cdot z_{ijk}, \qquad \forall\, (i, j, k) .
$$

**(5) A lo sumo un tramo por producto $(i, j)$.**

$$
\sum_{k \in K} z_{ijk} \le 1, \qquad \forall\, (i, j) .
$$

**(6) Liquidez corto vs. largo plazo (retrocompatibilidad).**

$$
L_{\text{corto}} \cdot A \le \sum_{i \in I} \sum_{j \le 180} \sum_{k \in K} x_{ijk} \le U_{\text{corto}} \cdot A ,
$$

$$
L_{\text{largo}} \cdot A \le \sum_{i \in I} \sum_{j > 180} \sum_{k \in K} x_{ijk} \le U_{\text{largo}} \cdot A .
$$

Estas cotas, heredadas de la versión anterior, limitan la exposición a cada horizonte mediante la partición binaria $j \le 180$ / $j > 180$. En el escenario base vigente quedan **desactivadas** (las cuatro cotas en `None`), porque la política de liquidez se expresa ahora con la familia (9), más general.

**(7) Disponibilidad.**

$$
z_{ijk} \le disp_{ijk}, \qquad \forall\, (i, j, k) .
$$

**(8) No negatividad e integralidad.**

$$
x_{ijk} \ge 0, \qquad s_0 \ge 0, \qquad z_{ijk} \in \{0, 1\}, \qquad \forall\, (i, j, k) .
$$

**(9) Liquidez por fecha (aporte de esta versión).** Para cada regla con umbral $D$ (días), sobre el conjunto $S_D = \{\, (i, j, k) : j \le D \,\}$ de productos que vencen en $\le D$ días se impone, con las fracciones definidas:

$$
\ell_D \cdot A \;\le\; \sum_{(i,j,k)\,\in\, S_D} x_{ijk} \;\le\; u_D \cdot A , \qquad \forall\, D \in \mathcal{D} ,
$$

donde $\mathcal{D}$ es el conjunto de umbrales de las reglas definidas. Cada desigualdad ($\ell_D$ inferior, $u_D$ superior) se añade solo si su fracción está definida; una fracción nula desactiva esa desigualdad. Esta familia formaliza la **liquidez en una fecha intermedia**: exigir que una fracción del capital esté disponible al día $D$ equivale, en un modelo de un solo periodo, a exigir que esa fracción se coloque en CDT que vencen en $\le D$ días. La formulación **no obliga a que todos los CDT compartan plazo** —precisamente la limitación que señaló la profesora—: distintos productos con $j \le D$ satisfacen la regla, de modo que el modelo puede combinar plazos para cumplir liquidez y rendimiento a la vez.

En el escenario base, con $\ell_{180} = 0{,}30$ y $\ell_{360} = 0{,}60$:

$$
\sum_{(i,j,k):\,j \le 180} x_{ijk} \;\ge\; 0{,}30\,A , \qquad
\sum_{(i,j,k):\,j \le 360} x_{ijk} \;\ge\; 0{,}60\,A .
$$

> La formulación "al menos 60 % vence en $\le 360$ días" es la expresión lineal equivalente de "a lo sumo 40 % queda en plazos $> 360$ días" sobre la partición acumulada $\{j \le D\}$.

**(10) Concentración máxima por plazo (aporte de esta versión).** Para cada plazo $j$ con combinaciones utilizables y tope definido:

$$
\sum_{i \in I} \sum_{k \in K} x_{ijk} \;\le\; q_j \cdot A, \qquad \forall\, j \in J .
$$

Esta familia evita concentrar todo el capital en un único plazo (por ejemplo, el más rentable). En el escenario base, $q_j = q_{\text{default}} = 0{,}40$ para todos los plazos, de modo que ningún horizonte único puede absorber más del 40 % de $A$.

### 4.6 Estrategia MILP + LP restringido para dualidad y sensibilidad

En un MILP las variables binarias rompen la convexidad del problema, por lo que los precios sombra y los rangos de sensibilidad **no gozan de la garantía de dualidad fuerte**: la teoría dual que los sustenta es válida únicamente para un LP. Para obtener una interpretación económica rigurosa se adopta la siguiente estrategia en dos etapas:

```
┌─────────────────────┐     fija z = z*      ┌──────────────────────┐
│   MILP (asignación)  │ ───────────────────► │  LP restringido       │
│  x_ijk, z_ijk        │                      │  solo x_ijk activas   │
│  → solución óptima    │                      │  → dual, precios       │
│                      │                      │    sombra, rangos      │
└─────────────────────┘                      └──────────────────────┘
```

1. Se resuelve el MILP completo y se obtiene la solución entera óptima $z^*_{ijk}$.
2. Se **fijan** las binarias en su valor óptimo, $z_{ijk} = z^*_{ijk}$, y se conservan únicamente las combinaciones **activas** $Act = \{\, (i, j, k) : z^*_{ijk} = 1 \,\}$, junto con la holgura $s_0$. El problema residual es un LP puramente lineal, sobre el que la dualidad fuerte es válida.

Al fijar $z^* = 1$, las restricciones que dependían de las binarias se transforman en cotas constantes de las variables continuas: el vínculo de tramo $L_k \le x_{ijk} \le U_k$ y el mínimo de apertura $x_{ijk} \ge m_{ij}$ se combinan en $\max(L_k, m_{ij}) \le x_{ijk} \le U_k$ (impuesto como cotas inferior/superior de la variable), mientras que "a lo sumo un tramo" ($\sum_k z \le 1$) y la disponibilidad ($z \le disp$) quedan satisfechas por $z^*$ y no aportan filas al LP. Las restricciones de capital, concentración por banco, liquidez por fecha y concentración por plazo **sí** se conservan como filas del LP y aportan variables duales. **Toda la sensibilidad y todos los precios sombra reportados se refieren a este LP restringido, no al MILP original**; el informe lo advierte explícitamente.

### 4.7 Primal del LP restringido (P)

Sea $x = (x_{ijk})_{(i,j,k)\in Act}$ el vector de montos continuos de las combinaciones activas, más la holgura $s_0 \ge 0$. El Primal es:

$$
\text{(P)}\quad
\begin{aligned}
\max\ \ & \sum_{(i,j,k)\in Act} f_{ijk}\, x_{ijk} \\[2pt]
\text{s.a.}\quad
& \sum_{(i,j,k)\in Act} x_{ijk} + s_0 = A && (\lambda) \\
& \sum_{(j,k):(i,j,k)\in Act} x_{ijk} \le p_i \cdot A && (\mu_i \ge 0),\ \forall\, i \\
& \sum_{(i,j,k)\in Act,\ j\le D} x_{ijk} \ge \ell_D \cdot A && (\sigma^{\text{liq}}_D \ge 0),\ \forall\, D \\
& \sum_{(i,j,k)\in Act,\ j = j_0} x_{ijk} \le q_{j_0} \cdot A && (\sigma^{\text{plz}}_{j_0} \ge 0),\ \forall\, j_0 \\
& \text{cota}^{\text{inf}}_{ijk} \le x_{ijk} \le \text{cota}^{\text{sup}}_{ijk} && (\nu_{ijk}) \\
& x_{ijk} \ge 0,\quad s_0 \ge 0 &&
\end{aligned}
$$

donde $\text{cota}^{\text{inf}}_{ijk} = \max(L_k, m_{ij})$ y $\text{cota}^{\text{sup}}_{ijk} = U_k$ (o $A$ si el tramo es abierto por arriba). Entre paréntesis se anotan las variables duales asociadas a cada familia de restricciones: $\lambda$ para el capital, $\mu_i$ para la concentración por banco, $\sigma^{\text{liq}}_D$ para cada **regla de liquidez por fecha** (familia 9), $\sigma^{\text{plz}}_{j_0}$ para cada **tope de concentración por plazo** (familia 10), y $\nu_{ijk}$ para las cotas de cada variable (mínimo de apertura y límites de tramo). Las cotas de tramo y el mínimo de apertura se imponen como cotas de la variable, por lo que su precio sombra $\nu_{ijk}$ corresponde al costo reducido (reduced cost) de $x_{ijk}$.

### 4.8 Dual del LP restringido (D)

El Dual asocia una variable a cada restricción del Primal y minimiza el costo imputado de los recursos. Con $\lambda$ **libre** (por corresponder a una igualdad), $\mu_i, \sigma^{\text{plz}}_{j_0} \ge 0$ (restricciones $\le$) y $\sigma^{\text{liq}}_D \ge 0$ (restricciones $\ge$, con su signo correspondiente en el objetivo dual):

$$
\text{(D)}\quad
\begin{aligned}
\min\ \ & A\,\lambda \;+\; \sum_{i} (p_i A)\,\mu_i \;-\; \sum_{D} (\ell_D A)\,\sigma^{\text{liq}}_D \;+\; \sum_{j_0} (q_{j_0} A)\,\sigma^{\text{plz}}_{j_0} \;+\; (\text{términos de cotas } \nu) \\[2pt]
\text{s.a.}\quad
& \lambda + \mu_{i(ijk)} - \sigma^{\text{liq}}_{D(ijk)} + \sigma^{\text{plz}}_{j(ijk)} + \nu_{ijk} \;\ge\; f_{ijk} && \forall\, (i,j,k)\in Act \\
& \lambda \;\ge\; 0 && (\text{fila de } s_0,\ \text{coef. } 0 \text{ en P}) \\
& \mu_i \ge 0,\quad \sigma^{\text{plz}}_{j_0} \ge 0,\quad \sigma^{\text{liq}}_D \ge 0,\quad \lambda\ \text{libre} &&
\end{aligned}
$$

donde $D(ijk)$ recorre las reglas de liquidez cuyo umbral cubre al producto ($j \le D$) y $j(ijk)$ es el plazo del producto. La restricción dual exige que el **precio compuesto** de los recursos que consume cada peso colocado en $(i, j, k)$ cubra al menos su rendimiento $f_{ijk}$. En la base óptima, esta desigualdad se vuelve igualdad para las variables básicas, lo que constituye la condición de holgura complementaria.

**Interpretación económica de los precios sombra.**

- $\lambda^*$ (**capital**): retorno marginal de una unidad monetaria adicional de capital $A$; cuánto crecería el objetivo $\sum f_{ijk}\,x_{ijk}$ con un peso más para invertir, manteniendo óptima la base.
- $\mu_i^*$ (**concentración por banco** $i$): costo de oportunidad del tope $p_i A$. Si $\mu_i^* > 0$, el tope del banco $i$ está activo y limita; relajarlo permitiría colocar un peso más en esa entidad y ganar $\mu_i^*$ de rendimiento.
- $\sigma^{\text{liq}*}_D$ (**liquidez por fecha**): valor marginal de la regla asociada al umbral $D$. Mide cuánto cambia el rendimiento por relajar en un peso la exigencia de capital que debe vencer en $\le D$ días. Un signo negativo indica que la exigencia de liquidez a corto resta rendimiento (obliga a colocar capital en plazos menos rentables).
- $\sigma^{\text{plz}*}_{j_0}$ (**concentración por plazo** $j_0$): costo de oportunidad del tope $q_{j_0} A$. Si es positivo, el plazo $j_0$ está saturado y el modelo querría colocar más ahí; relajar el tope mejoraría el objetivo en esa magnitud por peso.

### 4.9 Holgura complementaria y relación $s_0^* \leftrightarrow \lambda^*$

En el óptimo del par Primal–Dual se cumple la condición de **holgura complementaria**, que sobre el LP restringido se expresa como

$$
(x^*)^{\mathsf T} s^* = 0 ,
$$

es decir, el producto de cada variable primal por la holgura de su restricción complementaria es nulo (dentro de una tolerancia numérica, p. ej. $10^{-6}$). Esto se descompone en dos familias de términos: por restricción, $slack_c \cdot \pi_c = 0$ (una restricción con holgura tiene precio sombra nulo); y por variable, $dj_v \cdot (v - \text{cota activa}) = 0$ (una variable estrictamente dentro de sus cotas tiene costo reducido nulo).

La holgura de no-inversión $s_0$ entra en la restricción de capital con coeficiente $0$ en el objetivo, de modo que su condición dual es $\lambda \ge 0$ y la complementariedad impone $s_0^* \cdot \lambda^* = 0$:

- Si $s_0^* > 0$ (**sobró capital** sin colocar), entonces necesariamente $\lambda^* = 0$: tener más capital no agrega retorno, pues ni siquiera se colocó todo el disponible; son las restricciones activas de concentración, liquidez o tramos —no la escasez de capital— las que limitan la solución.
- Si $s_0^* = 0$ (**capital agotado**), entonces $\lambda^*$ puede ser positivo y revela el valor marginal del capital: cada peso adicional sí se colocaría y produciría ese rendimiento extra.

Sobre este mismo LP restringido se calculan, finalmente, los **rangos de sensibilidad**: el intervalo de variación de cada coeficiente objetivo $f_{ijk}$ y de cada término del lado derecho $b$ (capital $A$, topes $p_i A$, umbrales de liquidez $\ell_D A$ y topes por plazo $q_j A$) dentro del cual la base óptima se mantiene y los precios sombra permanecen constantes. La interpretación y los valores numéricos de estos precios sombra y rangos se desarrollan en la Sección 6.

---

## 5. Resultados

### 5.1 Datos de entrada: 90 combinaciones reales, trazables

A diferencia de versiones anteriores de este trabajo, **los resultados se generan
sobre datos reales**. La matriz `data/cdt_productos.csv` contiene $5
\text{ bancos} \times 7 \text{ plazos} \times 3 \text{ tramos} = 105$
combinaciones $(i, j, k)$, de las cuales:

- **90 combinaciones son reales y utilizables** (`disponible = True`,
  `es_supuesto = False`): tienen tasa E.A. tomada de fuentes de entidades
  colombianas vigiladas por la Superintendencia Financiera, con corte a
  octubre de 2026. Las tasas de Bancolombia y Davivienda provienen del promedio
  ponderado E.A. reportado por la SFC (corte 29-oct-2026); las de Banco de
  Bogotá, Nu Bank y Lulo Bank, de sus tarifarios digitales por plazo vigentes en
  octubre de 2026 (ver la columna `fuente` del CSV y la Sección 8).
- **15 combinaciones quedan marcadas `es_supuesto = True` y `disponible =
  False`** porque **el banco no ofrece ese plazo**, no porque la tasa sea
  inventada: Nu Bank a 30 y 60 días (6 filas) y Lulo Bank a 30, 60 y 720 días
  (9 filas). Estas combinaciones tienen la tasa vacía y el modelo las excluye.

> **Precisión sobre la desagregación por tramo (trazabilidad).** El mercado
> colombiano cotiza el CDT **por plazo**, no por los tres tramos de monto del
> spec. Por eso, para las 90 combinaciones reales, la **tasa es real y verificada
> por plazo**, y esa misma tasa del plazo se aplica a los tres tramos de monto
> (en ese rango el mercado no premia el monto). Lo único supuesto es, pues, la
> *desagregación por tramo*, no la tasa; así lo declara explícitamente la columna
> `fuente` de cada fila. No se inventó ninguna cifra de tasa.

El escenario base usa capital $A = 100.000.000$, concentración máxima uniforme
$p_i = 0{,}40$ para los cinco bancos, los tres tramos del spec, las dos reglas de
liquidez por fecha ($\ell_{180} = 0{,}30$, $\ell_{360} = 0{,}60$) y el tope de
concentración por plazo $q_{\text{default}} = 0{,}40$ (todos ellos supuestos de
política del equipo, declarados en `data/config.py`).

### 5.2 Reproducibilidad

Los resultados se obtienen ejecutando el pipeline real del proyecto
(`cargar_datos → construir_modelo → agregar_restricciones_tramos →
agregar_restricciones_riesgo → resolver → construir_lp_restringido →
extraer_precios_sombra → verificar_holgura_complementaria →
calcular_rangos_sensibilidad`) sobre la matriz real de productos. La secuencia
reproducible en Windows/PowerShell es:

```powershell
# Crear y activar entorno virtual
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Instalar dependencias
pip install -r requirements.txt

# Ejecutar el modelo y generar el informe de dualidad/sensibilidad en results/
python src\main.py
```

El solver reportado es **CBC** (el que acompaña a PuLP) y el estado de la corrida
del escenario base es `Optimal`. El objetivo de producción es el rendimiento
efectivo del periodo $Z = \sum f_{ijk}\,x_{ijk}$ (Sección 4.4).

### 5.3 Escenario base y solución óptima

Con las reglas de liquidez por fecha y el tope por plazo activos, el óptimo **ya
no concentra el capital en un solo plazo**: lo reparte entre 180, 360 y 720 días,
y coloca **todo** el capital ($s_0^* = 0$) en cuatro productos:

| Banco | Plazo (días) | Tramo | Monto $x^*$ (COP) | $r_{ijk}$ (E.A.) | $f_{ijk}$ (periodo) | Rendimiento $f\cdot x^*$ (COP) | % de $A$ |
| --- | ---: | :---: | ---: | ---: | ---: | ---: | ---: |
| Bancolombia | 180 | 1 | 10.000.000,00 | 11,04 % | 5,3755 % | 537.551,90 | 10,00 % |
| Lulo Bank | 180 | 2 | 20.000.000,00 | 11,00 % | 5,3565 % | 1.071.307,51 | 20,00 % |
| Bancolombia | 360 | 2 | 30.000.000,00 | 12,01 % | 12,0100 % | 3.603.000,00 | 30,00 % |
| Davivienda | 720 | 2 | 40.000.000,00 | 12,02 % | 25,4848 % | 10.193.921,60 | 40,00 % |
| **Total** | | | **100.000.000,00** | | | **15.405.781,00** | **100,00 %** |

- **Valor objetivo** $Z^* = \sum f_{ijk}\,x^*_{ijk} = 15.405.781{,}00$ COP: el
  rendimiento efectivo total del capital colocado, con los vencimientos
  escalonados que exige la liquidez.
- **Capital no colocado** $s_0^* = 0$: se invirtió el 100 % del capital
  disponible; no quedó holgura de no-inversión.
- **Variante didáctica** $\sum r_{ijk}\,x^*_{ijk} = 11.715.000{,}00$ COP: la misma
  solución valorada con la tasa E.A. "plana" (sin ajustar por el horizonte de
  tenencia). El contraste con $Z^*$ ilustra de nuevo por qué el coeficiente
  correcto para comparar plazos heterogéneos es $f_{ijk}$ y no $r_{ijk}$: el
  factor $f$ reconoce que el capital a 720 días capitaliza durante dos años.

**Interpretación clave: el capital ya no queda amarrado a un solo plazo.** La
solución reparte el dinero entre horizontes cumpliendo **exactamente** las nuevas
restricciones:

- **Liquidez a 180 días ($\ge 30 \%$):** vence en $\le 180$ días
  $10.000.000 + 20.000.000 = 30.000.000$, es decir, el 30 % de $A$, justo en el
  mínimo exigido.
- **Liquidez a 360 días ($\ge 60 \%$):** vence en $\le 360$ días
  $30.000.000 + 30.000.000 = 60.000.000$, es decir, el 60 % de $A$, justo en el
  mínimo exigido.
- **Tope por plazo ($\le 40 \%$):** el plazo de 720 días recibe exactamente
  $40.000.000$ (el 40 % de $A$, en el tope), y ningún plazo supera el 40 %.

Este reparto resuelve directamente la retroalimentación de la profesora: el
modelo exige liquidez en una fecha intermedia (seis meses) **sin forzar que todos
los CDT compartan plazo**, combinando productos a 180, 360 y 720 días.

### 5.4 Costo de oportunidad de la liquidez: comparación con y sin exigencia

Para aislar el efecto de las nuevas restricciones se re-ejecutó el modelo
**desactivando** la política de liquidez (`liquidez_reglas = []`) y el tope por
plazo (`concentracion_plazo_max = {}`), dejando el resto idéntico al base. Sin
esas exigencias, el óptimo vuelve a concentrarse en el plazo más rentable (720
días) y mejora el rendimiento:

| Escenario | Restricciones de liquidez/plazo | $Z^*$ (COP) | Estructura de la solución |
| --- | --- | ---: | --- |
| **Base** | Activas ($\ell_{180}=0{,}30$, $\ell_{360}=0{,}60$, $q=0{,}40$) | **15.405.781,00** | Repartida 180/360/720 días |
| **Sin liquidez** | Desactivadas | **24.832.031,60** | Todo a 720 días: Banco de Bogotá 20 %, Bancolombia 40 %, Davivienda 40 % |

La diferencia es el **costo de oportunidad de la liquidez**:

$$
24.832.031{,}60 \;-\; 15.405.781{,}00 \;=\; 9.426.250{,}60 \text{ COP} .
$$

Es decir, exigir disponibilidad de caja en fechas intermedias (y evitar la
concentración en un plazo) cuesta ≈ 9,43 millones de COP de rendimiento efectivo
sobre un capital de 100 millones. Este es el resultado central del trabajo: el
modelo **cuantifica** el precio de la liquidez, convirtiendo una política de
tesorería cualitativa ("quiero poder disponer de parte del dinero a los seis
meses") en una cifra concreta de rendimiento sacrificado. Ese costo reaparece,
desagregado en el margen, en los precios sombra de las restricciones activas de
la Sección 6.

---

## 6. Discusión y Análisis de Sensibilidad

> **Advertencia transversal (Req. 4.7).** Todo el análisis de esta sección
> —precios sombra, interpretación económica, rangos de estabilidad y holgura
> complementaria— se refiere al **LP restringido** que resulta de fijar las
> binarias en su valor óptimo $z = z^*$ (Sección 4.6), **no al MILP original**.
> En el MILP las variables binarias rompen la convexidad y la dualidad fuerte no
> está definida; los valores duales solo son rigurosos sobre este LP. Los
> números provienen del escenario base de la Sección 5 y los genera el módulo
> `sensitivity.py` (informe en `results/informe_dualidad_sensibilidad.md`).

### 6.1 Precios sombra del escenario base

Fijadas las cuatro binarias activas del óptimo base (Bancolombia 180/1, Lulo
Bank 180/2, Bancolombia 360/2, Davivienda 720/2) y resuelto el LP restringido,
los valores duales son:

| Recurso | Símbolo | Precio sombra | Estado |
| --- | --- | ---: | --- |
| Capital $\sum x + s_0 = A$ | $\lambda^*$ | 0,12010000 | activa (capital agotado) |
| Concentración Bancolombia $\le p\cdot A$ | $\mu^*_{\text{Bancolombia}}$ | $\approx 0$ | no activa |
| Concentración Davivienda $\le p\cdot A$ | $\mu^*_{\text{Davivienda}}$ | $\approx 0$ | no activa |
| Concentración Lulo Bank $\le p\cdot A$ | $\mu^*_{\text{Lulo Bank}}$ | $\approx 0$ | no activa |
| Liquidez $\ge 30\%$ a $\le 180$ días | $\sigma^*_{\text{liq. }180,\text{ inf}}$ | $-0{,}06653463$ | **activa** |
| Liquidez $\ge 60\%$ a $\le 360$ días | $\sigma^*_{\text{liq. }360,\text{ inf}}$ | $\approx 0$ | no activa |
| Tope plazo 180 días $\le q\cdot A$ | $\sigma^*_{\text{plazo }180}$ | $\approx 0$ | no activa |
| Tope plazo 360 días $\le q\cdot A$ | $\sigma^*_{\text{plazo }360}$ | $\approx 0$ | no activa |
| Tope plazo 720 días $\le q\cdot A$ | $\sigma^*_{\text{plazo }720}$ | $0{,}13474804$ | **activa** |

### 6.2 Interpretación económica de las restricciones activas

**Capital $\lambda^* = 0{,}120100$.** Como el capital se agotó en el óptimo
($s_0^* = 0$), el precio sombra del capital es positivo: un peso adicional de
capital, colocado de forma óptima bajo las restricciones vigentes, incrementaría
el objetivo en ≈ 0,1201 COP de rendimiento efectivo. El valor coincide con el
$f_{ijk}$ del producto marginal del óptimo (Bancolombia 360/2, con $f =
12{,}01\%$), que es donde se colocaría el siguiente peso disponible.

**Concentración por banco $\mu_i^* \approx 0$.** Ninguno de los topes de
concentración por banco está activo: con la cartera repartida por liquidez, ningún
banco llega a su límite del 40 % de forma que lo convierta en restricción
"escasa", de modo que relajar esos cupos no mejoraría el objetivo.

**Liquidez a 180 días $\sigma^*_{\text{liq. }180,\text{ inf}} = -0{,}066535$
(activa).** Esta es la restricción de liquidez por fecha que **efectivamente
limita**. Su signo **negativo** refleja que exigir liquidez a corto plazo
*resta* rendimiento: obligar a que al menos el 30 % del capital venza en $\le
180$ días fuerza a colocar dinero en productos de menor $f_{ijk}$ (plazos cortos)
en lugar del plazo de 720 días, más rentable. En el margen, relajar un peso esa
exigencia (permitir que un peso menos venza a corto) **mejoraría** el objetivo en
≈ 0,0665 COP. La regla de 360 días, en cambio, no está activa
($\sigma^* \approx 0$): se cumple con holgura (vence $\ge 60\%$ sin que la cota
"muerda").

**Tope del plazo de 720 días $\sigma^*_{\text{plazo }720} = 0{,}134748$
(activa).** El tope de concentración del plazo de 720 días está **saturado**
(recibe exactamente el 40 % de $A$) porque 720 es el horizonte más rentable y el
modelo querría colocar aún más ahí. Relajar ese tope en un peso incrementaría el
objetivo en ≈ 0,1347 COP. Los topes de 180 y 360 días no están activos
($\sigma^* \approx 0$). La lectura conjunta es nítida: las dos restricciones que
"mandan" en el óptimo son precisamente las nuevas —la exigencia de liquidez a 180
días (que resta rendimiento) y el tope del plazo de 720 días (que impide
concentrar en el horizonte más rentable)—, y entre ambas explican el costo de
oportunidad de 9,43 millones cuantificado en la Sección 5.4.

### 6.3 Verificación del Teorema de Holgura Complementaria

Sobre el LP restringido del escenario base se verifica la condición
$(x^*)^{\mathsf T} s^* = 0$, descompuesta término a término (por restricción,
$slack \cdot \pi$, y por variable, $dj \cdot (v - \text{cota})$):

- **Condición verificada:** sí.
- **Máxima violación:** $0{,}00\mathrm{e}{+}00$, por debajo de la tolerancia
  $10^{-6}$.
- **Producto global:** $0{,}00\mathrm{e}{+}00$.

El resultado confirma la coherencia entre la solución primal y la dual: toda
restricción no activa tiene precio sombra nulo y toda variable estrictamente
interior a sus cotas tiene costo reducido nulo. En particular, la relación
$s_0^* \cdot \lambda^* = 0$ se cumple en el caso "capital agotado": $s_0^* = 0$ y
$\lambda^* > 0$ (Sección 4.9).

### 6.4 Rangos de estabilidad de la base óptima

El módulo calcula los rangos por **perturbación y re-solución** (un parámetro a
la vez, ceteris paribus), porque CBC no expone el ranging exacto del símplex.

**Lado derecho (RHS) — capital $A$, topes $p_i A$, umbrales de liquidez y topes
por plazo.**

| Recurso | RHS base (COP) | Límite inferior | Límite superior |
| --- | ---: | ---: | ---: |
| Capital $A$ | 100.000.000 | 99.000.000 | 101.000.000 |
| Concentración Bancolombia | 40.000.000 | 39.600.000 | 40.400.000 |
| Concentración Davivienda | 40.000.000 | 39.600.000 | 40.400.000 |
| Concentración Lulo Bank | 40.000.000 | 20.000.000 | $+\infty$ |
| Liquidez $\le 180$ días ($\ge 30\%$) | 30.000.000 | 29.700.000 | 30.300.000 |
| Liquidez $\le 360$ días ($\ge 60\%$) | 60.000.000 | 59.400.000 | 60.600.000 |
| Tope plazo 180 días | 40.000.000 | 30.000.000 | $+\infty$ |
| Tope plazo 360 días | 40.000.000 | 30.000.000 | $+\infty$ |
| Tope plazo 720 días | 40.000.000 | 39.600.000 | 40.400.000 |

Dentro de cada intervalo la base óptima se mantiene y el precio sombra es
constante, con $\Delta Z = \pi \cdot \Delta b$. Los intervalos más estrechos
corresponden a las restricciones activas (capital, liquidez a 180 días y tope del
plazo de 720), coherente con que son las que fijan la solución; el tope de
Lulo Bank y los de los plazos de 180/360 días, no activos, admiten holgura
amplia hacia arriba.

**Coeficientes objetivo $f_{ijk}$ de las variables activas.**

| Combinación activa | $f$ base | Límite inferior | Límite superior |
| --- | ---: | ---: | ---: |
| Bancolombia \| 180 \| 1 | 0,053755 | 0,051963 | $+\infty$ |
| Bancolombia \| 360 \| 2 | 0,120100 | 0,052043 | 0,256213 |
| Davivienda \| 720 \| 2 | 0,254848 | 0,118929 | $+\infty$ |
| Lulo Bank \| 180 \| 2 | 0,053565 | $-\infty$ | 0,055351 |

Interpretación: cada coeficiente $f_{ijk}$ puede moverse dentro de su intervalo
sin que cambie la base óptima (la cartera recomendada). Por ejemplo, el
rendimiento de Davivienda 720/2 puede subir sin límite sin alterar la solución
(ya está en el tope del plazo), pero si cayera por debajo de ≈ 0,1189 saldría de
la base; el de Lulo Bank 180/2 puede bajar sin límite, pero si subiera por encima
de ≈ 0,0554 convendría reasignar. Estos rangos acotan cuánto pueden moverse las
tasas antes de que la recomendación de cartera cambie, dando una medida directa
de la robustez de la solución.

### 6.5 Limitaciones del análisis

A diferencia de versiones anteriores de este trabajo —en las que el LP
restringido resultaba no degenerado—, **con las nuevas restricciones de liquidez
por fecha el LP restringido del escenario base resultó degenerado** (alguna
variable básica queda pegada a su cota, o hay una restricción activa con dual
nulo). El propio informe de sensibilidad lo advierte. La consecuencia práctica es
importante: **los precios sombra pueden no ser únicos** y el valor dual puede no
ser una derivada bien definida del objetivo respecto del recurso, de modo que los
rangos de la Sección 6.4 deben interpretarse **con cautela** como indicadores
locales y no como fronteras exactas.

Además, los rangos son numéricos (perturbación + re-solución), válidos "un
parámetro a la vez" y no cubren variaciones simultáneas (regla del 100 %). Y, de
nuevo, **todo el análisis aplica al LP restringido con $z = z^*$**: si cambia la
solución entera (por ejemplo, al mover $A$ lo suficiente como para cruzar el
umbral de un tramo o activar un cuarto banco), el conjunto de variables activas
cambia y el análisis dual debe rehacerse sobre la nueva base.

---

## 7. Conclusiones

Este trabajo formuló y resolvió la asignación de capital en CDT como un modelo
MILP y, sobre su solución entera, construyó el LP restringido que habilita el
análisis de dualidad y sensibilidad del curso. Los cuatro objetivos planteados
en la Introducción se cumplieron: (i) se maximizó el rendimiento efectivo total
con el coeficiente $f_{ijk}$; (ii) se incorporó la lógica de tasas escalonadas
por tramos con binarias y las restricciones de riesgo y liquidez, incluidas las
dos familias nuevas de **liquidez por fecha** y **concentración por plazo**;
(iii) se resolvió el modelo con PuLP/CBC **sobre tasas reales** de bancos
colombianos y se reportó la asignación óptima por banco, plazo y tramo; y (iv) se
interpretaron económicamente los precios sombra, se verificó la holgura
complementaria y se calcularon los rangos de estabilidad de la base.

**Hallazgos principales.** Sobre los datos reales del escenario base, la solución
óptima **reparte el capital entre 180, 360 y 720 días** para cumplir exactamente
las reglas de liquidez por fecha (30 % vence a $\le 180$ días; 60 % a $\le 360$
días) y el tope del 40 % por plazo, con un rendimiento efectivo de $Z^* =
15.405.781{,}00$ COP. El resultado más instructivo es la **cuantificación del
costo de oportunidad de la liquidez**: comparar el escenario base con uno sin
exigencia de liquidez ($Z^* = 24.832.031{,}60$ COP, todo a 720 días) arroja una
diferencia de $9.426.250{,}60$ COP, el precio en rendimiento de poder disponer de
caja en fechas intermedias. El análisis dual descompone ese costo en el margen:
el capital tiene valor marginal $\lambda^* = 0{,}1201$; la regla de liquidez a
180 días está activa con precio sombra **negativo** ($-0{,}066535$), señal de que
exigir liquidez a corto resta rendimiento; y el tope del plazo de 720 días está
activo con precio sombra positivo ($0{,}134748$), porque el modelo querría
concentrar más en el horizonte más rentable. La holgura complementaria se
verificó exactamente ($(x^*)^{\mathsf T} s^* = 0$).

**Limitaciones.** La más importante es metodológica y transversal: los precios
sombra y los rangos de sensibilidad son rigurosos solo sobre el **LP restringido
con las binarias fijadas**, no sobre el MILP original; si la solución entera
cambia, el análisis dual debe rehacerse sobre la nueva base. Con las nuevas
restricciones de liquidez por fecha, el LP restringido resultó **degenerado**,
por lo que los precios sombra pueden no ser únicos y los rangos deben leerse como
indicadores locales. Los rangos se obtienen además por perturbación numérica, un
parámetro a la vez, y no cubren variaciones simultáneas. En cuanto a los datos,
las tasas son reales y trazables por plazo, pero la desagregación por los tres
tramos de monto es un supuesto declarado (el mercado cotiza por plazo, no por
esos tramos); y las políticas de liquidez y de concentración por plazo son
supuestos de tesorería del equipo, no cifras de mercado. Finalmente, el modelo
ignora el riesgo de reinversión, los impuestos (retención en la fuente) y la
posibilidad de retiro anticipado.

**Trabajo futuro.** Entre las extensiones naturales están: incorporar el
tratamiento tributario y los costos de reinversión para plazos cortos; añadir una
componente de riesgo de crédito por emisor (más allá de la cobertura de Fogafín)
que module la diversificación; modelar escalonamiento de vencimientos (laddering)
multiperiodo para equilibrar liquidez y rendimiento de forma dinámica en lugar de
con reglas de un solo periodo; afinar las reglas de liquidez por fecha con
necesidades de caja reales del inversionista; y estudiar la sensibilidad del MILP
completo mediante reoptimización sistemática ante cambios de parámetros,
complementando el análisis dual del LP restringido.

---

## 8. Referencias

<!--
Referencias de las secciones 2 (Introducción), 3 (Revisión de Literatura) y
5-6 (Resultados/Discusión) — Requisito 5.7. Fuentes reales; sin DOIs inventados.
La nota final documenta la procedencia de las tasas REALES de la Sección 5 y el
alcance de los supuestos (desagregación por tramo y política de liquidez).
-->

[1] Banco de la República. *Certificado de depósito a término (CDT)* (entrada de glosario). Disponible en: https://www.banrep.gov.co/es/glosario/certificado-deposito-termino-cdt

[2] Fondo de Garantías de Instituciones Financieras (Fogafín). *¿Qué es el Seguro de Depósitos?* Disponible en: https://www.fogafin.gov.co/que-es-el-seguro-de-depositos

[3] Superintendencia Financiera de Colombia. *Portal institucional — información y protección del consumidor financiero.* Disponible en: https://www.superfinanciera.gov.co/

[4] Banco de la República. *Tasas de captación de los CDT* (entrada de glosario). Disponible en: https://www.banrep.gov.co/es/glosario/tasas-captacion

[5] Markowitz, H. (1952). Portfolio Selection. *The Journal of Finance*, 7(1), 77–91.

[6] Dantzig, G. B. (1963). *Linear Programming and Extensions.* Princeton University Press.

[7] Bertsimas, D., & Shioda, R. (2009). Algorithm for cardinality-constrained quadratic optimization. *Computational Optimization and Applications*, 43(1), 1–22.

[8] Graham, R. L., Lawler, E. L., Lenstra, J. K., & Rinnooy Kan, A. H. G. (1979). Optimization and approximation in deterministic sequencing and scheduling: a survey. *Annals of Discrete Mathematics*, 5, 287–326.

[9] Pinedo, M. L. (2016). *Scheduling: Theory, Algorithms, and Systems* (5a ed.). Springer.

[10] Wolsey, L. A. (1998). *Integer Programming.* Wiley-Interscience.

[11] Nemhauser, G. L., & Wolsey, L. A. (1988). *Integer and Combinatorial Optimization.* Wiley.

[12] Williams, H. P. (2013). *Model Building in Mathematical Programming* (5a ed.). Wiley.

> **Nota de atribución.** El contexto del mercado colombiano de CDT (naturaleza del instrumento, tasas de captación y seguro de depósitos) se apoya en fuentes públicas del Banco de la República, la Superintendencia Financiera de Colombia y Fogafín, parafraseadas para esta redacción. Contenido reformulado para cumplir con restricciones de licenciamiento.

> **Nota sobre las tasas usadas en Resultados (Req. 1.5 y 5.7) — datos REALES con un supuesto de desagregación acotado.** A diferencia de versiones anteriores, los números de las Secciones 5 y 6 se generan sobre **tasas reales** de entidades colombianas vigiladas por la Superintendencia Financiera, con corte a octubre de 2026, registradas en `data/cdt_productos.csv`: 90 de las 105 combinaciones $(i, j, k)$ son reales y utilizables (`es_supuesto = False`), y 15 quedan marcadas `es_supuesto = True` solo porque el banco no ofrece ese plazo (Nu Bank a 30/60 días; Lulo Bank a 30/60/720 días), no porque la tasa sea inventada. Las tasas de Bancolombia y Davivienda provienen del promedio ponderado E.A. reportado por la SFC (corte 29-oct-2026); las de Banco de Bogotá, Nu Bank y Lulo Bank, de sus tarifarios digitales por plazo vigentes en octubre de 2026 (ver la columna `fuente` de cada fila del CSV y los enlaces allí citados, p. ej. comparatodo.com.co y ahorrar.com.co como agregadores de referencia). **El único supuesto sobre las tasas es su desagregación por los tres tramos de monto**: como el mercado colombiano cotiza el CDT por plazo y no por esos tramos, la tasa real del plazo se aplica a los tres tramos (en ese rango el mercado no premia el monto); la tasa en sí no es un supuesto. Por su parte, las **políticas de liquidez por fecha** ($\ell_{180} = 0{,}30$, $\ell_{360} = 0{,}60$) y de **concentración por plazo** ($q_{\text{default}} = 0{,}40$), definidas en `data/config.py`, son supuestos de tesorería del equipo —no cifras de mercado— y así se declaran en la Sección 4.2.
