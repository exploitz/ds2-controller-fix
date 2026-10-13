@echo off
rem Double-click to undo the patch and put the original DarkSoulsII.exe back.
rem If it can't find the game, drag the game's "Game" folder onto this file.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0ds2_xinput_patch.ps1" restore %*
pause
