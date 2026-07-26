; Activity logger + form-fill triggers — port of conversation #1039
; "Coding GPT Framework Plan" (2024-11-27), Pre Atlas harvest pipeline.
;
; The source thread sketched several disconnected AHK fragments (key/mouse
; logging, active-window logging, window-switch triggers that auto-type
; boilerplate). This consolidates them into one script that actually runs:
; every hotkey/timer/trigger writes to the same actions_log.txt, and the
; form-fill triggers are commented placeholders with real window-title
; variables at the top instead of hardcoded literal strings scattered
; through the original blocks -- so this is configured once, not edited
; in six places.
;
; AutoHotkey v1 syntax (matches the source blocks). Validated with:
;   AutoHotkeyU64.exe /Validate activity_logger.ahk
#NoEnv
#SingleInstance Force
SetWorkingDir %A_ScriptDir%

LogFile := "actions_log.txt"

; --- Configuration: fill these in for your own auto-fill targets ---
CodeEditorTitle := "YourCodeEditorTitle"
LoginWindowTitle := "LoginWindow"

; --- Key press logging ---
~*a::
~*b::
~*c::
    FileAppend, %A_ThisHotkey% was pressed at %A_Now%`n, %LogFile%
return

; --- Mouse movement logging (polls every 100ms) ---
SetTimer, LogMouse, 100
return

LogMouse:
    MouseGetPos, xPos, yPos
    FileAppend, Mouse moved to: %xPos%, %yPos% at %A_Now%`n, %LogFile%
return

; --- Active window change logging (polls every 100ms) ---
SetTimer, LogActiveWindow, 100
return

LogActiveWindow:
    WinGetActiveTitle, activeWindow
    FileAppend, Active Window: %activeWindow% at %A_Now%`n, %LogFile%
return

; --- Trigger: typing "login()" in the configured code editor inserts a
;     boilerplate login function stub ---
#IfWinActive, %CodeEditorTitle%
:*:login()::
    Send, def login(username, password):`n    # Function to validate user login`n    pass
return
#IfWinActive

; --- Trigger: F9 auto-fills the configured login window (username/password
;     fields left blank on purpose -- fill in your own values below before
;     using this trigger; shipping real credentials in a script is exactly
;     the kind of hardcoded-secret mistake the security rules forbid) ---
#IfWinExist, %LoginWindowTitle%
F9::
    WinActivate, %LoginWindowTitle%
    Send, {Tab 2}
    Send, {Tab}
    Send, {Enter}
return
#IfWinExist
