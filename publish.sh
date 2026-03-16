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
# Use API token auth. Set PYPI_TOKEN env var or you'll be prompted.
if [ -n "$PYPI_TOKEN" ]; then
    python3 -m twine upload dist/* --username __token__ --password "$PYPI_TOKEN"
else
    echo "Tip: set PYPI_TOKEN env var to avoid interactive prompt."
    echo "  Generate a token at https://pypi.org/manage/account/token/"
    python3 -m twine upload dist/* --username __token__
fi

echo "Publish complete!"
