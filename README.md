# Optimización de circuitos digitales mediante álgebra booleana

Proyecto final de **MAT 4021 – Matemáticas Discretas**, Universidad del Norte.
Profesor: MSc. Iván Gómez Gómez. Noviembre de 2026.

**Integrantes:** Emmanuel Kohen Morales, Luis Lafauri Yaguna, Javier Leguizamo Mora,
Samuel Romero Martínez y Henry Torres Mantilla.

## El problema

Al llevar una especificación lógica a hardware, lo directo es escribir la expresión tal como
sale de la tabla de verdad: la forma canónica en suma de productos (SOP). Esa expresión suele
tener compuertas de más, y cada compuerta ocupa área de silicio, consume energía al cambiar de
estado y genera calor. La pregunta del proyecto es: **¿cuánto se puede reducir un circuito
combinacional sin cambiar lo que hace?**

## La solución

El programa `karnaugh.py` recibe **cualquier función booleana de 1 a 4 variables**, escrita
como expresión o como lista de mintérminos, y la simplifica con mapas de Karnaugh y el método de
Quine–McCluskey. Explica cada paso, verifica que la expresión simplificada es equivalente a la
original y calcula tres métricas del circuito:

| Métrica | Cómo se cuenta |
|---|---|
| Número de literales | Cada aparición de una variable, directa o complementada |
| Compuertas lógicas | Una AND por cada término con 2 o más literales, más una OR si hay 2 o más términos (las NOT no se cuentan) |
| Porcentaje de reducción | %R = (1 − optimizado / original) · 100, donde el original es la forma canónica SOP |

