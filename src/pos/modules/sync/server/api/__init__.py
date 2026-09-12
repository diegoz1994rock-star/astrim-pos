"""API HTTP de negocio (ASTRIM) — expuesta por la misma estación "servidor
principal" que ya embebe `sync/server/app.py`, en el mismo puerto y proceso.

Fase 1 (ver PROGRESS.md/ROADMAP.md, "App Android"): solo autenticación por
token e infraestructura transversal (middleware, health check). Los
endpoints de negocio (productos, ventas, pedidos, etc.) se agregan en fases
posteriores sobre esta misma base, sin repetirla."""

from __future__ import annotations
