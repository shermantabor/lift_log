# Lift Log

Lift Log is a simple command-line application for tracking weightlifting sessions.
It focuses on reliable data entry, persistence, and basic querying.

This repository currently contains **Phase 1** of the project: a local CLI backed
by SQLite.

---

## Current Features (Phase 1)

- Log sets with:
  - weight
  - reps
  - optional 1RM flag
- Persist data locally using SQLite
- Simple menu-driven CLI
- Clear separation between:
  - database logic
  - business logic
  - user interaction

---

## Project Structure


All current code lives in `src/`.  
Additional directories (tests, config, UI, etc.) will be added in later phases.

---

## Requirements

- Python 3.10+
- Standard library only (no external dependencies)

---

## Running the App

From the project root:

```bash
python src/main.py
