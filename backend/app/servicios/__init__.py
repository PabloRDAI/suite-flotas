"""Servicios: unen el motor de reglas (Python puro) con la base de datos.

Un servicio reúne de la BD los datos que necesita una regla, la ejecuta y guarda
el resultado. Así los routers no repiten esa lógica y las reglas no dependen de la BD.
"""
