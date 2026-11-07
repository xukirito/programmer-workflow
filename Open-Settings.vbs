Option Explicit

Dim shell, fso, root, companion, quickUrl, http, command
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
root = fso.GetParentFolderName(WScript.ScriptFullName)
quickUrl = "http://127.0.0.1:8765/quick?host=kimi"

On Error Resume Next
Set http = CreateObject("MSXML2.XMLHTTP")
http.Open "GET", quickUrl, False
http.Send
If Err.Number = 0 And http.Status = 200 Then
  shell.Run quickUrl
  WScript.Quit
End If
Err.Clear

companion = root & "\skills\programmer-workflow\scripts\companion.py"
If Not fso.FileExists(companion) Then
  MsgBox "companion.py was not next to this launcher. Reinstall the complete plugin package.", 16, "Programmer Workflow"
  WScript.Quit 1
End If

command = "python """ & companion & """ settings --host kimi --workspace """ & root & """ --open"
shell.Run command, 0, False
If Err.Number <> 0 Then
  MsgBox "Python was not found on PATH. Install Python 3.8+ and try again.", 16, "Programmer Workflow"
  WScript.Quit 1
End If
