; ============================================================================
; Instalador NSIS: "Instalador oficina virtual"
; Compilar con:  _herramientas\nsis-3.11\Bin\makensis.exe instalador.nsi
; Genera: instalador\Instalador oficina virtual.exe
; ============================================================================
; Instalación por usuario (sin permisos de administrador). Deja accesos directos
; "Iniciar Sesión Oficina Virtual" en el escritorio y el menú Inicio. No pisa
; .env / tarjeta_dgii.json si ya existen, y al desinstalar los conserva.
;
; NOTA: la carpeta del programa se lee desde una ruta corta (C:\Temp\LGDGII_stage)
; porque las rutas internas de Chromium superan los 260 caracteres de Windows
; al compilar desde la carpeta del proyecto.
; Este archivo debe guardarse como UTF-8 CON BOM (por las tildes).

Unicode true

!define APPNAME "Oficina Virtual DGII"
!define LNKNAME "Iniciar Sesión Oficina Virtual"
!define VERSION "1.1.0"
!define COMPANY "Sanchez Matos & Asociados"
!define STAGE "C:\Temp\LGDGII_stage"
!define UNINSTKEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}"

Name "Instalador oficina virtual"
Caption "Instalador oficina virtual"
BrandingText "${COMPANY}"
OutFile "instalador\Instalador oficina virtual.exe"
Icon "recursos\instalador.ico"
UninstallIcon "recursos\app.ico"
InstallDir "$LOCALAPPDATA\Programs\${APPNAME}"
RequestExecutionLevel user
SetCompressor zlib

!include "MUI2.nsh"

; === Firma de código (descomentar cuando se tenga el certificado) =============
; Requiere signtool.exe (Windows SDK), el token/certificado conectado y su PIN.
; Estas líneas firman el instalador y el desinstalador automáticamente al compilar.
; !finalize 'signtool sign /fd SHA256 /td SHA256 /tr http://timestamp.digicert.com /a "${__FILEOUT__}"'
; !uninstfinalize 'signtool sign /fd SHA256 /td SHA256 /tr http://timestamp.digicert.com /a "${__FILEOUT__}"'


!define MUI_ICON "recursos\instalador.ico"
!define MUI_UNICON "recursos\app.ico"
!define MUI_WELCOMEFINISHPAGE_BITMAP "recursos\bienvenida.bmp"
!define MUI_UNWELCOMEFINISHPAGE_BITMAP "recursos\bienvenida.bmp"
!define MUI_ABORTWARNING
!define MUI_WELCOMEPAGE_TITLE "Instalador oficina virtual"
!define MUI_WELCOMEPAGE_TEXT "Este asistente instalará el acceso automático a la Oficina Virtual de la DGII.$\r$\n$\r$\nAl terminar encontrará en el escritorio el icono «${LNKNAME}»."
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN "$INSTDIR\LoginDGII.exe"
!define MUI_FINISHPAGE_RUN_TEXT "Abrir «${LNKNAME}» ahora"
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "Spanish"

Section "Instalar"
  SetOutPath "$INSTDIR"
  File /r "${STAGE}\LoginDGII\*.*"
  File "LEEME.txt"

  ; Credenciales: solo si no existen (no pisar una configuración previa)
  IfFileExists "$INSTDIR\.env" env_ya_esta
    File ".env"
  env_ya_esta:
  IfFileExists "$INSTDIR\tarjeta_dgii.json" tarjeta_ya_esta
    File "tarjeta_dgii.json"
  tarjeta_ya_esta:

  ; Accesos directos con el icono de la aplicación
  CreateDirectory "$SMPROGRAMS\${APPNAME}"
  CreateShortcut "$SMPROGRAMS\${APPNAME}\${LNKNAME}.lnk" "$INSTDIR\LoginDGII.exe" "" "$INSTDIR\LoginDGII.exe" 0
  CreateShortcut "$SMPROGRAMS\${APPNAME}\Desinstalar.lnk" "$INSTDIR\Desinstalar.exe"
  CreateShortcut "$DESKTOP\${LNKNAME}.lnk" "$INSTDIR\LoginDGII.exe" "" "$INSTDIR\LoginDGII.exe" 0

  WriteUninstaller "$INSTDIR\Desinstalar.exe"

  WriteRegStr HKCU "${UNINSTKEY}" "DisplayName" "${APPNAME}"
  WriteRegStr HKCU "${UNINSTKEY}" "UninstallString" '"$INSTDIR\Desinstalar.exe"'
  WriteRegStr HKCU "${UNINSTKEY}" "DisplayIcon" "$INSTDIR\LoginDGII.exe"
  WriteRegStr HKCU "${UNINSTKEY}" "DisplayVersion" "${VERSION}"
  WriteRegStr HKCU "${UNINSTKEY}" "Publisher" "${COMPANY}"
  WriteRegDWORD HKCU "${UNINSTKEY}" "NoModify" 1
  WriteRegDWORD HKCU "${UNINSTKEY}" "NoRepair" 1
SectionEnd

Section "Uninstall"
  Delete "$INSTDIR\LoginDGII.exe"
  Delete "$INSTDIR\LEEME.txt"
  Delete "$INSTDIR\Desinstalar.exe"
  RMDir /r "$INSTDIR\_internal"
  Delete "$SMPROGRAMS\${APPNAME}\${LNKNAME}.lnk"
  Delete "$SMPROGRAMS\${APPNAME}\Desinstalar.lnk"
  RMDir "$SMPROGRAMS\${APPNAME}"
  Delete "$DESKTOP\${LNKNAME}.lnk"
  DeleteRegKey HKCU "${UNINSTKEY}"
  ; NO se borran .env ni tarjeta_dgii.json (credenciales del usuario)
SectionEnd
