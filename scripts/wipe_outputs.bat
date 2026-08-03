@echo off
set BASE=e:\Manick_AI_ML\project\output\PNB-Pradhan Mantri Mudra Yojana
set CKPT=e:\Manick_AI_ML\project\checkpoints\jobs

echo Wiping job checkpoints...
del /f /q "%CKPT%\*.json" 2>nul

echo Wiping dubbed outputs...
for %%L in (asm ben guj hin kan mal mar mni mai nep ory pan san sat snd tam tel urd bod doi kas kok) do (
    del /f /q "%BASE%\%%L\*_%%L.mp4"  2>nul
    del /f /q "%BASE%\%%L\*_%%L.mp3"  2>nul
    del /f /q "%BASE%\%%L\*_%%L.srt"  2>nul
    del /f /q "%BASE%\%%L\*_%%L.vtt"  2>nul
    del /f /q "%BASE%\%%L\*_metadata.json" 2>nul
)

echo Wiping flat root outputs...
del /f /q "e:\Manick_AI_ML\project\output\PNB-Pradhan Mantri Mudra Yojana_*.mp4" 2>nul
del /f /q "e:\Manick_AI_ML\project\output\PNB-Pradhan Mantri Mudra Yojana_*.srt" 2>nul
del /f /q "e:\Manick_AI_ML\project\output\PNB-Pradhan Mantri Mudra Yojana_*.vtt" 2>nul

echo Done. All old outputs and checkpoints cleared.
