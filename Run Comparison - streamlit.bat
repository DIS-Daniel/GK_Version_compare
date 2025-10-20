@echo off
REM Activate your virtual environment if needed
REM Example: call C:\path\to\venv\Scripts\activate.bat

REM Navigate to the folder containing app.py
cd /d "C:\path\to\your\app\folder"

REM Run the Streamlit app
streamlit run app.py

pause
