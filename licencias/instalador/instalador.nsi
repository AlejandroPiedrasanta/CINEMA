; =====================================================================
;  Instalador del Administrador de Licencias (NSIS 3 · Modern UI 2)
;  Crea:  "Instalar Administrador de Licencias 4.0.0.exe"
;  - Páginas con banner: bienvenida, carpeta, componentes, progreso y final
;  - Accesos directos en el menú Inicio y (opcional) en el escritorio
;  - Desinstalador registrado en "Agregar o quitar programas"
;  Compilar:  makensis instalador.nsi   (o doble clic en CONSTRUIR_INSTALADOR.bat)
; =====================================================================
Target amd64-unicode      ; instalador de 64 bits, igual que el programa
SetCompressor /SOLID lzma
SetCompressorDictSize 64
ManifestDPIAware true

!define APP "Administrador de Licencias"
!define APP_EXE "Administrador de Licencias.exe"
!ifndef VERSION
  !define VERSION "4.0.0"
!endif
!define EMPRESA "Resolve Creator Subtitles"
!define CLAVE_DESINSTALAR "Software\Microsoft\Windows\CurrentVersion\Uninstall\AdministradorDeLicencias"
!ifndef DIST
  !define DIST "..\administrador\dist\Administrador de Licencias"
!endif

Name "${APP}"
OutFile "Instalar Administrador de Licencias ${VERSION}.exe"
InstallDir "$PROGRAMFILES64\${APP}"
InstallDirRegKey HKLM "${CLAVE_DESINSTALAR}" "InstallLocation"
RequestExecutionLevel admin
BrandingText "${EMPRESA}  ·  v${VERSION}"
ShowInstDetails show
ShowUninstDetails show

!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "WinVer.nsh"
!include "x64.nsh"
!include "FileFunc.nsh"

; ---------- apariencia (banners e icono) ----------
!define MUI_ICON "imagenes\icono.ico"
!define MUI_UNICON "imagenes\icono.ico"
!define MUI_WELCOMEFINISHPAGE_BITMAP "imagenes\bienvenida.bmp"
!define MUI_UNWELCOMEFINISHPAGE_BITMAP "imagenes\bienvenida.bmp"
!define MUI_HEADERIMAGE
!define MUI_HEADERIMAGE_RIGHT
!define MUI_HEADERIMAGE_BITMAP "imagenes\cabecera.bmp"
!define MUI_HEADERIMAGE_UNBITMAP "imagenes\cabecera.bmp"
!define MUI_ABORTWARNING
!define MUI_UNABORTWARNING
!define MUI_COMPONENTSPAGE_SMALLDESC

; ---------- textos ----------
!define MUI_WELCOMEPAGE_TITLE "Bienvenido al ${APP}"
!define MUI_WELCOMEPAGE_TEXT "Este asistente instalará el ${APP} ${VERSION} en tu computadora.$\r$\n$\r$\nDesde el panel controlas las licencias, equipos, ventas y compradores de tu programa en Lemon Squeezy, Hotmart y Gumroad.$\r$\n$\r$\nPulsa Siguiente para continuar."
!define MUI_DIRECTORYPAGE_TEXT_TOP "El programa se instalará en esta carpeta. Para usar otra, pulsa Examinar."
!define MUI_FINISHPAGE_TITLE "¡Listo! Ya quedó instalado"
!define MUI_FINISHPAGE_TEXT "El ${APP} está instalado. Lo encontrarás en el menú Inicio y, si lo elegiste, en el escritorio.$\r$\n$\r$\nTus credenciales se guardan solo en esta computadora."
!define MUI_FINISHPAGE_RUN "$INSTDIR\${APP_EXE}"
!define MUI_FINISHPAGE_RUN_TEXT "Abrir el ${APP} ahora"
!define MUI_UNCONFIRMPAGE_TEXT_TOP "Se quitará el ${APP} de esta computadora."
!define MUI_UNFINISHPAGE_NOAUTOCLOSE

; ---------- páginas ----------
!insertmacro MUI_PAGE_WELCOME
!define MUI_PAGE_HEADER_TEXT "Elige dónde instalarlo"
!define MUI_PAGE_HEADER_SUBTEXT "Carpeta donde se instalará el ${APP}."
!insertmacro MUI_PAGE_DIRECTORY
!define MUI_PAGE_HEADER_TEXT "Elige qué instalar"
!define MUI_PAGE_HEADER_SUBTEXT "Marca lo que quieres y pulsa Instalar."
!define MUI_COMPONENTSPAGE_TEXT_TOP "Marca lo que quieres instalar y pulsa Instalar para empezar."
!insertmacro MUI_PAGE_COMPONENTS
!define MUI_PAGE_HEADER_TEXT "Instalando…"
!define MUI_PAGE_HEADER_SUBTEXT "Espera un momento mientras se copian los archivos."
!define MUI_INSTFILESPAGE_FINISHHEADER_TEXT "Instalación completa"
!define MUI_INSTFILESPAGE_FINISHHEADER_SUBTEXT "El ${APP} se instaló correctamente."
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_COMPONENTS
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

!insertmacro MUI_LANGUAGE "Spanish"

