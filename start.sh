sudo apt install -y tmux

tmux new -spython -d "python main.py"
gunicorn app:app