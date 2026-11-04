; Tauri 2.12.4 template, modified for publisher-independent install paths.
; Upstream SHA256: d00089d3b1a2c4a30d7b6e098079100cb8f25e980f84d4515aca4597b95e967d
; License: LICENSE-MIT.txt
Unicode true
ManifestDPIAware true
; Add in `dpiAwareness` `PerMonitorV2` to manifest for Windows 10 1607+ (note this should not affect lower versions since they should be able to ignore this and pick up `dpiAware` `true` set by `ManifestDPIAware true`)
; Currently undocumented on NSIS's website but is in the Docs folder of source tree, see
; https://github.com/kichik/nsis/blob/5fc0b87b819a9eec006df4967d08e522ddd651c9/Docs/src/attributes.but#L286-L300
; https://github.com/tauri-apps/tauri/pull/10106
ManifestDPIAwareness PerMonitorV2

!if "{{compression}}" == "none"
  SetCompress off
!else
  ; Set the compression algorithm. We default to LZMA.
  SetCompressor /SOLID "{{compression}}"
!endif

; Keep above !include to stay ahead of any plugin command
; see https://github.com/tauri-apps/tauri/pull/15422#discussion_r3289239624
{{#if signed_plugins_path}}
!addplugindir "{{signed_plugins_path}}"
{{/if}}

!include MUI2.nsh
!include FileFunc.nsh
!include x64.nsh
!include WordFunc.nsh
!include "utils.nsh"
!include "FileAssociation.nsh"
!include "Win\COM.nsh"
!include "Win\Propkey.nsh"
!include "Win\RestartManager.nsh"
!include "StrFunc.nsh"
${StrCase}
${StrLoc}

{{#if installer_hooks}}
!include "{{installer_hooks}}"
{{/if}}

!define WEBVIEW2APPGUID "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"

!define MANUFACTURER "{{manufacturer}}"
!define PRODUCTNAME "Calix"
!define CALIXDISPLAYNAME "{{product_name}}"
!define VERSION "{{version}}"
!define VERSIONWITHBUILD "{{version_with_build}}"
!define HOMEPAGE "{{homepage}}"
!define INSTALLMODE "{{install_mode}}"
!define LICENSE "{{license}}"
!define INSTALLERICON "{{installer_icon}}"
!define SIDEBARIMAGE "{{sidebar_image}}"
!define HEADERIMAGE "{{header_image}}"
!define UNINSTALLERICON "{{uninstaller_icon}}"
!define UNINSTALLERHEADERIMAGE "{{uninstaller_header_image}}"
!define MAINBINARYNAME "{{main_binary_name}}"
!define MAINBINARYSRCPATH "{{main_binary_path}}"
!define BUNDLEID "{{bundle_id}}"
!define COPYRIGHT "{{copyright}}"
!define OUTFILE "{{out_file}}"
!define ARCH "{{arch}}"
!define ADDITIONALPLUGINSPATH "{{additional_plugins_path}}"
!define ALLOWDOWNGRADES "{{allow_downgrades}}"
!define DISPLAYLANGUAGESELECTOR "{{display_language_selector}}"
!define INSTALLWEBVIEW2MODE "{{install_webview2_mode}}"
!define WEBVIEW2INSTALLERARGS "{{webview2_installer_args}}"
!define WEBVIEW2BOOTSTRAPPERPATH "{{webview2_bootstrapper_path}}"
!define WEBVIEW2INSTALLERPATH "{{webview2_installer_path}}"
!define MINIMUMWEBVIEW2VERSION "{{minimum_webview2_version}}"
!define UNINSTKEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCTNAME}"
!define MANUKEY "Software\${MANUFACTURER}"
!define MANUPRODUCTKEY "${MANUKEY}\${PRODUCTNAME}"
!define UNINSTALLERSIGNCOMMAND "{{uninstaller_sign_cmd}}"
!define ESTIMATEDSIZE "{{estimated_size}}"
!define STARTMENUFOLDER "{{start_menu_folder}}"

Var PassiveMode
Var UpdateMode
Var NoShortcutMode
Var WixMode
Var OldMainBinaryName
Var CalixPreviousDisplayName

Name "${CALIXDISPLAYNAME}"
BrandingText "${COPYRIGHT}"
OutFile "${OUTFILE}"

; We don't actually use this value as default install path,
; it's just for nsis to append the product name folder in the directory selector
; https://nsis.sourceforge.io/Reference/InstallDir
!define PLACEHOLDER_INSTALL_DIR "placeholder\${PRODUCTNAME}"
InstallDir "${PLACEHOLDER_INSTALL_DIR}"

VIProductVersion "${VERSIONWITHBUILD}"
VIAddVersionKey "ProductName" "${PRODUCTNAME}"
VIAddVersionKey "FileDescription" "${PRODUCTNAME}"
VIAddVersionKey "LegalCopyright" "${COPYRIGHT}"
VIAddVersionKey "FileVersion" "${VERSION}"
VIAddVersionKey "ProductVersion" "${VERSION}"

# additional plugins
!addplugindir "${ADDITIONALPLUGINSPATH}"

; Uninstaller signing command
!if "${UNINSTALLERSIGNCOMMAND}" != ""
  !uninstfinalize '${UNINSTALLERSIGNCOMMAND}'
!endif

; Handle install mode, `perUser`, `perMachine` or `both`
!if "${INSTALLMODE}" == "perMachine"
  RequestExecutionLevel admin
!endif

!if "${INSTALLMODE}" == "currentUser"
  RequestExecutionLevel user
!endif

!if "${INSTALLMODE}" == "both"
  !define MULTIUSER_MUI
  !define MULTIUSER_INSTALLMODE_INSTDIR "${PRODUCTNAME}"
  !define MULTIUSER_INSTALLMODE_COMMANDLINE
  !if "${ARCH}" == "x64"
    !define MULTIUSER_USE_PROGRAMFILES64
  !else if "${ARCH}" == "arm64"
    !define MULTIUSER_USE_PROGRAMFILES64
  !endif
  !define MULTIUSER_INSTALLMODE_DEFAULT_REGISTRY_KEY "${UNINSTKEY}"
  !define MULTIUSER_INSTALLMODE_DEFAULT_REGISTRY_VALUENAME "CurrentUser"
  !define MULTIUSER_INSTALLMODEPAGE_SHOWUSERNAME
  !define MULTIUSER_INSTALLMODE_FUNCTION RestorePreviousInstallLocation
  !define MULTIUSER_EXECUTIONLEVEL Highest
  !include MultiUser.nsh
!endif

; Installer icon
!if "${INSTALLERICON}" != ""
  !define MUI_ICON "${INSTALLERICON}"
!endif

; Installer sidebar image
!if "${SIDEBARIMAGE}" != ""
  !define MUI_WELCOMEFINISHPAGE_BITMAP "${SIDEBARIMAGE}"
!endif

; Enable header images for installer and uninstaller pages when either image is configured.
!if "${HEADERIMAGE}" != ""
  !define MUI_HEADERIMAGE
!else if "${UNINSTALLERHEADERIMAGE}" != ""
  !define MUI_HEADERIMAGE
!endif

; Installer header image
!if "${HEADERIMAGE}" != ""
  !define MUI_HEADERIMAGE_BITMAP "${HEADERIMAGE}"
!endif

; Uninstaller header image
!if "${UNINSTALLERHEADERIMAGE}" != ""
  !define MUI_HEADERIMAGE_UNBITMAP "${UNINSTALLERHEADERIMAGE}"
!endif

; Uninstaller icon
!if "${UNINSTALLERICON}" != ""
  !define MUI_UNICON "${UNINSTALLERICON}"
!endif

; Define registry key to store installer language
!define MUI_LANGDLL_REGISTRY_ROOT "HKCU"
!define MUI_LANGDLL_REGISTRY_KEY "${MANUPRODUCTKEY}"
!define MUI_LANGDLL_REGISTRY_VALUENAME "Installer Language"

; Installer pages, must be ordered as they appear
; 1. Welcome Page
!define MUI_PAGE_CUSTOMFUNCTION_PRE SkipIfPassive
!insertmacro MUI_PAGE_WELCOME

; 2. License Page (if defined)
!if "${LICENSE}" != ""
  !define MUI_PAGE_CUSTOMFUNCTION_PRE SkipIfPassive
  !insertmacro MUI_PAGE_LICENSE "${LICENSE}"
!endif

; 3. Install mode (if it is set to `both`)
!if "${INSTALLMODE}" == "both"
  !define MUI_PAGE_CUSTOMFUNCTION_PRE SkipIfPassive
  !insertmacro MULTIUSER_PAGE_INSTALLMODE
!endif

; 4. Custom page to ask user if he wants to reinstall/uninstall
;    only if a previous installation was detected
Var ReinstallPageCheck
Var CalixPreviousLocation
Var CalixHasExistingData
Var CalixKeepOption
Var CalixResetOption
Var CalixPreserveOption
Var CalixResetRoaming
Var CalixResetLocal
Page custom PageReinstall PageLeaveReinstall

; Find a previous WiX installation and set $R6 to its uninstall registry key, or to "" if none.
;
; A WiX installer stores the installation info in registry
; using a UUID and so we have to loop through all keys under
; `HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall`
; and check if `DisplayName` and `Publisher` keys match ${PRODUCTNAME} and ${MANUFACTURER}
;
; This has a potential issue that there maybe another installation that matches
; our ${PRODUCTNAME} and ${MANUFACTURER} but wasn't installed by our WiX installer,
; however, this should be fine since the user will have to confirm the uninstallation
; and they can chose to abort it if doesn't make sense.
Function FindWixInstall
  StrCpy $R6 ""
  StrCpy $0 0
  wix_loop:
    EnumRegKey $1 HKLM "SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall" $0
    StrCmp $1 "" wix_loop_done ; Exit loop if there is no more keys to loop on
    IntOp $0 $0 + 1
    ReadRegStr $R0 HKLM "SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\$1" "DisplayName"
    ReadRegStr $R1 HKLM "SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\$1" "Publisher"
    StrCmp "$R0$R1" "${PRODUCTNAME}${MANUFACTURER}" 0 wix_loop
    ReadRegStr $R0 HKLM "SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\$1" "UninstallString"
    ${StrCase} $R1 $R0 "L"
    ${StrLoc} $R0 $R1 "msiexec" ">"
    StrCmp $R0 0 0 wix_loop_done
    StrCpy $R6 "SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\$1"
  wix_loop_done:
FunctionEnd

Function PageReinstall
  StrCpy $CalixPreviousLocation ""
  StrCpy $CalixHasExistingData 0
  Call FindWixInstall
  StrCpy $WixMode 0
  ${If} $R6 != ""
    StrCpy $WixMode 1
  ${Else}
    Call CalixResolveInstallLocation
    StrCpy $CalixPreviousLocation $4
  ${EndIf}
  ${If} ${FileExists} "$APPDATA\LutteLaurent\Calix"
  ${OrIf} ${FileExists} "$LOCALAPPDATA\${BUNDLEID}"
    StrCpy $CalixHasExistingData 1
  ${EndIf}
  ${If} $PassiveMode = 1
  ${OrIf} $UpdateMode = 1
    Abort
  ${EndIf}
  ${If} $CalixPreviousLocation == ""
  ${AndIf} $WixMode = 0
  ${AndIf} $CalixHasExistingData = 0
    Abort
  ${EndIf}

  !insertmacro MUI_HEADER_TEXT "Calix 설치" "이전 버전과 데이터 처리 방법을 선택하세요."
  nsDialogs::Create 1018
  Pop $R4
  ${If} $R4 == error
    Abort
  ${EndIf}
  ${NSD_CreateRadioButton} 0 12u 100% 14u "데이터 유지 · 이전 버전 삭제"
  Pop $CalixPreserveOption
  ${NSD_CreateRadioButton} 0 42u 100% 14u "데이터 초기화 · 새로 설치"
  Pop $CalixResetOption
  ${NSD_CreateRadioButton} 0 72u 100% 14u "이전 버전도 보관"
  Pop $CalixKeepOption
  ${NSD_CreateLabel} 12u 90u 95% 18u "새 버전은 별도 폴더에 설치되며 기존 데이터를 함께 사용합니다."
  Pop $R3
  ${If} $CalixPreviousLocation == ""
    EnableWindow $CalixKeepOption 0
    EnableWindow $R3 0
  ${EndIf}
  ${If} $CalixHasExistingData = 0
    EnableWindow $CalixResetOption 0
  ${EndIf}
  ${If} $ReinstallPageCheck = 2
    ${NSD_Check} $CalixResetOption
  ${ElseIf} $ReinstallPageCheck = 3
    ${NSD_Check} $CalixKeepOption
  ${Else}
    ${NSD_Check} $CalixPreserveOption
  ${EndIf}
  nsDialogs::Show
FunctionEnd

Function PageLeaveReinstall
  StrCpy $ReinstallPageCheck 1
  ${NSD_GetState} $CalixResetOption $0
  ${If} $0 = ${BST_CHECKED}
    MessageBox MB_ICONEXCLAMATION|MB_YESNO|MB_DEFBUTTON2 "일정, 설정, 일기와 로그인 정보가 삭제됩니다. 복구할 수 없습니다. 계속하시겠습니까?" IDYES calix_reset_confirmed
    Abort
    calix_reset_confirmed:
    StrCpy $ReinstallPageCheck 2
    Return
  ${EndIf}
  ${NSD_GetState} $CalixKeepOption $0
  ${If} $0 = ${BST_CHECKED}
    StrCpy $ReinstallPageCheck 3
  ${EndIf}
FunctionEnd

Function CalixRemovePreviousInstallation
    ClearErrors

    ${If} $WixMode = 1
      ReadRegStr $R1 HKLM "$R6" "UninstallString"
      ExecWait '$R1' $0
    ${Else}
      Call CalixResolveInstallLocation
      ${If} $4 == ""
        MessageBox MB_ICONEXCLAMATION "$(unableToUninstall)"
        SetErrorLevel 2
        Quit
      ${EndIf}
      ReadRegStr $R1 SHCTX "${UNINSTKEY}" "UninstallString"
      ; Removing old binaries during Setup must never offer to delete app data.
      StrCpy $R1 "$R1 /P /UPDATE _?=$4"
      ExecWait '$R1' $0
    ${EndIf}

    ${IfThen} ${Errors} ${|} StrCpy $0 2 ${|} ; ExecWait failed, set fake exit code

    ${If} $0 = 0
    ${AndIf} $WixMode = 0
    ${AndIf} ${FileExists} "$4\${MAINBINARYNAME}.exe"
      StrCpy $0 2
    ${EndIf}
    ${If} $0 <> 0
      ; User cancelled wix uninstaller? return to select un/reinstall page
      ${If} $WixMode = 1
      ${AndIf} $0 = 1602
        SetErrorLevel 2
        Quit
      ${EndIf}

      ; User cancelled NSIS uninstaller? return to select un/reinstall page
      ${If} $0 = 1
        SetErrorLevel 2
        Quit
      ${EndIf}

      ; Other errors? show generic error message and return to select un/reinstall page
      MessageBox MB_ICONEXCLAMATION "$(unableToUninstall)"
      SetErrorLevel 2
      Quit
    ${EndIf}

    ; The NSIS uninstaller was run in place (`_?=`), so it cannot delete itself
    ; and the install directory, clean them up here once the uninstall succeeded
    ; https://nsis.sourceforge.io/Docs/Chapter3.html#:~:text=path%20contains%20spaces.-,3.2.3%20Examples,-installer.exe%20/NCRC
    ${If} $WixMode = 0
    ${AndIf} $4 != ""
      ; Old uninstallers only remove the files listed in their bundle.
      ; _internal is the packaged engine runtime. Leave other files alone.
      Push "$4\_internal"
      Call CalixRemoveTree
      Delete "$4\uninstall.exe"
      ${If} ${FileExists} "$4\_internal"
      ${OrIf} ${FileExists} "$4\calix-engine.exe"
      ${OrIf} ${FileExists} "$4\uninstall.exe"
        MessageBox MB_ICONEXCLAMATION "$(unableToUninstall)"
        SetErrorLevel 2
        Quit
      ${EndIf}
      RMDir "$4"
    ${EndIf}
FunctionEnd

; 5. Choose install directory page
Function CalixDirectoryPage
  ${If} $ReinstallPageCheck = 3
    Abort
  ${EndIf}
  Call SkipIfPassive
FunctionEnd
!define MUI_PAGE_CUSTOMFUNCTION_PRE CalixDirectoryPage
!insertmacro MUI_PAGE_DIRECTORY

; 6. Start menu shortcut page
Var AppStartMenuFolder
!if "${STARTMENUFOLDER}" != ""
  !define MUI_PAGE_CUSTOMFUNCTION_PRE SkipIfPassive
  !define MUI_STARTMENUPAGE_DEFAULTFOLDER "${STARTMENUFOLDER}"
!else
  !define MUI_PAGE_CUSTOMFUNCTION_PRE Skip
!endif
!insertmacro MUI_PAGE_STARTMENU Application $AppStartMenuFolder

; 7. Installation page
!insertmacro MUI_PAGE_INSTFILES

; 8. Finish page
;
; Don't auto jump to finish page after installation page,
; because the installation page has useful info that can be used debug any issues with the installer.
!define MUI_FINISHPAGE_NOAUTOCLOSE
; Use show readme button in the finish page as a button create a desktop shortcut
!define MUI_FINISHPAGE_SHOWREADME
!define MUI_FINISHPAGE_SHOWREADME_TEXT "$(createDesktop)"
!define MUI_FINISHPAGE_SHOWREADME_FUNCTION CreateOrUpdateDesktopShortcut
; Show run app after installation.
!define MUI_FINISHPAGE_RUN
!define MUI_FINISHPAGE_RUN_FUNCTION RunMainBinary
!define MUI_PAGE_CUSTOMFUNCTION_PRE SkipIfPassive
!insertmacro MUI_PAGE_FINISH

Function RunMainBinary
  StrCpy $R0 ""
  Call CalixLaunch
FunctionEnd

Function CalixLaunch
  SetOutPath "$INSTDIR"
  !if "${INSTALLMODE}" == "currentUser"
    ExecShell "open" "$INSTDIR\${MAINBINARYNAME}.exe" "$R0" SW_SHOWNORMAL
  !else
    nsis_tauri_utils::RunAsUser "$INSTDIR\${MAINBINARYNAME}.exe" "$R0"
  !endif
FunctionEnd

; Uninstaller Pages
; 1. Confirm uninstall page
Var DeleteAppDataCheckbox
Var DeleteAppDataCheckboxState
!define /ifndef WS_EX_LAYOUTRTL         0x00400000
!define MUI_PAGE_CUSTOMFUNCTION_SHOW un.ConfirmShow
Function un.ConfirmShow
  StrCpy $DeleteAppDataCheckboxState ${BST_UNCHECKED}
  ; $1 inner dialog HWND
  ; $2 window DPI
  ; $3 style
  ; $4 x
  ; $5 y
  ; $6 width
  ; $7 height
  FindWindow $1 "#32770" "" $HWNDPARENT ; Find inner dialog
  System::Call "user32::GetDpiForWindow(p r1) i .r2"
  ${If} $(^RTL) = 1
    StrCpy $3 "${__NSD_CheckBox_EXSTYLE} | ${WS_EX_LAYOUTRTL}"
    IntOp $4 50 * $2
  ${Else}
    StrCpy $3 "${__NSD_CheckBox_EXSTYLE}"
    IntOp $4 0 * $2
  ${EndIf}
  IntOp $5 100 * $2
  IntOp $6 400 * $2
  IntOp $7 25 * $2
  IntOp $4 $4 / 96
  IntOp $5 $5 / 96
  IntOp $6 $6 / 96
  IntOp $7 $7 / 96
  System::Call 'user32::CreateWindowEx(i r3, w "${__NSD_CheckBox_CLASS}", w "$(deleteAppData)", i ${__NSD_CheckBox_STYLE}, i r4, i r5, i r6, i r7, p r1, i0, i0, i0) i .s'
  Pop $DeleteAppDataCheckbox
  SendMessage $HWNDPARENT ${WM_GETFONT} 0 0 $1
  SendMessage $DeleteAppDataCheckbox ${WM_SETFONT} $1 1
FunctionEnd
!define MUI_PAGE_CUSTOMFUNCTION_LEAVE un.ConfirmLeave
Function un.ConfirmLeave
  SendMessage $DeleteAppDataCheckbox ${BM_GETCHECK} 0 0 $DeleteAppDataCheckboxState
FunctionEnd
!define MUI_PAGE_CUSTOMFUNCTION_PRE un.SkipIfPassive
!insertmacro MUI_UNPAGE_CONFIRM

; 2. Uninstalling Page
!insertmacro MUI_UNPAGE_INSTFILES

;Languages
; PageReinstall reads the misspelled `choowHowToInstall` as a fallback, and makensis warns
; about a language string that is read but never set, so default it to an empty string for
; every language. This runs before the language files are included, so a custom language
; file that only defines the old spelling overrides the default and the fallback shows its
; text. `0` as the language id means the language inserted right above.
; TODO: remove the `choowHowToInstall` fallback in a future major version
{{#each languages}}
!insertmacro MUI_LANGUAGE "{{this}}"
LangString choowHowToInstall 0 ""
{{/each}}
!insertmacro MUI_RESERVEFILE_LANGDLL
{{#each language_files}}
  !include "{{this}}"
{{/each}}

Function .onInit
  ${GetOptions} $CMDLINE "/P" $PassiveMode
  ${IfNot} ${Errors}
    StrCpy $PassiveMode 1
  ${EndIf}

  ${GetOptions} $CMDLINE "/NS" $NoShortcutMode
  ${IfNot} ${Errors}
    StrCpy $NoShortcutMode 1
  ${EndIf}

  ${GetOptions} $CMDLINE "/UPDATE" $UpdateMode
  ${IfNot} ${Errors}
    StrCpy $UpdateMode 1
  ${EndIf}

  !if "${DISPLAYLANGUAGESELECTOR}" == "true"
    !insertmacro MUI_LANGDLL_DISPLAY
  !endif

  !insertmacro SetContext

  ${If} $INSTDIR == "${PLACEHOLDER_INSTALL_DIR}"
    ; Set default install location
    !if "${INSTALLMODE}" == "perMachine"
      ${If} ${RunningX64}
        !if "${ARCH}" == "x64"
          StrCpy $INSTDIR "$PROGRAMFILES64\${PRODUCTNAME}"
        !else if "${ARCH}" == "arm64"
          StrCpy $INSTDIR "$PROGRAMFILES64\${PRODUCTNAME}"
        !else
          StrCpy $INSTDIR "$PROGRAMFILES\${PRODUCTNAME}"
        !endif
      ${Else}
        StrCpy $INSTDIR "$PROGRAMFILES\${PRODUCTNAME}"
      ${EndIf}
    !else if "${INSTALLMODE}" == "currentUser"
      StrCpy $INSTDIR "$LOCALAPPDATA\${PRODUCTNAME}"
    !endif

    Call RestorePreviousInstallLocation
  ${EndIf}


  !if "${INSTALLMODE}" == "both"
    !insertmacro MULTIUSER_INIT
  !endif

  ; Abort downgrades if they are disabled, in the modes that skip the reinstall page choice:
  ; silent, passive and update
  !if "${ALLOWDOWNGRADES}" == "false"
  ${If} ${Silent}
  ${OrIf} $PassiveMode = 1
  ${OrIf} $UpdateMode = 1
    ; Compare with the same installation the reinstall page would: a WiX one first
    Call FindWixInstall
    ${If} $R6 != ""
      ReadRegStr $R0 HKLM "$R6" "DisplayVersion"
    ${Else}
      ReadRegStr $R0 SHCTX "${UNINSTKEY}" "DisplayVersion"
    ${EndIf}
    nsis_tauri_utils::SemverCompare "${VERSION}" $R0
    Pop $R0
    ; If downgrading
    ${If} $R0 = -1
      ${If} ${Silent}
        System::Call 'kernel32::AttachConsole(i -1)i.r0'
        ${If} $0 <> 0
          System::Call 'kernel32::GetStdHandle(i -11)i.r0'
          System::call 'kernel32::SetConsoleTextAttribute(i r0, i 0x0004)' ; set red color
          FileWrite $0 "$(silentDowngrades)"
        ${EndIf}
      ${Else}
        MessageBox MB_ICONSTOP "$(silentDowngrades)"
      ${EndIf}
      Abort
    ${EndIf}
  ${EndIf}
  !endif
FunctionEnd

Section WebView2
  ; Check if Webview2 is already installed and skip this section
  ${If} ${RunningX64}
    ReadRegStr $4 HKLM "SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\${WEBVIEW2APPGUID}" "pv"
  ${Else}
    ReadRegStr $4 HKLM "SOFTWARE\Microsoft\EdgeUpdate\Clients\${WEBVIEW2APPGUID}" "pv"
  ${EndIf}
  ${If} $4 == ""
    ReadRegStr $4 HKCU "SOFTWARE\Microsoft\EdgeUpdate\Clients\${WEBVIEW2APPGUID}" "pv"
  ${EndIf}

  ${If} $4 == ""
    ; Webview2 installation
    ;
    ; Skip if updating
    ${If} $UpdateMode <> 1
      !if "${INSTALLWEBVIEW2MODE}" == "downloadBootstrapper"
        Delete "$TEMP\MicrosoftEdgeWebview2Setup.exe"
        DetailPrint "$(webview2Downloading)"
        NSISdl::download "https://go.microsoft.com/fwlink/p/?LinkId=2124703" "$TEMP\MicrosoftEdgeWebview2Setup.exe"
        Pop $0
        ${If} $0 == "success"
          DetailPrint "$(webview2DownloadSuccess)"
        ${Else}
          DetailPrint "$(webview2DownloadError)"
          Abort "$(webview2AbortError)"
        ${EndIf}
        StrCpy $6 "$TEMP\MicrosoftEdgeWebview2Setup.exe"
        Goto install_webview2
      !endif

      !if "${INSTALLWEBVIEW2MODE}" == "embedBootstrapper"
        Delete "$TEMP\MicrosoftEdgeWebview2Setup.exe"
        File "/oname=$TEMP\MicrosoftEdgeWebview2Setup.exe" "${WEBVIEW2BOOTSTRAPPERPATH}"
        DetailPrint "$(installingWebview2)"
        StrCpy $6 "$TEMP\MicrosoftEdgeWebview2Setup.exe"
        Goto install_webview2
      !endif

      !if "${INSTALLWEBVIEW2MODE}" == "offlineInstaller"
        Delete "$TEMP\MicrosoftEdgeWebView2RuntimeInstaller.exe"
        File "/oname=$TEMP\MicrosoftEdgeWebView2RuntimeInstaller.exe" "${WEBVIEW2INSTALLERPATH}"
        DetailPrint "$(installingWebview2)"
        StrCpy $6 "$TEMP\MicrosoftEdgeWebView2RuntimeInstaller.exe"
        Goto install_webview2
      !endif

      Goto webview2_done

      install_webview2:
        DetailPrint "$(installingWebview2)"
        ; $6 holds the path to the webview2 installer
        ExecWait "$6 ${WEBVIEW2INSTALLERARGS} /install" $1
        ${If} $1 = 0
          DetailPrint "$(webview2InstallSuccess)"
        ${Else}
          DetailPrint "$(webview2InstallError)"
          Abort "$(webview2AbortError)"
        ${EndIf}
      webview2_done:
    ${EndIf}
  ${Else}
    !if "${MINIMUMWEBVIEW2VERSION}" != ""
      ${VersionCompare} "${MINIMUMWEBVIEW2VERSION}" "$4" $R0
      ${If} $R0 = 1
        update_webview:
          DetailPrint "$(installingWebview2)"
          ${If} ${RunningX64}
            ReadRegStr $R1 HKLM "SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate" "path"
          ${Else}
            ReadRegStr $R1 HKLM "SOFTWARE\Microsoft\EdgeUpdate" "path"
          ${EndIf}
          ${If} $R1 == ""
            ReadRegStr $R1 HKCU "SOFTWARE\Microsoft\EdgeUpdate" "path"
          ${EndIf}
          ${If} $R1 != ""
            ; Chromium updater docs: https://source.chromium.org/chromium/chromium/src/+/main:docs/updater/user_manual.md
            ; Modified from "HKEY_LOCAL_MACHINE\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\Microsoft EdgeWebView\ModifyPath"
            ExecWait `"$R1" /install appguid=${WEBVIEW2APPGUID}&needsadmin=true` $1
            ${If} $1 = 0
              DetailPrint "$(webview2InstallSuccess)"
            ${Else}
              MessageBox MB_ICONEXCLAMATION|MB_ABORTRETRYIGNORE "$(webview2InstallError)" IDIGNORE ignore IDRETRY update_webview
              Quit
              ignore:
            ${EndIf}
          ${EndIf}
      ${EndIf}
    !endif
  ${EndIf}
SectionEnd

Section Install
  ReadRegStr $CalixPreviousDisplayName SHCTX "${UNINSTKEY}" "DisplayName"
  Call FindWixInstall
  ${If} $R6 != ""
    StrCpy $WixMode 1
  ${Else}
    Call CalixResolveInstallLocation
    StrCpy $CalixPreviousLocation $4
  ${EndIf}
  ${If} $ReinstallPageCheck = 3
    Call CalixChooseSideBySideLocation
  ${ElseIf} $WixMode = 1
    Call CalixRemovePreviousInstallation
  ${ElseIf} $UpdateMode <> 1
  ${AndIf} $CalixPreviousLocation != ""
    Call CalixRemovePreviousInstallation
  ${EndIf}
  ${If} $ReinstallPageCheck = 2
    ; The fresh installation cannot live inside a directory being reset.
    GetFullPathName $0 "$INSTDIR\."
    StrCpy $0 "$0\"
    StrCpy $1 "$APPDATA\LutteLaurent\Calix\"
    StrLen $2 $1
    StrCpy $3 $0 $2
    ${If} $3 == $1
      Goto calix_reset_install_path_invalid
    ${EndIf}
    StrCpy $1 "$LOCALAPPDATA\${BUNDLEID}\"
    StrLen $2 $1
    StrCpy $3 $0 $2
    ${If} $3 == $1
      calix_reset_install_path_invalid:
      MessageBox MB_ICONEXCLAMATION "데이터 폴더와 다른 위치에 설치하세요."
      SetErrorLevel 2
      Quit
    ${EndIf}
  ${EndIf}
  SetOutPath $INSTDIR

  !ifmacrodef NSIS_HOOK_PREINSTALL
    !insertmacro NSIS_HOOK_PREINSTALL
  !endif

  !insertmacro CheckIfAppIsRunning "$INSTDIR\${MAINBINARYNAME}.exe" "${PRODUCTNAME}"

  ; Copy main executable
  File "${MAINBINARYSRCPATH}"

  ; Copy resources
  {{#each resources_dirs}}
    CreateDirectory "$INSTDIR\\{{this}}"
  {{/each}}
  {{#each resources}}
    File /a "/oname={{this.[1]}}" "{{no-escape @key}}"
  {{/each}}

  ; Copy external binaries
  {{#each binaries}}
    File /a "/oname={{this}}" "{{no-escape @key}}"
  {{/each}}

  ; Create file associations
  {{#each file_associations as |association| ~}}
    {{#each association.ext as |ext| ~}}
       !insertmacro APP_ASSOCIATE "{{ext}}" "{{or association.name ext}}" "{{association-description association.description ext}}" "$\"$INSTDIR\${MAINBINARYNAME}.exe$\",0" "Open with ${PRODUCTNAME}" "$\"$INSTDIR\${MAINBINARYNAME}.exe$\" $\"%1$\""
    {{/each}}
  {{/each}}

  ; Register deep links
  {{#each deep_link_protocols as |protocol| ~}}
    WriteRegStr SHCTX "Software\Classes\\{{protocol}}" "URL Protocol" ""
    WriteRegStr SHCTX "Software\Classes\\{{protocol}}" "" "URL:${BUNDLEID} protocol"
    WriteRegStr SHCTX "Software\Classes\\{{protocol}}\DefaultIcon" "" "$\"$INSTDIR\${MAINBINARYNAME}.exe$\",0"
    WriteRegStr SHCTX "Software\Classes\\{{protocol}}\shell\open\command" "" "$\"$INSTDIR\${MAINBINARYNAME}.exe$\" $\"%1$\""
  {{/each}}

  ${If} $ReinstallPageCheck = 2
    Call CalixResetSelectedData
  ${ElseIf} $ReinstallPageCheck = 3
    ; The preserved executable is usable, but only the new install is registered.
    ClearErrors
    Rename "$CalixPreviousLocation\uninstall.exe" "$CalixPreviousLocation\uninstall.previous"
    ${If} ${Errors}
      MessageBox MB_ICONEXCLAMATION "이전 버전을 보관하지 못했습니다."
      SetErrorLevel 2
      Quit
    ${EndIf}
  ${EndIf}

  ; Create uninstaller
  WriteUninstaller "$INSTDIR\uninstall.exe"

  ; Save $INSTDIR in registry for future installations
  WriteRegStr SHCTX "${MANUPRODUCTKEY}" "" $INSTDIR

  !if "${INSTALLMODE}" == "both"
    ; Save install mode to be selected by default for the next installation such as updating
    ; or when uninstalling
    WriteRegStr SHCTX "${UNINSTKEY}" $MultiUser.InstallMode 1
  !endif

  ; Remove old main binary if it doesn't match new main binary name
  ReadRegStr $OldMainBinaryName SHCTX "${UNINSTKEY}" "MainBinaryName"
  ${If} $OldMainBinaryName != ""
  ${AndIf} $OldMainBinaryName != "${MAINBINARYNAME}.exe"
    Delete "$INSTDIR\$OldMainBinaryName"
  ${EndIf}

  ; Save current MAINBINARYNAME for future updates
  WriteRegStr SHCTX "${UNINSTKEY}" "MainBinaryName" "${MAINBINARYNAME}.exe"

  ; Registry information for add/remove programs
  WriteRegStr SHCTX "${UNINSTKEY}" "DisplayName" "${CALIXDISPLAYNAME}"
  WriteRegStr SHCTX "${UNINSTKEY}" "DisplayIcon" "$\"$INSTDIR\${MAINBINARYNAME}.exe$\""
  WriteRegStr SHCTX "${UNINSTKEY}" "DisplayVersion" "${VERSION}"
  WriteRegStr SHCTX "${UNINSTKEY}" "Publisher" "${MANUFACTURER}"
  WriteRegStr SHCTX "${UNINSTKEY}" "InstallLocation" "$\"$INSTDIR$\""
  WriteRegStr SHCTX "${UNINSTKEY}" "UninstallString" "$\"$INSTDIR\uninstall.exe$\""
  WriteRegDWORD SHCTX "${UNINSTKEY}" "NoModify" "1"
  WriteRegDWORD SHCTX "${UNINSTKEY}" "NoRepair" "1"

  ${GetSize} "$INSTDIR" "/M=uninstall.exe /S=0K /G=0" $0 $1 $2
  IntOp $0 $0 + ${ESTIMATEDSIZE}
  IntFmt $0 "0x%08X" $0
  WriteRegDWORD SHCTX "${UNINSTKEY}" "EstimatedSize" "$0"

  !if "${HOMEPAGE}" != ""
    WriteRegStr SHCTX "${UNINSTKEY}" "URLInfoAbout" "${HOMEPAGE}"
    WriteRegStr SHCTX "${UNINSTKEY}" "URLUpdateInfo" "${HOMEPAGE}"
    WriteRegStr SHCTX "${UNINSTKEY}" "HelpLink" "${HOMEPAGE}"
  !endif

  ; Create start menu shortcut
  !insertmacro MUI_STARTMENU_WRITE_BEGIN Application
    Call CreateOrUpdateStartMenuShortcut
  !insertmacro MUI_STARTMENU_WRITE_END

  ; Create desktop shortcut for silent and passive installers
  ; because finish page will be skipped
  ${If} $PassiveMode = 1
  ${OrIf} ${Silent}
    Call CreateOrUpdateDesktopShortcut
  ${EndIf}

  !ifmacrodef NSIS_HOOK_POSTINSTALL
    !insertmacro NSIS_HOOK_POSTINSTALL
  !endif

  ; Auto close this page for passive mode
  ${If} $PassiveMode = 1
    SetAutoClose true
  ${EndIf}
SectionEnd

Function .onInstSuccess
  ; Older app versions pass /UPDATE without /R. Relaunch them as well.
  ; Interactive Setup uses the Finish page run checkbox.
  ${If} $PassiveMode = 1
  ${OrIf} ${Silent}
    ${GetOptions} $CMDLINE "/R" $R0
    ${IfNot} ${Errors}
    ${OrIf} $UpdateMode = 1
      ${GetOptions} $CMDLINE "/ARGS" $R0
      Call CalixLaunch
    ${EndIf}
  ${EndIf}
FunctionEnd

Function un.onInit
  !insertmacro SetContext

  !if "${INSTALLMODE}" == "both"
    !insertmacro MULTIUSER_UNINIT
  !endif

  !insertmacro MUI_UNGETLANGUAGE

  ${GetOptions} $CMDLINE "/P" $PassiveMode
  ${IfNot} ${Errors}
    StrCpy $PassiveMode 1
  ${EndIf}

  ${GetOptions} $CMDLINE "/UPDATE" $UpdateMode
  ${IfNot} ${Errors}
    StrCpy $UpdateMode 1
  ${EndIf}
FunctionEnd

Section Uninstall

  !ifmacrodef NSIS_HOOK_PREUNINSTALL
    !insertmacro NSIS_HOOK_PREUNINSTALL
  !endif

  !insertmacro CheckIfAppIsRunning "$INSTDIR\${MAINBINARYNAME}.exe" "${PRODUCTNAME}"

  ; Delete the app directory and its content from disk
  ; Copy main executable
  Delete "$INSTDIR\${MAINBINARYNAME}.exe"

  ; Delete resources
  {{#each resources}}
    Delete "$INSTDIR\\{{this.[1]}}"
  {{/each}}

  ; Delete external binaries
  {{#each binaries}}
    Delete "$INSTDIR\\{{this}}"
  {{/each}}

  ; Delete app associations
  {{#each file_associations as |association| ~}}
    {{#each association.ext as |ext| ~}}
      !insertmacro APP_UNASSOCIATE "{{ext}}" "{{or association.name ext}}"
    {{/each}}
  {{/each}}

  ; Delete deep links
  {{#each deep_link_protocols as |protocol| ~}}
    ReadRegStr $R7 SHCTX "Software\Classes\\{{protocol}}\shell\open\command" ""
    ${If} $R7 == "$\"$INSTDIR\${MAINBINARYNAME}.exe$\" $\"%1$\""
      DeleteRegKey SHCTX "Software\Classes\\{{protocol}}"
    ${EndIf}
  {{/each}}


  ; Delete uninstaller
  Delete "$INSTDIR\uninstall.exe"

  {{#each resources_ancestors}}
  RMDir /REBOOTOK "$INSTDIR\\{{this}}"
  {{/each}}
  RMDir "$INSTDIR"

  ; Remove shortcuts if not updating
  ${If} $UpdateMode <> 1
    !insertmacro DeleteAppUserModelId

    ; Remove start menu shortcut
    !insertmacro MUI_STARTMENU_GETFOLDER Application $AppStartMenuFolder
    !insertmacro IsShortcutTarget "$SMPROGRAMS\$AppStartMenuFolder\${CALIXDISPLAYNAME}.lnk" "$INSTDIR\${MAINBINARYNAME}.exe"
    Pop $0
    ${If} $0 = 1
      !insertmacro UnpinShortcut "$SMPROGRAMS\$AppStartMenuFolder\${CALIXDISPLAYNAME}.lnk"
      Delete "$SMPROGRAMS\$AppStartMenuFolder\${CALIXDISPLAYNAME}.lnk"
      RMDir "$SMPROGRAMS\$AppStartMenuFolder"
    ${EndIf}
    !insertmacro IsShortcutTarget "$SMPROGRAMS\${CALIXDISPLAYNAME}.lnk" "$INSTDIR\${MAINBINARYNAME}.exe"
    Pop $0
    ${If} $0 = 1
      !insertmacro UnpinShortcut "$SMPROGRAMS\${CALIXDISPLAYNAME}.lnk"
      Delete "$SMPROGRAMS\${CALIXDISPLAYNAME}.lnk"
    ${EndIf}

    ; Remove desktop shortcuts
    !insertmacro IsShortcutTarget "$DESKTOP\${CALIXDISPLAYNAME}.lnk" "$INSTDIR\${MAINBINARYNAME}.exe"
    Pop $0
    ${If} $0 = 1
      !insertmacro UnpinShortcut "$DESKTOP\${CALIXDISPLAYNAME}.lnk"
      Delete "$DESKTOP\${CALIXDISPLAYNAME}.lnk"
    ${EndIf}
  ${EndIf}

  ; Remove registry information for add/remove programs
  !if "${INSTALLMODE}" == "both"
    DeleteRegKey SHCTX "${UNINSTKEY}"
  !else if "${INSTALLMODE}" == "perMachine"
    DeleteRegKey HKLM "${UNINSTKEY}"
  !else
    DeleteRegKey HKCU "${UNINSTKEY}"
  !endif

  ; Removes the Autostart entry for ${PRODUCTNAME} from the HKCU Run key if it exists.
  ; This ensures the program does not launch automatically after uninstallation if it exists.
  ; If it doesn't exist, it does nothing.
  ; We do this when not updating (to preserve the registry value on updates)
  ${If} $UpdateMode <> 1
    DeleteRegValue HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "${PRODUCTNAME}"
  ${EndIf}

  ; Delete app data if the checkbox is selected
  ; and if not updating
  ${If} $DeleteAppDataCheckboxState = ${BST_CHECKED}
  ${AndIf} $UpdateMode <> 1
    ; Clear the install location $INSTDIR from registry
    DeleteRegKey SHCTX "${MANUPRODUCTKEY}"
    DeleteRegKey /ifempty SHCTX "${MANUKEY}"

    ; Clear the install language from registry
    DeleteRegValue HKCU "${MANUPRODUCTKEY}" "Installer Language"
    DeleteRegKey /ifempty HKCU "${MANUPRODUCTKEY}"
    DeleteRegKey /ifempty HKCU "${MANUKEY}"

    SetShellVarContext current
    RmDir /r "$APPDATA\${BUNDLEID}"
    RmDir /r "$LOCALAPPDATA\${BUNDLEID}"
  ${EndIf}

  !ifmacrodef NSIS_HOOK_POSTUNINSTALL
    !insertmacro NSIS_HOOK_POSTUNINSTALL
  !endif

  ; Auto close if passive mode or updating
  ${If} $PassiveMode = 1
  ${OrIf} $UpdateMode = 1
    SetAutoClose true
  ${EndIf}
SectionEnd

Function RestorePreviousInstallLocation
  Call CalixResolveInstallLocation
  StrCmp $4 "" +2 0
    StrCpy $INSTDIR $4
FunctionEnd

Function Skip
  Abort
FunctionEnd

Function SkipIfPassive
  ${IfThen} $PassiveMode = 1  ${|} Abort ${|}
FunctionEnd
Function un.SkipIfPassive
  ${IfThen} $PassiveMode = 1  ${|} Abort ${|}
FunctionEnd

Function CreateOrUpdateStartMenuShortcut
  !if "${STARTMENUFOLDER}" != ""
    StrCpy $R1 "$SMPROGRAMS\$AppStartMenuFolder"
  !else
    StrCpy $R1 "$SMPROGRAMS"
  !endif
  Call CalixCreateShortcut
FunctionEnd

Function CreateOrUpdateDesktopShortcut
  StrCpy $R1 "$DESKTOP"
  Call CalixCreateShortcut
FunctionEnd

Function CalixCreateShortcut
  ${If} $NoShortcutMode = 1
    Return
  ${EndIf}
  StrCpy $R2 "$R1\${CALIXDISPLAYNAME}.lnk"
  StrCpy $R3 "$R1\${PRODUCTNAME}.lnk"
  ; DisplayName comes from the stable key. Construct versioned paths from
  ; validated version characters only, and only remove links to Calix.
  StrCpy $R4 $CalixPreviousDisplayName 7
  StrCpy $R5 $CalixPreviousDisplayName 1 -1
  ${If} $R4 == "Calix ("
  ${AndIf} $R5 == ")"
    StrCpy $R4 $CalixPreviousDisplayName -1 7
    ${If} $R4 != ""
      StrCpy $R5 0
      ${Do}
        StrCpy $R6 $R4 1 $R5
        ${If} $R6 == ""
          StrCpy $R3 "$R1\$CalixPreviousDisplayName.lnk"
          ${ExitDo}
        ${EndIf}
        ${StrLoc} $R7 "0123456789." "$R6" ">"
        ${If} $R7 == ""
          ${ExitDo}
        ${EndIf}
        IntOp $R5 $R5 + 1
      ${Loop}
    ${EndIf}
  ${EndIf}
  StrCpy $R4 0
  ${If} $CalixPreviousLocation != ""
    !insertmacro IsShortcutTarget "$R3" "$CalixPreviousLocation\${MAINBINARYNAME}.exe"
    Pop $R4
  ${EndIf}
  ${If} $UpdateMode = 1
  ${AndIf} $R4 <> 1
    Return
  ${EndIf}
  CreateDirectory "$R1"
  ClearErrors
  CreateShortcut "$R2" "$INSTDIR\${MAINBINARYNAME}.exe"
  ${IfNot} ${Errors}
    !insertmacro SetLnkAppUserModelId "$R2"
    ${If} $R4 = 1
    ${AndIf} $R2 != $R3
      Delete "$R3"
    ${EndIf}
  ${EndIf}
FunctionEnd

; Resolve by the stable uninstall key first. Publisher labels may change.
Function CalixChooseSideBySideLocation
  ${GetParent} "$CalixPreviousLocation" $0
  StrCpy $INSTDIR "$0\Calix ${VERSION}"
  StrCpy $1 1
  ${While} ${FileExists} "$INSTDIR"
    IntOp $1 $1 + 1
    StrCpy $INSTDIR "$0\Calix ${VERSION} ($1)"
  ${EndWhile}
FunctionEnd

Function CalixResetSelectedData
  ; Move both stores first so a locked profile cannot cause a partial reset.
  StrCpy $CalixResetRoaming ""
  StrCpy $CalixResetLocal ""
  ${If} ${FileExists} "$APPDATA\LutteLaurent\Calix"
    GetTempFileName $0 "$APPDATA\LutteLaurent"
    ${If} $0 == ""
      Goto calix_reset_failed
    ${EndIf}
    Delete "$0"
    ClearErrors
    Rename "$APPDATA\LutteLaurent\Calix" "$0"
    ${If} ${Errors}
      Goto calix_reset_failed
    ${EndIf}
    StrCpy $CalixResetRoaming $0
  ${EndIf}
  ${If} ${FileExists} "$LOCALAPPDATA\${BUNDLEID}"
    GetTempFileName $0 "$LOCALAPPDATA"
    ${If} $0 == ""
      Goto calix_reset_failed
    ${EndIf}
    Delete "$0"
    ClearErrors
    Rename "$LOCALAPPDATA\${BUNDLEID}" "$0"
    ${If} ${Errors}
      Goto calix_reset_failed
    ${EndIf}
    StrCpy $CalixResetLocal $0
  ${EndIf}

  ; An empty directory prevents the old BUFS database from being imported again.
  ClearErrors
  CreateDirectory "$APPDATA\LutteLaurent\Calix"
  ${If} ${Errors}
    Goto calix_reset_failed
  ${EndIf}
  ${If} $CalixResetRoaming != ""
    Push "$CalixResetRoaming"
    Call CalixRemoveTree
  ${EndIf}
  ${If} $CalixResetLocal != ""
    Push "$CalixResetLocal"
    Call CalixRemoveTree
  ${EndIf}
  ${If} ${FileExists} "$CalixResetRoaming"
  ${OrIf} ${FileExists} "$CalixResetLocal"
    MessageBox MB_ICONEXCLAMATION "데이터가 초기화되었지만 일부 이전 파일을 삭제하지 못했습니다."
    SetErrorLevel 2
    Quit
  ${EndIf}
  Return

  calix_reset_failed:
  ${If} $CalixResetRoaming != ""
    Rename "$CalixResetRoaming" "$APPDATA\LutteLaurent\Calix"
  ${EndIf}
  ${If} $CalixResetLocal != ""
    Rename "$CalixResetLocal" "$LOCALAPPDATA\${BUNDLEID}"
  ${EndIf}
  MessageBox MB_ICONEXCLAMATION "데이터를 초기화하지 못했습니다. Calix를 종료한 뒤 다시 시도하세요."
  SetErrorLevel 2
  Quit
FunctionEnd

Function CalixRemoveTree
  Exch $0
  Push $1
  Push $2
  Push $3
  System::Call 'kernel32::GetFileAttributesW(w r0) i .r1'
  ${If} $1 != -1
    IntOp $2 $1 & 0x10
    ${If} $2 = 0
      Delete "$0"
    ${Else}
      ; A junction or directory symlink is removed without visiting its target.
      IntOp $2 $1 & 0x400
      ${If} $2 = 0
        ClearErrors
        FindFirst $2 $3 "$0\*"
        ${IfNot} ${Errors}
          ${Do}
            ${If} $3 != "."
            ${AndIf} $3 != ".."
              Push "$0\$3"
              Call CalixRemoveTree
            ${EndIf}
            ClearErrors
            FindNext $2 $3
          ${LoopUntil} ${Errors}
          FindClose $2
        ${EndIf}
      ${EndIf}
      RMDir "$0"
    ${EndIf}
  ${EndIf}
  Pop $3
  Pop $2
  Pop $1
  Pop $0
FunctionEnd

Function CalixResolveInstallLocation
  ReadRegStr $4 SHCTX "${UNINSTKEY}" "InstallLocation"
  Call CalixValidateInstallLocation
  ${If} $4 == ""
    ReadRegStr $4 SHCTX "${MANUPRODUCTKEY}" ""
    Call CalixValidateInstallLocation
  ${EndIf}
  ${If} $4 == ""
    ReadRegStr $4 SHCTX "Software\Lutté Laurent\Calix" ""
    Call CalixValidateInstallLocation
  ${EndIf}
FunctionEnd
Function CalixValidateInstallLocation
  Push $0
  StrCpy $0 $4 1
  ${If} $0 == '$\"'
    StrCpy $0 $4 1 -1
    ${If} $0 == '$\"'
      StrCpy $4 $4 -1 1
    ${Else}
      StrCpy $4 ""
    ${EndIf}
  ${EndIf}
  ${If} $4 != ""
    ${GetRoot} "$4" $0
    ${If} $0 == ""
    ${OrIf} $4 == $0
    ${OrIf} $4 == "$0\"
      StrCpy $4 ""
    ${ElseIfNot} ${FileExists} "$4\uninstall.exe"
      StrCpy $4 ""
    ${EndIf}
  ${EndIf}
  Pop $0
FunctionEnd
