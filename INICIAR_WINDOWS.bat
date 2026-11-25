@echo off
cd /d "%~dp0"
echo ============================================
echo AHP Feedstock | Interface de Pesquisa Local
echo ============================================
where py >nul 2>&1
if %errorlevel%==0 (set "PY=py -3") else (set "PY=python")
if not exist .venv ( %PY% -m venv .venv || goto failed )
call .venv\Scripts\activate.bat
python -m pip install -r requirements.txt || goto failed
set "AHP_ENABLE_DRAFT=1"
echo A ferramenta abrira uma nova instancia local no navegador.
python iniciar.py
goto end
:failed
echo ERRO: verifique Python 3.10+ e conexao para instalacao inicial.
pause
:end
