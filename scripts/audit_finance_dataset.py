from __future__ import annotations

import argparse

from finance_model.datasets.factory import DatasetFactory


def main() -> None:
    parser = argparse.ArgumentParser(
        description="DELTA point-in-time dataset audit"
    )

    parser.add_argument(
        "dataset",
        help="Path to JSONL dataset",
    )

    parser.add_argument(
        "--dataset-id",
        required=True,
    )

    parser.add_argument(
        "--version",
        default="1.0.0",
    )

    parser.add_argument(
        "--manifest",
        default="data/finance_model/manifests/dataset.json",
    )

    args = parser.parse_args()

    factory = DatasetFactory(strict=True)

    artifact = factory.build_from_jsonl(
        args.dataset,
        dataset_id=args.dataset_id,
        version=args.version,
    )

    manifest = factory.write_manifest(
        artifact,
        args.manifest,
    )

    print("DELTA DATASET AUDIT")
    print("===================")
    print(f"Dataset       : {artifact.dataset_id}")
    print(f"Version       : {artifact.version}")
    print(f"Records       : {artifact.record_count}")
    print(f"SHA-256       : {artifact.dataset_hash}")
    print(f"PIT integrity : {artifact.leakage_passed}")
    print(f"Manifest      : {manifest}")


if __name__ == "__main__":
    main()