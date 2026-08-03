@echo off
:: ============================================================
:: run_finetune.bat  —  4x RTX A6000  |  All 5 training steps
::
:: Usage:
::   run_finetune.bat          -> run all 5 steps in order
::   run_finetune.bat 1        -> en_indic only
::   run_finetune.bat 2        -> indic_en only
::   run_finetune.bat 3        -> indic_indic only
::   run_finetune.bat 4        -> seamless ASR only
::   run_finetune.bat 5        -> seamless T2T only
:: ============================================================

call activate_env.bat

set "PY=C:\Users\M1021\AppData\Local\Programs\Python\Python312\python.exe"
set "ACC=C:\Users\M1021\AppData\Local\Programs\Python\Python312\Scripts\accelerate.exe"
set "NGPU=4"
set "STEP=%1"
set "PYTHONPATH=E:\Manick_AI_ML\project"
set "PL_TORCH_DISTRIBUTED_BACKEND=gloo"
set "MASTER_ADDR=127.0.0.1"
set "MASTER_PORT=29500"
set "GLOO_SOCKET_IFNAME=Ethernet"
set "USE_LIBUV=0"
set "LAUNCH=%ACC% launch --num_processes=%NGPU% --mixed_precision=bf16 --multi_gpu"

echo.
echo ============================================================
echo  KB Translation Fine-Tuning  ^|  4x RTX A6000  ^|  192GB VRAM
echo ============================================================
echo.

:: ── Step 1: IndicTrans2 en_indic ──────────────────────────────
if "%STEP%"=="2" goto step2
if "%STEP%"=="3" goto step3
if "%STEP%"=="4" goto step4
if "%STEP%"=="5" goto step5

:step1
echo [Step 1/5] IndicTrans2 English to Indic ...
%LAUNCH% finetune\finetune_indictrans.py --direction en_indic
if errorlevel 1 ( echo [FAIL] en_indic failed & goto end )
echo [OK] en_indic done. Checkpoint: checkpoints\indictrans\en_indic\best
if "%STEP%"=="1" goto end

:: ── Step 2: IndicTrans2 indic_en ──────────────────────────────
:step2
echo.
echo [Step 2/5] IndicTrans2 Indic to English ...
%LAUNCH% finetune\finetune_indictrans.py --direction indic_en
if errorlevel 1 ( echo [FAIL] indic_en failed & goto end )
echo [OK] indic_en done. Checkpoint: checkpoints\indictrans\indic_en\best
if "%STEP%"=="2" goto end

:: ── Step 3: IndicTrans2 indic_indic ───────────────────────────
:step3
echo.
echo [Step 3/5] IndicTrans2 Indic to Indic ...
%LAUNCH% finetune\finetune_indictrans.py --direction indic_indic
if errorlevel 1 ( echo [FAIL] indic_indic failed & goto end )
echo [OK] indic_indic done. Checkpoint: checkpoints\indictrans\indic_indic\best
if "%STEP%"=="3" goto end

:: ── Step 4: SeamlessM4T ASR ───────────────────────────────────
:step4
echo.
echo [Step 4/5] SeamlessM4T ASR fine-tune ...
%LAUNCH% finetune\finetune_seamless.py --task asr
if errorlevel 1 ( echo [FAIL] Seamless ASR failed & goto end )
echo [OK] Seamless ASR done. Checkpoint: checkpoints\seamless\asr\best
if "%STEP%"=="4" goto end

:: ── Step 5: SeamlessM4T T2T ───────────────────────────────────
:step5
echo.
echo [Step 5/5] SeamlessM4T T2T fine-tune ...
%LAUNCH% finetune\finetune_seamless.py --task t2t
if errorlevel 1 ( echo [WARN] Seamless T2T had errors )
echo [OK] Seamless T2T done. Checkpoint: checkpoints\seamless\t2t\best

:end
echo.
echo ============================================================
echo  Fine-tuning complete.
echo  Checkpoints: checkpoints\indictrans\  +  checkpoints\seamless\
echo ============================================================
