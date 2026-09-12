; Script de Inno Setup: genera el instalador tipo asistente ("Siguiente ->
; Siguiente -> Instalar -> Finalizar", PROJECT_SPEC.md) para ASTRIM POS en
; Windows. Ver installer/README.md y README_BUILD.md (raíz del repo) para
; el flujo completo.
;
; Requiere que `dist\ASTRIM_POS\` ya exista (salida de PyInstaller, ver
; pos.spec) antes de compilar este script con Inno Setup (ISCC.exe / IDE
; de Inno Setup) — `build_scripts\build.bat`/`.ps1` hacen ambos pasos en
; el orden correcto con un solo comando.
;
; AppId es un GUID fijo: NO cambiar entre versiones — es lo que permite que
; el instalador reconozca una instalación previa y ofrezca actualizarla en
; vez de instalar en paralelo (ver sección "Actualizaciones" en el README).

#define MyAppName "ASTRIM POS"
#define MyAppPublisher "ASTRIM"
#define MyAppSlogan "Tecnología que impulsa tu negocio."
#define MyAppExeName "ASTRIM_POS.exe"
#define MyAppId "{{93C16703-95A6-4365-9D08-0798718628DD}"
#define MyAppDistDir "..\dist\ASTRIM_POS"
; La versión NO se declara acá a mano: se lee del propio .exe ya compilado
; (recurso VERSIONINFO que `pos.spec` escribe a partir de la única fuente de
; verdad real, `[project].version` en pyproject.toml — ver ese archivo). Así
; el número que ve el cliente en el instalador y en "Programas y
; características" siempre coincide exactamente con el del ejecutable,
; sin paso manual de sincronización que se pueda olvidar entre versiones.
#define MyAppVersion GetFileVersionString(MyAppDistDir + "\" + MyAppExeName)

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppComments={#MyAppName} - {#MyAppSlogan}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=dist_installer
OutputBaseFilename=ASTRIM_POS_Setup_v{#MyAppVersion}
SetupIconFile=..\resources\icons\pos.ico
WizardImageFile=assets\wizard_image.bmp
WizardSmallImageFile=assets\wizard_small.bmp
; Muestra COPYRIGHT.txt como pantalla de aceptación de condiciones del
; asistente ("Al continuar con la instalación, usted acepta estas
; condiciones", ver ese archivo) antes de permitir avanzar con la
; instalación.
LicenseFile=..\COPYRIGHT.txt
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; Instala en Program Files (equipo completo, no solo el usuario actual) y
; crea la carpeta compartida en ProgramData (ver [Dirs] más abajo) — a
; propósito requiere privilegios de administrador durante la instalación
; (antes este instalador usaba PrivilegesRequired=lowest para no pedir
; contraseña de administrador en cuentas restringidas; se cambia acá
; porque Program Files y ProgramData no son escribibles por una cuenta
; estándar sin elevar).
PrivilegesRequired=admin
UninstallDisplayIcon={app}\{#MyAppExeName}
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Messages]
spanish.WelcomeLabel2=Este asistente instalará [name/ver] en este equipo.%n%n{#MyAppSlogan}%n%nSe recomienda cerrar el resto de aplicaciones antes de continuar.

[Tasks]
Name: "desktopicon"; Description: "Crear un acceso directo en el escritorio"; GroupDescription: "Accesos directos adicionales:"
Name: "startuplaunch"; Description: "Iniciar {#MyAppName} automáticamente al encender el equipo"; GroupDescription: "Accesos directos adicionales:"

[Dirs]
; Carpeta compartida reservada en ProgramData (pedida para esta versión
; del instalador). IMPORTANTE: la aplicación en sí sigue guardando la
; base de datos, la licencia y los respaldos en el perfil del usuario
; actual (%USERPROFILE%\.pos_system, ver core/config/bootstrap.py::
; get_app_data_dir — sin cambios, no se toca lógica de negocio en esta
; tarea). Esta carpeta queda disponible para uso compartido futuro entre
; usuarios del mismo equipo; hoy el instalador solo la crea y le da
; permisos de escritura a cuentas estándar.
Name: "{commonappdata}\ASTRIM"; Permissions: users-modify

[Files]
; Todo el contenido de dist\ASTRIM_POS\ (salida de `pyinstaller installer/pos.spec`),
; incluyendo ASTRIM_POS.exe, las librerías empaquetadas y los datos agregados en
; pos.spec (alembic.ini, migrations/, fuentes, docs/branding, licenses_pool.db).
Source: "{#MyAppDistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; COPYRIGHT.txt y THIRD-PARTY-NOTICES.txt se copian aparte, directo desde la
; raíz del repo a la raíz de instalación (junto a ASTRIM_POS.exe) -- si se
; agregaran a `datas` en pos.spec en cambio quedarían enterrados en
; _internal\ (layout de PyInstaller 6.x), donde nadie los va a encontrar.
Source: "..\COPYRIGHT.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\THIRD-PARTY-NOTICES.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Desinstalar {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{commonstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: startuplaunch

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Ejecutar {#MyAppName} al finalizar la instalación"; Flags: nowait postinstall skipifsilent

; Deliberadamente NO se borra la carpeta de datos del negocio al
; desinstalar (%USERPROFILE%\.pos_system — base de datos, backups,
; licencia — ver core/config/bootstrap.py::get_app_data_dir). Desinstalar
; el programa nunca debe borrar los datos del negocio; si el usuario
; quiere borrarlos también, lo hace a mano y de forma consciente. Lo
; mismo aplica a la carpeta de {commonappdata}\ASTRIM creada arriba.
