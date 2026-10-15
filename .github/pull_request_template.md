## Qué cambia y por qué

## Tipo de cambio (ver CLAUDE.md, secciones 2 y 3)
- [ ] Pequeño y coherente con lo construido (bug, texto, pruebas, documentación, ajuste visual)
- [ ] Grande: aprobado por SOKA el ____ (pega o enlaza la aprobación)

## Verificación
- [ ] `python -m pytest`: 0 fallas (pega la salida)
- [ ] Si toqué el motor: `python -m lulo_app.core backtest` con 0 violaciones (pega la salida)
- [ ] No rompí ninguna invariante de la sección 5 de CLAUDE.md

## Documentación
- [ ] Entrada nueva en `CAMBIOS.md`
- [ ] Si cambió una regla: `VERSION` y `CHANGELOG` en `lulo_app/core/rules.py`
- [ ] Cifras nuevas con su origen

## Modelo de Claude usado
<!-- id del modelo; solo se permite el más capaz disponible (CLAUDE.md, sección 1) -->
