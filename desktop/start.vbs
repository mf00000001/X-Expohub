' ===========================================================================
'  ExpoHub silent launcher
'  ASCII ONLY -- wscript.exe reads .vbs as ANSI; non-ASCII here would garble.
'  Job: run start.ps1 with no console window flash, then exit immediately.
'       The services it spawns are detached, so they outlive this script.
' ===========================================================================
Option Explicit

Dim fso, shell, here, ps1, cmd
Set fso   = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

here = fso.GetParentFolderName(WScript.ScriptFullName)
ps1  = here & "\start.ps1"

If Not fso.FileExists(ps1) Then
    MsgBox "start.ps1 not found:" & vbCrLf & ps1, 16, "ExpoHub"
    WScript.Quit 1
End If

cmd = "powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File """ & ps1 & """"

' 0 = hidden console window, False = do not wait for it to finish
shell.Run cmd, 0, False
WScript.Quit 0
