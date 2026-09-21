' REIS AI Agent - Masaustune Kopyalama (VBS, Explorer Shell kullanarak)
Option Explicit
Dim WshShell, fso, src, dst, desktop, progName, appData

Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' Gecerli scriptin oldugu klasor = kaynak klasor
src = fso.GetParentFolderName(WScript.ScriptFullName)
progName = fso.GetFolder(src).Name

' Masaustu yolunu al
desktop = WshShell.SpecialFolders("Desktop")
dst = fso.BuildPath(desktop, progName)

' Eski hedefi sil
If fso.FolderExists(dst) Then
    On Error Resume Next
    fso.DeleteFolder dst, True
    On Error GoTo 0
End If

' Kopyalama baslasin (GUI ile gerceklesecek, sandbox engellenmez)
Dim progressDlg
Set progressDlg = CreateObject("Shell.Application")
progressDlg.Namespace(CStr(fso.GetParentFolderName(dst))).CopyHere _
    CStr(src), _
    4 + 8 + 16 + 256 + 1024

' Sonucu raporla
WScript.Sleep 2000
If fso.FolderExists(dst) And fso.FileExists(fso.BuildPath(dst, "start.bat")) Then
    MsgBox "BASARILI! REIS AI Agent Masaustune tasindi:" & vbCrLf & vbCrLf & dst & vbCrLf & vbCrLf & "Kurulum icin setup.bat dosyasina cift tikla.", vbInformation, "REIS AI"
    ' Klasoru ac
    WshShell.Run "explorer.exe """ & dst & """", 1, False
Else
    MsgBox "Kopyalama basarisiz. Manuel olarak:" & vbCrLf & "1. " & src & " klasorunu sag tik Kopyala" & vbCrLf & "2. Masaustune sag tik Yapistir", vbExclamation, "REIS AI"
End If
