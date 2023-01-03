#!/usr/bin/bash
sudo apt install -y tmux

tmux new -spython -d "python3 main.py"
gunicorn app:app