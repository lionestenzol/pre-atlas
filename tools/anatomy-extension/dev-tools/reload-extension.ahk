; Anatomy extension reloader (AutoHotkey v2)
;
; Opens chrome://extensions in Bruke's existing Chrome window and presses
; the developer-mode "Update" button (Tab key navigation), which reloads
; every unpacked extension — including Anatomy — without him touching a
; mouse. The new background.js then takes over via /dev/version polling.
;
; Run via: & "C:\Program Files\AutoHotkey\v2\AutoHotkey.exe" "<path to this>"
;
; Notes:
; - Assumes Chrome is already running and developer mode is already on
;   (it is — that's how unpacked extensions get loaded in the first place).
; - The Tab count below targets Chrome's current chrome://extensions
;   layout: 4 tabs from default focus reaches the "Update" button.
;   Brittle if Chrome changes the page; if so, fall back to one manual click.

#Requires AutoHotkey v2.0
#SingleInstance Force

; 1. Bring Chrome to the foreground.
if !WinExist("ahk_exe chrome.exe") {
    MsgBox "Chrome isn't running — open it first."
    ExitApp 1
}
WinActivate "ahk_exe chrome.exe"
if !WinWaitActive("ahk_exe chrome.exe", , 3) {
    MsgBox "Couldn't focus Chrome."
    ExitApp 2
}

; 2. Open a new tab targeting chrome://extensions.
Send "^t"
Sleep 350
Send "chrome://extensions{Enter}"
Sleep 1500   ; let the page render its toolbar buttons before navigating

; 3. Tab into the "Update" button. Default focus on chrome://extensions
;    is the Search field, then in order: dev mode toggle, Load unpacked,
;    Pack extension, Update. Four tabs lands on Update.
Loop 4 {
    Send "{Tab}"
    Sleep 80
}
Send "{Enter}"
Sleep 800

; 4. Done — new background.js is now running and polling /dev/version.
;    Don't auto-close the tab; leave it visible so Bruke can see the
;    "Updated" toast and confirm the reload happened.
ExitApp 0
