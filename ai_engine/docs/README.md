# AI technical references and historical evidence

Use the [engine README](../README.md) for current commands, model selection and module boundaries, and [evaluation guide](../eval/README.md) for measurement.

## Technical references

- [Port handover and parity constraints](port-handover.md)
- [Cadence measurement](cadence-measurement.md)
- [Training and evaluation provenance](training_docs/README.md)
- [Diagnostic tools](../diagnostics/README.md)
- [GPU prototypes cited by production code](../prototypes/README.md)

## Historical plans and reports

The dated design/plan files and `AI_ENGINE_*` investigation, integration and handoff documents in this directory record the evolution of the implemented engine. Their execution/approval instructions are historical and must not be replayed as current tasks. Measurements and limitations retain their original scope; relocation or indexing does not revalidate them.

In particular, the [GPU integration plan](AI_ENGINE_GPU_INTEGRATION_PLAN.md), [pipeline handoff](AI_ENGINE_GPU_PIPELINE_IMPLEMENTATION_HANDOFF.md) and [prototype report](AI_ENGINE_GPU_RESIDENT_PROTOTYPE_REPORT.md) provide provenance for the implemented GPU path. Preserve referenced arithmetic and parity evidence.
