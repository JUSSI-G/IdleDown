pip install -r requirements-dev.txt
pyinstaller --onefile --windowed --name IdleDown --icon assets\IdleDown.ico --add-data "assets;assets" --clean main.py
