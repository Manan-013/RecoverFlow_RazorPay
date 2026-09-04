@echo off
echo ===================================================
echo   RecoverFlow AI - Setup and Demo Launcher
echo ===================================================
echo.
echo [Step 1] Checking Python installation...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH. Please install Python 3.10+
    pause
    exit /b
)

echo [Step 2] Installing dependencies from requirements.txt...
python -m pip install -r requirements.txt >nul 2>&1

echo [Step 3] Generating Synthetic failed transaction dataset...
python generate_data.py
echo.

echo [Step 4] Running Automated Compliance Unit Tests...
python -m unittest verify_recovery.py
if %errorlevel% neq 0 (
    echo [WARNING] Some tests failed. Please check files.
)
echo.

echo [Step 5] Running Batch Simulation Engine...
python batch_engine.py
echo.

echo [Step 6] Launching Visual Dashboard on Streamlit...
echo.
echo Launching Streamlit web app... Browser should open automatically to http://localhost:8501
streamlit run app.py
pause
