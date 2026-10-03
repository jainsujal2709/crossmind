#!/bin/sh
. venv/bin/activate
cd backend && uvicorn main:app --reload --port 8000
