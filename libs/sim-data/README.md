# Sim Data

Physics-informed sensor and incident simulator, per `ARCHITECTURE.md` §17.4. Generates realistic multi-signal time series (including injected failure scenarios like the "Predicted Leak" journey, `ARCHITECTURE.md` §5.1) that publish onto the same `telemetry.raw` schema a real MQTT/OPC-UA adapter would use — so swapping in real hardware later requires zero downstream changes.

Empty in this scaffold. Built out in `DEVELOPMENT_ROADMAP.md` M59-M60 (baseline generator, then the failure-injection scenario library).
