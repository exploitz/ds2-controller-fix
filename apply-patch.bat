@echo off
rem Double-click to patch Dark Souls II: SotFS (finds the game through Steam).
rem If it can't find the game, drag the game's "Game" folder onto this file.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0ds2_xinput_patch.ps1" apply %*
pause
