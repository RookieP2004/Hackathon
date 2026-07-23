# Shared Schemas

Source-of-truth event and API contracts, per `ARCHITECTURE.md` §10.3 (Kafka topic schemas) and §22.2 (OpenAPI/Protobuf-first API design). Both Python services and the Next.js frontend generate their typed clients/consumers from the files in this folder — nothing here is language-specific.

```
libs/schemas/
├── events/       # Avro / JSON-Schema definitions per Kafka topic (telemetry.raw, risk.updated, ...)
└── openapi/      # OpenAPI specs per service, used for typed frontend API client generation
```

Empty in this scaffold. First schemas are added in `DEVELOPMENT_ROADMAP.md` M55 (`telemetry.raw`, `anomaly.detected`, `risk.updated`), with CI compatibility checking wired in M56.