; ---------- datos del archivo del instalador ----------
VIProductVersion "${VERSION}.0"
VIAddVersionKey /LANG=${LANG_SPANISH} "ProductName" "${APP}"
VIAddVersionKey /LANG=${LANG_SPANISH} "CompanyName" "${EMPRESA}"
VIAddVersionKey /LANG=${LANG_SPANISH} "FileDescription" "Instalador del ${APP}"
VIAddVersionKey /LANG=${LANG_SPANISH} "FileVersion" "${VERSION}"
VIAddVersionKey /LANG=${LANG_SPANISH} "ProductVersion" "${VERSION}"
VIAddVersionKey /LANG=${LANG_SPANISH} "LegalCopyright" "© ${EMPRESA}"

; ---------- comprobaciones al empezar ----------
Function .onInit
  ${IfNot} ${RunningX64}
    MessageBox MB_ICONSTOP "El ${APP} necesita Windows de 64 bits."
    Abort
  ${EndIf}
  ${IfNot} ${AtLeastWin10}
  ${OrIfNot} ${AtLeastBuild} 18362
    MessageBox MB_ICONSTOP "El ${APP} necesita Windows 10 (versión 1903 o más nueva) o Windows 11."
    Abort
  ${EndIf}
  SetRegView 64
FunctionEnd

Function un.onInit
  SetRegView 64
FunctionEnd

; ---------- instalación ----------
Section "${APP} (obligatorio)" SecPrograma
  SectionIn RO
  SetShellVarContext all
  SetOutPath "$INSTDIR"
  ; si había una versión anterior, se reemplaza limpia
  RMDir /r "$INSTDIR\_internal"
  File /r "${DIST}\*"
  WriteUninstaller "$INSTDIR\Desinstalar.exe"

  CreateDirectory "$SMPROGRAMS\${APP}"
  CreateShortcut "$SMPROGRAMS\${APP}\${APP}.lnk" "$INSTDIR\${APP_EXE}" "" "$INSTDIR\${APP_EXE}" 0
  CreateShortcut "$SMPROGRAMS\${APP}\Desinstalar ${APP}.lnk" "$INSTDIR\Desinstalar.exe"

  ; registro para "Agregar o quitar programas"
  WriteRegStr HKLM "${CLAVE_DESINSTALAR}" "DisplayName" "${APP}"
  WriteRegStr HKLM "${CLAVE_DESINSTALAR}" "DisplayVersion" "${VERSION}"
  WriteRegStr HKLM "${CLAVE_DESINSTALAR}" "Publisher" "${EMPRESA}"
  WriteRegStr HKLM "${CLAVE_DESINSTALAR}" "DisplayIcon" "$INSTDIR\${APP_EXE},0"
  WriteRegStr HKLM "${CLAVE_DESINSTALAR}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKLM "${CLAVE_DESINSTALAR}" "UninstallString" '"$INSTDIR\Desinstalar.exe"'
  WriteRegStr HKLM "${CLAVE_DESINSTALAR}" "QuietUninstallString" '"$INSTDIR\Desinstalar.exe" /S'
  WriteRegDWORD HKLM "${CLAVE_DESINSTALAR}" "NoModify" 1
  WriteRegDWORD HKLM "${CLAVE_DESINSTALAR}" "NoRepair" 1
  ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
  WriteRegDWORD HKLM "${CLAVE_DESINSTALAR}" "EstimatedSize" $0
SectionEnd

Section "Acceso directo en el escritorio" SecEscritorio
  SetShellVarContext all
  CreateShortcut "$DESKTOP\${APP}.lnk" "$INSTDIR\${APP_EXE}" "" "$INSTDIR\${APP_EXE}" 0
SectionEnd

!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
  !insertmacro MUI_DESCRIPTION_TEXT ${SecPrograma} "El panel para controlar las licencias y ventas de tu programa."
  !insertmacro MUI_DESCRIPTION_TEXT ${SecEscritorio} "Pone un acceso directo en el escritorio."
!insertmacro MUI_FUNCTION_DESCRIPTION_END

; ---------- desinstalación ----------
Section "un.${APP}" SecQuitarPrograma
  SectionIn RO
  SetShellVarContext all
  Delete "$DESKTOP\${APP}.lnk"
  RMDir /r "$SMPROGRAMS\${APP}"
  RMDir /r "$INSTDIR\_internal"
  Delete "$INSTDIR\${APP_EXE}"
  Delete "$INSTDIR\Desinstalar.exe"
  RMDir "$INSTDIR"
  DeleteRegKey HKLM "${CLAVE_DESINSTALAR}"
SectionEnd

Section /o "un.Borrar también mis credenciales y ajustes" SecQuitarDatos
  SetShellVarContext current
  RMDir /r "$APPDATA\RCS-Administrador"
SectionEnd

!insertmacro MUI_UNFUNCTION_DESCRIPTION_BEGIN
  !insertmacro MUI_DESCRIPTION_TEXT ${SecQuitarPrograma} "Quita el programa, sus accesos directos y su registro."
  !insertmacro MUI_DESCRIPTION_TEXT ${SecQuitarDatos} "Borra tus API keys, tokens y ajustes guardados en esta computadora."
!insertmacro MUI_UNFUNCTION_DESCRIPTION_END
