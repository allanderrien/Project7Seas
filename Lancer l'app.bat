@echo off
echo Arret de l'ancienne session si active...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8501 ^| findstr LISTENING') do (
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 2 /nobreak >nul

echo Nettoyage du cache Python...
for /r "D:\Projects\sandbox\Project7seas\03. Strategy" %%f in (*.pyc) do del "%%f" >nul 2>&1
for /d /r "D:\Projects\sandbox\Project7seas\03. Strategy" %%d in (__pycache__) do (
    rd /s /q "%%d" >nul 2>&1
)

cd /d "D:\Projects\sandbox\Project7seas\03. Strategy"
echo Lancement de Project 7 Seas...
start "" http://localhost:8501
start /B streamlit run ui/app.py --server.headless true --server.port 8501
echo App lancee sur http://localhost:8501
echo Fermez cette fenetre pour arreter le serveur.
pause
