# Dashboard extension LWCs (phase P4)

Four dynamically bound extensions, all with `analytics__Dashboard` target, `apiVersion` 67.0, `masterLabel`/`description`, and `targetConfigs` using the `SemanticModel` / `SemanticMeasure` / `SemanticDimension` property types.

| Component | Bound properties | Behavior |
|---|---|---|
| `cumulusKpiTile` | model, measure, target (number) | Big number + delta vs prior period + sentiment; re-queries on `FILTER_CHANGE` |
| `cumulusRankedBars` | model, dimension, measure | Top-N bars; click → `applyFilter` |
| `cumulusNextBestActions` | model, 2 dimensions, measure | Ranked action list; click → `applyFilter` |
| `cumulusThresholdBanner` | model, measure, threshold (number) | Red banner above threshold; one-click filter via `applyParameter` |

Shared rules: `isConfigured` guard + configuration message, `limitOptions.limit` always set, `notifyLifecycleChange` for INIT/LOADED/NODATA/ERROR, unsubscribe in `disconnectedCallback`, keyboard + ARIA for interactive marks.
