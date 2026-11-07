# Shared Contracts

Phase 1 reserved this package for versioned shared contracts. Phase 2 implements typed API request/response models in `services/api/src/restaurant_api/schemas.py`, publishes OpenAPI at `/openapi.json`, and uses explicit frontend types in `apps/web/app/settings/types.ts`.

This package still contains no generated executable contracts. Frontend types are maintained manually and can drift; automatic generation is remaining technical debt. The edge-event shape in `docs/api_contract.md` remains planned for later ingestion work. Phase 2 does not implement edge events, device credentials, or synchronization.

Phase 3 adds strict dashboard/task/event/action schemas in `services/api/src/restaurant_api/workflow_schemas.py`, OpenAPI resource routes, versioned SSE event frames and frontend types in `apps/web/app/dashboard/types.ts`. PostgreSQL table events represent synthetic/manual/configuration changes; they are not the future authenticated edge-ingestion contract. API/transport/browser checks exercise the current shapes. Generating frontend types from OpenAPI remains future maintenance.
