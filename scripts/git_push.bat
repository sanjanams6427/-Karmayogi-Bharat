@echo off
cd /d "e:\Manick_AI_ML\project"

echo [1/6] Configuring git...
git config user.email "sanjanams6427@github.com"
git config user.name "sanjanams6427"
git config core.autocrlf true

echo [2/6] Adding remote...
git remote remove origin 2>nul
git remote add origin https://github.com/sanjanams6427/kb-translation-22langs.git

echo [3/6] Staging files...
git add .

echo [4/6] Checking what will be committed...
git status --short

echo [5/6] Committing...
git commit -m "Initial commit: KB Translation System - 22 Indian Languages

Pipeline: ASR (faster-whisper) + IndicTrans2 (fine-tuned) + Parler-TTS/MMS
- All 22 scheduled Indian languages supported
- Fine-tuned IndicTrans2 checkpoint auto-loaded
- Fixed: S2ST lang routing, MMS adapter loading, audio assembly
- Fixed: TTS robotic voice (length_scale, slow descriptions)
- Fixed: Output always saved to output/ folder (not Gradio temp)
- Fixed: force=True deletes stale outputs before re-run
- UI: Gradio web interface with live logs"

echo [6/6] Pushing to GitHub...
git branch -M main
git push -u origin main

echo.
echo Done. Check https://github.com/sanjanams6427/kb-translation-22langs
pause
