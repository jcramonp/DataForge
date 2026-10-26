"""Metadata-driven pipeline orchestration (#24).

Modules (imported directly; entrypoints are not re-exported here):

- ``plan``: validate a request against its contract and resolve stages/targets.
- ``stages``: one function per stage, delegating to the existing generic runners.
- ``state``: orchestration run/task state in the control plane (migration 0006).
- ``executor``: run a stage attempt with state tracking, logging and retry classification.
- ``pipeline``: standalone CLI runner (``python -m src.orchestration.pipeline``).
- ``airflow_client``: trigger and monitor ``dataforge_pipeline`` through the Airflow REST API.
"""
