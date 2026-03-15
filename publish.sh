#!/usr/bin/env bash

set -e

# Ensure we're in the project root containing pyproject.toml
if [ ! -f "pyproject.toml" ]; then
    echo "Error: pyproject.toml not found. Please run this script from the project root."
    exit 1
fi

echo "Cleaning up previous builds..."
rm -rf dist/ build/ *.egg-info/

echo "Upgrading build tools..."
python3 -m pip install --upgrade build twine

echo "Building distribution packages..."
python3 -m build

echo "Verifying build..."
python3 -m twine check dist/*

echo "Uploading to PyPI..."
python3 -m twine upload dist/*

echo "Publish complete!"