En el documento se desarrolla paso a paso un ejemplo, el segmento *e* del display BCD de 7
segmentos, y el programa se aplica también al display completo y a otras funciones (ver
[Ejemplos](#ejemplos)).

## Contenido del repositorio

| Archivo | Qué es |
|---|---|
| `karnaugh.py` | El programa (un solo archivo, solo usa la biblioteca estándar de Python) |
| `README.md` | Este archivo |

## Requisitos

- **Python 3.8 o superior.** No hay que instalar paquetes con `pip`.
- Para la interfaz gráfica, **tkinter**, que ya viene con Python en Windows y macOS.
  En Linux puede faltar; se instala con:
  ```bash
  sudo apt install python3-tk
  ```
  La versión de consola funciona sin tkinter.

Para comprobar la versión:

```bash
python --version
```

En macOS y Linux el comando puede ser `python3` en lugar de `python`.

## Descargar el proyecto

Con Git:

```bash
git clone https://github.com/SamuelRomero01/optimizacion-circuitos-karnaugh.git
cd optimizacion-circuitos-karnaugh
```

Sin Git: en la página del repositorio, botón **Code → Download ZIP**, y descomprimir.

## Ejecutar

### Interfaz gráfica

```bash
python karnaugh.py
```

Se escribe la función en el cuadro de texto y se pulsa **Simplificar**. La ventana muestra el
mapa paso a paso (estructura, llenado, implicantes primos, esenciales y resultado) y dos
pestañas más: **Métricas del circuito** y **Tabla de verdad**.

### Consola

Se pasa la función entre comillas, por ejemplo:

```bash
python karnaugh.py "f(x,y,z) = x·y + z'"
```

Imprime los mismos pasos, la expresión mínima, la verificación y el cuadro de métricas.

## Formatos de entrada

| Tipo | Ejemplos |
|---|---|
| Expresión | `x·y + z'` · `(p∨q)∧¬(p∧q)` · `(x+y)(x+y^c)` · `a ⊕ b` |
| Mintérminos | `m(2,3,6,7)` · `Σm(0,2,6,8) + d(10-15)` |
| Orden de variables (opcional) | `f(w,x,y,z) = ...` |

`d(...)` son las condiciones «no importa» (X): combinaciones que nunca ocurren y que el programa
puede usar como 1 si eso da grupos más grandes.

| Operación | Símbolos aceptados |
|---|---|
| O (suma) | `+` `∨` `\|` `or` |
| Y (producto) | `·` `*` `&` `∧` `and`, o juntar las variables: `xy` |
| NO | `x'` `x^c` `¬x` `~x` `!x` `not x` |
| O exclusivo | `⊕` `^` `xor` |
| Implicación / bicondicional | `→` `->` / `↔` `<->` |
| Constantes | `0` `1` |

Precedencia: NO > Y > ⊕ > O > → > ↔. Ante la duda, usar paréntesis.

## Ejemplos

El programa no está hecho para una función en particular. Estos son algunos resultados, todos
verificados contra la función original en todas las filas de la tabla de verdad:

| Comando | Expresión mínima | Literales | Compuertas |
|---|---|---|---|
| `python karnaugh.py "(p∨q)∧¬(p∧q)"` | p'q + pq' | 4 → 4 (0 %) | 3 → 3 (0 %) |
| `python karnaugh.py "(x+y)(x+y')"` | x | 4 → 1 (75,0 %) | 3 → 0 (100 %) |
| `python karnaugh.py "f(x,y,z) = x·y + z'"` | z' + xy | 15 → 3 (80,0 %) | 6 → 2 (66,7 %) |
| `python karnaugh.py "f(A,B,C) = m(0,1,2,5,6,7)"` | A'B' + BC' + AC | 18 → 6 (66,7 %) | 7 → 4 (42,9 %) |
| `python karnaugh.py "f(A,B,C,D) = m(1,3,4,6,9,11)"` | B'D + A'BD' | 24 → 5 (79,2 %) | 7 → 3 (57,1 %) |
| `python karnaugh.py "f(w,x,y,z) = m(2,3,6,7,10,11,14,15)"` | y | 32 → 1 (96,9 %) | 9 → 0 (100 %) |

El O exclusivo ya era mínimo, y el programa lo reporta sin inventar una mejora. La función
m(0,1,2,5,6,7) no tiene implicantes esenciales y admite dos soluciones mínimas; el programa
entrega una de ellas.

Estos ejemplos también están en la lista «Ejemplos» de la interfaz gráfica.

### Aplicación: display BCD de 7 segmentos

Un decodificador BCD recibe un dígito del 0 al 9 en binario (wxyz, con w el bit más
significativo) y enciende los segmentos del display. Cada segmento es una función booleana de
cuatro variables. Las entradas 10 a 15 no son BCD válido, así que son condiciones «no importa».

#### Segmento *e*, el ejemplo que el documento desarrolla paso a paso

El segmento *e* se enciende en los dígitos 0, 2, 6 y 8.

```bash
python karnaugh.py "e(w,x,y,z) = m(0,2,6,8) + d(10-15)"
```

Resultado esperado:

```
f(w,x,y,z) = x'z' + yz'
  Literales:   16 → 4   (%R = 75.0 %)
  Compuertas:  5 → 3   (%R = 40.0 %)
Optimizada sin usar las X (tratándolas como 0):
   f(w,x,y,z) = w'yz' + x'y'z'
```

Sin las X la expresión queda con 6 literales (%R = 62,5 %); con ellas, 4 (%R = 75 %).

#### El display completo

| Segmento | Comando | Expresión mínima | Literales | Compuertas |
|---|---|---|---|---|
| a | `python karnaugh.py "a(w,x,y,z) = m(0,2,3,5,6,7,8,9) + d(10-15)"` | x'z' + y + xz + w | 32 → 6 | 9 → 3 |
| b | `python karnaugh.py "b(w,x,y,z) = m(0,1,2,3,4,7,8,9) + d(10-15)"` | x' + y'z' + yz | 32 → 5 | 9 → 3 |
| c | `python karnaugh.py "c(w,x,y,z) = m(0,1,3,4,5,6,7,8,9) + d(10-15)"` | y' + z + x | 36 → 3 | 10 → 1 |
| d | `python karnaugh.py "d(w,x,y,z) = m(0,2,3,5,6,8,9) + d(10-15)"` | x'z' + x'y + xy'z + yz' + w | 28 → 10 | 8 → 5 |
| e | `python karnaugh.py "e(w,x,y,z) = m(0,2,6,8) + d(10-15)"` | x'z' + yz' | 16 → 4 | 5 → 3 |
| f | `python karnaugh.py "f(w,x,y,z) = m(0,4,5,6,8,9) + d(10-15)"` | y'z' + xy' + xz' + w | 24 → 7 | 7 → 4 |
| g | `python karnaugh.py "g(w,x,y,z) = m(2,3,4,5,6,8,9) + d(10-15)"` | x'y + xy' + w + yz' | 28 → 7 | 8 → 4 |
| **Total** | | | **196 → 42 (78,6 %)** | **56 → 23 (58,9 %)** |

`(w,x,y,z)` fija el nombre y el orden de las variables; w es el bit más significativo. Si se
omite, el programa las llama A, B, C, D. En la salida la función siempre se imprime como
`f(w,x,y,z)`.

## Limitaciones

- Admite hasta 4 variables, para que el mapa de Karnaugh siga siendo legible.
- Solo produce formas de dos niveles (suma de productos).
- Las métricas cuentan literales y compuertas, no transistores ni consumo medido.
