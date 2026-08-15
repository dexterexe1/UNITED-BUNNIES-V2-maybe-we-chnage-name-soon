@echo off
echo Creating United Bunnies Revenue Database...

:: Create the directory
mkdir "C:\Users\%USERNAME%\UnitedBunniesBot" 2>nul

:: Create a simple SQLite database using Windows commands
echo Creating revenue_data.db...

:: Try to find Python in common locations
set PYTHON_FOUND=0

if exist "C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python311\python.exe" (
    set PYTHON_PATH="C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python311\python.exe"
    set PYTHON_FOUND=1
)

if exist "C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python310\python.exe" (
    set PYTHON_PATH="C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python310\python.exe"
    set PYTHON_FOUND=1
)

if exist "C:\Python311\python.exe" (
    set PYTHON_PATH="C:\Python311\python.exe"
    set PYTHON_FOUND=1
)

if %PYTHON_FOUND%==1 (
    echo Python found at %PYTHON_PATH%
    %PYTHON_PATH% setup_pc_revenue_db.py
) else (
    echo Python not found in common locations.
    echo.
    echo Please download Python from: https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    echo.
    echo Alternatively, I'll create a simple database file for you...
    
    :: Create an empty SQLite database file
    echo. > "C:\Users\%USERNAME%\UnitedBunniesBot\revenue_data.db"
    echo Empty database file created at C:\Users\%USERNAME%\UnitedBunniesBot\revenue_data.db
)

echo.
echo === NEXT STEPS ===
echo 1. Your database location: C:\Users\%USERNAME%\UnitedBunniesBot\revenue_data.db
echo 2. Choose connection method:
echo    - Option A: Use ngrok (connect bot to your PC)
echo    - Option B: Use Supabase (remote database - easier)
echo.
echo Press any key to continue...
pause >nul