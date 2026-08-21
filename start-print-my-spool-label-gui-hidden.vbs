Option Explicit

Dim shell, fileSystem, folder, command
Set shell = CreateObject("WScript.Shell")
Set fileSystem = CreateObject("Scripting.FileSystemObject")
folder = fileSystem.GetParentFolderName(WScript.ScriptFullName)
command = """" & folder & "\start-print-my-spool-label-gui.bat"""
shell.Run command, 0, False
