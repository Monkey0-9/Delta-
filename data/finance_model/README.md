# DELTA Finance Model Dataset

Every example MUST preserve temporal provenance.

Required fields:

- sample_id
- task
- instruction
- input
- target
- event_time
- available_time
- source_id
- source_version
- source_hash
- dataset_version

Rules:

1. No look-ahead information.
2. No future labels inside model inputs.
3. No duplicate sample IDs.
4. Every external source requires provenance.
5. Training/evaluation splits are chronological.
6. Test data must never influence training configuration.
7. Data revisions must create new dataset versions.
8. Dataset manifests must be immutable after release.