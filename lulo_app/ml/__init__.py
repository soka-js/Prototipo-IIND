"""Modelos entrenados sobre la base del reto (propensión, segmentos, momento y canal).

El entrenamiento corre fuera de producción (`scripts/train_models.py`, con scikit-learn) y deja los
parámetros en `modelos.json`. En producción solo se calcula con Python puro: no agrega dependencias.
"""
