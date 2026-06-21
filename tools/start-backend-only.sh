#!/bin/bash
export PYTHONUTF8=1
cd "d:/noveos/novel-os"
python -m uvicorn api.main:app --host 127.0.0.1 --port 8001 > "d:/noveos/logs/backend.log" 2>&1 &
echo $!
