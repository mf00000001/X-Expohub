' ===========================================================================
'  ExpoHub stop launcher
'  ASCII ONLY -- wscript.exe reads .vbs as ANSI; non-ASCII here would garble.
'  Job: run stop.ps1 hidden; stop.ps1 itself shows the result dialog.
' ===========================================================================
Option Explicit

Dim fso, shell, here, ps1, cmd
Set fso   = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

here = fso.GetParentFolderName(WScript.ScriptFullName)
ps1  = here & "\stop.ps1"

If Not fso.FileExists(ps1) Then
    MsgBox "stop.ps1 not found:" & vbCrLf & ps1, 16, "ExpoHub"
    WScript.Quit 1
End If

cmd = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File """ & ps1 & """"

shell.Run cmd, 0, False
WScript.Quit 0
