' ===========================================================================
'  ExpoHub console launcher
'  ASCII ONLY -- wscript.exe reads .vbs as ANSI; non-ASCII here would garble.
'  Job: run console.ps1 with the console window hidden. The WinForms window
'       it creates is its own top-level window, so it still shows normally.
' ===========================================================================
Option Explicit

Dim fso, shell, here, ps1, cmd
Set fso   = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

here = fso.GetParentFolderName(WScript.ScriptFullName)
ps1  = here & "\console.ps1"

If Not fso.FileExists(ps1) Then
    MsgBox "console.ps1 not found:" & vbCrLf & ps1, 16, "ExpoHub"
    WScript.Quit 1
End If

cmd = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File """ & ps1 & """"

shell.Run cmd, 0, False
WScript.Quit 0
