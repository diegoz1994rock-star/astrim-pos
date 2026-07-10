; Script de Inno Setup: genera el instalador tipo asistente ("Siguiente ->
; Siguiente -> Instalar -> Finalizar", PROJECT_SPEC.md) para el Sistema
; POS en Windows. Ver installer/README.md para el flujo completo.
;
; Requiere que `dist\pos\` ya exista (salida de PyInstaller, ver pos.spec)
; antes de compilar este script con Inno Setup (ISCC.exe / IDE de Inno Setup).
;
; AppId es un GUID fijo: NO cambiar entre versiones — es lo que permite que
; el instalador reconozca una instalación previa y ofrezca actualizarla en
; vez de instalar en paralelo.

#define MyAppName "Sistema POS"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "Tu Empresa"
#define MyAppExeName "pos.exe"
#define MyAppId "{{93C16703-95A6-4365-9D08-0798718628DD}"

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=dist_installer
OutputBaseFilename=SistemaPOS-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; No requiere privilegios de administrador: instala bajo el perfil del
; usuario actual por defecto (autopf resuelve Program Files si se ejecuta
; elevado, o AppData\Local si no) — evita pedir contraseña de admin en
; equipos de punto de venta con cuentas restringidas.
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\{#MyAppExeName}
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear un acceso directo en el escritorio"; GroupDescription: "Accesos directos adicionales:"

[Files]
; Todo el contenido de dist\pos\ (salida de `pyinstaller installer/pos.spec`),
; incluyendo pos.exe, las librerías empaquetadas y los datos agregados en
; pos.spec (alembic.ini, migrations/).
Source: "..\dist\pos\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Desinstalar {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Abrir {#MyAppName} ahora"; Flags: nowait postinstall skipifsilent

; Deliberadamente NO se borra la carpeta de datos del negocio al
; desinstalar (%USERPROFILE%\.pos_system — base de datos, backups,
; licencia — ver core/config/bootstrap.py::get_app_data_dir). Desinstalar
; el programa nunca debe borrar los datos del negocio; si el usuario
; quiere borrarlos también, lo hace a mano y de forma consciente.
