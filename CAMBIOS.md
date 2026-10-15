# Registro de cambios

Todo cambio al repositorio se anota aquí, el más reciente arriba. Es obligatorio (ver `CLAUDE.md`, sección 4).

## Formato de cada entrada

```
## AAAA-MM-DD · <autor> · rama <rama> · commit <hash corto>
- Qué cambió:
- Por qué:
- Archivos:
- Cómo se verificó: <salida real de pytest / backtest / CLI>
- Consultado con SOKA: sí (fecha y qué aprobó) / no aplica (cambio pequeño de la sección 2)
- Cifras nuevas y su origen: <de qué pestaña o cálculo sale cada una> / ninguna
- Modelo de Claude usado: <id del modelo>
```

---

## 2026-10-14 · Claude con SOKA · rama v3 · commit (este commit)
- Qué cambió: reglas de colaboración para compartir el repo con el equipo. `CLAUDE.md` con el modelo permitido, el alcance, qué es un cambio grande, la documentación obligatoria, las invariantes, el plan y el flujo de git. Además `.claude/settings.json`, que fija el modelo `best` y bloquea push a `main` y `v2-cliente`, push forzado y la edición manual de la base. También este registro, `.github/CODEOWNERS` y la plantilla de pull request.
- Por qué: SOKA va a compartir el repo con compañeros y pidió que sus instancias de Claude sigan solo lo planeado, usen el modelo más capaz, consulten los cambios grandes y documenten todo.
- Archivos: `CLAUDE.md`, `CAMBIOS.md`, `.claude/settings.json`, `.github/CODEOWNERS`, `.github/pull_request_template.md`, `README.md`.
- Cómo se verificó: `python -m pytest` → 58 passed; `.claude/settings.json` es JSON válido.
- Consultado con SOKA: sí, lo pidió el 2026-10-14.
- Cifras nuevas y su origen: ninguna.
- Modelo de Claude usado: claude-opus-5-5.

## 2026-10-10 · Claude con SOKA · rama v3 · commits 118b1d1 a 0db4181
Construcción de la versión 3, por etapas, con aprobación de SOKA en cada punto de control.

- **118b1d1 · E1 Ingesta.** Se agregaron `scripts/ingest_reto.py` y `lulo_app/dataset/` (CSV, `manifest.json`, `CALIDAD.md`). Verificación: 33 passed y reingesta idéntica byte a byte. Cifras: 444 movimientos y 118 abonos posteriores al corte excluidos; `conversion_impactados` = ventas/elegibles en 5 de 5 filas (Campanas_Previas).
- **66a483d · E2 Motor v3.** Se agregó `lulo_app/core` con reglas v1 aprobadas por SOKA: tabla de cobertura, valor esperado, control 10 %, banner al tope y 56+ excluido. Verificación: 50 passed y backtest con 0 violaciones.
- **bc80632 · Reglas v1.1.** Fecha límite primero, 7 días entre push y próximos disparos, aprobados por SOKA. Verificación: 52 passed y backtest con 0 violaciones.
- **2451b01 · E3 API v3.** Se agregaron `/api/v3` y Tu año calculado con el motor. Verificación: 57 passed. Cifra: Sebastián conserva $33 M (suma de ingresos de los 365 días del periodo).
- **8b76534 · E4 App v3.** Look de la app real; `/` sirve v3 y `/v2` conserva la versión del cliente. Verificación: 58 passed, la demo guiada de 16 pasos corre sin errores de consola y el Preview de Vercel quedó en `success`. Los colores salen de capturas de la app real.
- **0db4181 · Ajustes.** Tipografía y densidad como la app real; coberturas en el catálogo. Verificación: 58 passed y Preview en `success`.
- Modelo de Claude usado: claude-opus-5-5.
