#!/bin/bash

OUTPUT="smartcart_repo_snapshot.md"

{
    echo "# SmartCart AI — Repository Snapshot"
    echo
    echo "Generated: $(date)"
    echo
    echo "============================================================"
    echo "## 1. PROJECT STRUCTURE"
    echo "============================================================"
    echo

    find . \
        -not -path './.git/*' \
        -not -path './.venv/*' \
        -not -path '*/__pycache__/*' \
        -not -path '*/.pytest_cache/*' \
        -not -path '*/.mypy_cache/*' \
        -not -name '.DS_Store' \
        -print | sort

    echo
    echo "============================================================"
    echo "## 2. GIT STATUS"
    echo "============================================================"
    echo
    git status --short 2>/dev/null || true

    echo
    echo "============================================================"
    echo "## 3. RECENT GIT HISTORY"
    echo "============================================================"
    echo
    git log --oneline -10 2>/dev/null || true

    echo
    echo "============================================================"
    echo "## 4. ROOT FILES"
    echo "============================================================"

    for file in README.md requirements.txt pyproject.toml setup.py setup.cfg \
                .gitignore .python-version Makefile Dockerfile docker-compose.yml \
                compose.yml; do

        if [ -f "$file" ]; then
            echo
            echo "------------------------------------------------------------"
            echo "FILE: $file"
            echo "------------------------------------------------------------"
            echo
            cat "$file"
        fi
    done

    echo
    echo "============================================================"
    echo "## 5. PYTHON SOURCE FILES"
    echo "============================================================"

    find . \
        -not -path './.git/*' \
        -not -path './.venv/*' \
        -not -path '*/__pycache__/*' \
        -not -path '*/.pytest_cache/*' \
        -type f \
        -name '*.py' \
        -print | sort |
    while IFS= read -r file; do
        echo
        echo "------------------------------------------------------------"
        echo "FILE: $file"
        echo "------------------------------------------------------------"
        echo
        cat "$file"
    done

    echo
    echo "============================================================"
    echo "## 6. CONFIGURATION FILES"
    echo "============================================================"

    find . \
        -not -path './.git/*' \
        -not -path './.venv/*' \
        -not -path '*/__pycache__/*' \
        -not -path '*/.pytest_cache/*' \
        -type f \
        \( \
            -name '*.toml' \
            -o -name '*.yaml' \
            -o -name '*.yml' \
            -o -name '*.ini' \
            -o -name '*.cfg' \
            -o -name 'requirements*.txt' \
        \) \
        -print | sort |
    while IFS= read -r file; do
        echo
        echo "------------------------------------------------------------"
        echo "FILE: $file"
        echo "------------------------------------------------------------"
        echo
        cat "$file"
    done

    echo
    echo "============================================================"
    echo "## 7. MARKDOWN / DOCUMENTATION"
    echo "============================================================"

    find . \
        -not -path './.git/*' \
        -not -path './.venv/*' \
        -not -path '*/__pycache__/*' \
        -type f \
        -name '*.md' \
        -print | sort |
    while IFS= read -r file; do
        echo
        echo "------------------------------------------------------------"
        echo "FILE: $file"
        echo "------------------------------------------------------------"
        echo
        cat "$file"
    done

    echo
    echo "============================================================"
    echo "## 8. JSON DATA"
    echo "============================================================"

    find . \
        -not -path './.git/*' \
        -not -path './.venv/*' \
        -not -path '*/__pycache__/*' \
        -type f \
        -name '*.json' \
        -print | sort |
    while IFS= read -r file; do
        echo
        echo "------------------------------------------------------------"
        echo "FILE: $file"
        echo "------------------------------------------------------------"
        echo

        # Avoid dumping huge JSON files blindly.
        SIZE=$(wc -c < "$file")

        if [ "$SIZE" -le 200000 ]; then
            cat "$file"
        else
            echo "[JSON file is ${SIZE} bytes — omitted from snapshot]"
        fi
    done

    echo
    echo "============================================================"
    echo "## 9. CSV / TABULAR DATA"
    echo "============================================================"

    find . \
        -not -path './.git/*' \
        -not -path './.venv/*' \
        -not -path '*/__pycache__/*' \
        -type f \
        \( -name '*.csv' -o -name '*.tsv' \) \
        -print | sort |
    while IFS= read -r file; do
        echo
        echo "------------------------------------------------------------"
        echo "FILE: $file"
        echo "------------------------------------------------------------"
        echo

        echo "[File size: $(du -h "$file" | cut -f1)]"
        echo
        head -30 "$file"
        echo
        echo "[Only first 30 lines shown]"
    done

    echo
    echo "============================================================"
    echo "## 10. FILE INVENTORY WITH SIZES"
    echo "============================================================"

    find . \
        -not -path './.git/*' \
        -not -path './.venv/*' \
        -not -path '*/__pycache__/*' \
        -not -name '.DS_Store' \
        -type f \
        -print0 |
    xargs -0 ls -lh 2>/dev/null |
    awk '{print $5, $9}'

    echo
    echo "============================================================"
    echo "## END OF SNAPSHOT"
    echo "============================================================"

} > "$OUTPUT"

echo
echo "Repository snapshot created:"
echo "  $OUTPUT"
echo
echo "Size:"
du -h "$OUTPUT"
