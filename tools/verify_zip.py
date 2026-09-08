# ruff: noqa
import os
import sys
import zipfile


def main() -> None:
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    zip_path = os.path.join(root_dir, "submission.zip")

    if not os.path.exists(zip_path):
        print(f"ERROR: {zip_path} not found", file=sys.stderr)
        sys.exit(1)

    expected_files = {"agent.py", "search.py", "evaluation.py"}

    with zipfile.ZipFile(zip_path, "r") as zf:
        zip_members = set(zf.namelist())

        if zip_members != expected_files:
            print("ERROR: Zip contents mismatch!", file=sys.stderr)
            print(f"Expected exactly: {expected_files}", file=sys.stderr)
            print(f"Found in zip: {zip_members}", file=sys.stderr)
            sys.exit(1)

        for filename in expected_files:
            root_filepath = os.path.join(root_dir, filename)
            if not os.path.exists(root_filepath):
                print(f"ERROR: {filename} missing from repo root", file=sys.stderr)
                sys.exit(1)

            with open(root_filepath, "rb") as f:
                root_bytes = f.read()

            zip_bytes = zf.read(filename)

            if root_bytes != zip_bytes:
                print(f"ERROR: {filename} is stale in zip", file=sys.stderr)
                sys.exit(1)

    print("Zip verification passed.", file=sys.stderr)


if __name__ == "__main__":
    main()
