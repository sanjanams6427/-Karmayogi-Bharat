@echo off
:: Activate the correct Python 3.12 environment for this project
:: Usage: call activate_env.bat  (or double-click)

set "PYTHON=C:\Users\M1021\AppData\Local\Programs\Python\Python312\python.exe"
set "PIP=C:\Users\M1021\AppData\Local\Programs\Python\Python312\Scripts\pip.exe"

:: Override PATH so 'python' resolves to py-3.12 in this session
set "PATH=C:\Users\M1021\AppData\Local\Programs\Python\Python312;C:\Users\M1021\AppData\Local\Programs\Python\Python312\Scripts;%PATH%"

echo [ENV] Python 3.12 activated
python --version
echo [ENV] CUDA check:
python -c "import torch; print('  CUDA:', torch.cuda.is_available(), '| GPUs:', torch.cuda.device_count(), '| torch:', torch.__version__)"
echo.
