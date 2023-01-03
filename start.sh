#!/usr/bin/env bash
apt-get install -y tmux

tmux new -spython -d "python3 main.py"
gunicorn app:app