#!/usr/bin/env bash
#
# Einrichtungs-Skript für Schnacker (Ubuntu / GNOME / Wayland).
#
# Was es tut:
#   1. Installiert die nötigen System-Pakete (apt) — fragt einmal nach sudo.
#   2. Legt eine Python-Umgebung (venv) an und installiert die Python-Pakete.
#   3. Richtet ydotool fürs automatische Einfügen ein (uinput-Rechte + Hintergrund-Dienst).
#   4. Legt einen Programmstarter (.desktop) an.
#
# Aufruf:  ./setup.sh
#
set -euo pipefail

# Verzeichnis dieses Skripts (= Projektwurzel), egal von wo aufgerufen.
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"

say() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }

# ---------------------------------------------------------------------------
say "1/4  System-Pakete installieren (sudo nötig)"
# python3-gi/GTK = Oberfläche, appindicator = Menüleisten-Symbol,
# libportaudio2 = Mikrofon, wl-clipboard = Zwischenablage, ydotool = Auto-Einfügen.
SYS_PKGS=(
  python3-venv python3-dev python3-gi python3-gi-cairo
  gir1.2-gtk-3.0 gir1.2-ayatanaappindicator3-0.1
  libportaudio2 wl-clipboard ydotool
)
sudo apt-get update
sudo apt-get install -y "${SYS_PKGS[@]}"

# ---------------------------------------------------------------------------
say "2/4  Python-Umgebung anlegen und Pakete installieren"
# --system-site-packages: damit das System-GTK (python3-gi) in der venv sichtbar ist.
if [ ! -d "$VENV_DIR" ]; then
  python3 -m venv --system-site-packages "$VENV_DIR"
fi
"$VENV_DIR/bin/pip" install --upgrade pip
"$VENV_DIR/bin/pip" install -r "$PROJECT_DIR/requirements.txt"

# ---------------------------------------------------------------------------
say "3/4  Auto-Einfügen (ydotool) einrichten"
# udev-Regel: erlaubt der Gruppe 'input' den Zugriff auf /dev/uinput.
UDEV_RULE="/etc/udev/rules.d/80-blitztext-uinput.rules"
if [ ! -f "$UDEV_RULE" ]; then
  echo 'KERNEL=="uinput", GROUP="input", MODE="0660", OPTIONS+="static_node=uinput"' \
    | sudo tee "$UDEV_RULE" >/dev/null
  sudo udevadm control --reload-rules
  sudo udevadm trigger /dev/uinput || true
fi
# Aktuellen Benutzer der Gruppe 'input' hinzufügen (greift erst nach Neu-Anmeldung).
if ! id -nG "$USER" | grep -qw input; then
  sudo usermod -aG input "$USER"
  NEED_RELOGIN=1
fi

# ydotoold-Daemon: nur die moderne ydotool-Reihe (1.x) hat ihn. Ubuntu 24.04
# liefert aber ydotool 0.1.8 OHNE Daemon — das greift direkt auf /dev/uinput zu
# (Rechte siehe udev-Regel + Gruppe 'input' oben). Daher den Dienst NUR anlegen,
# wenn ydotoold wirklich vorhanden ist; sonst würde er mit Status 203/EXEC abstürzen.
YDOTOOLD_BIN="$(command -v ydotoold || true)"
if [ -n "$YDOTOOLD_BIN" ]; then
  SERVICE_DIR="$HOME/.config/systemd/user"
  mkdir -p "$SERVICE_DIR"
  cat > "$SERVICE_DIR/ydotoold.service" <<EOF
[Unit]
Description=ydotool daemon (für Schnacker Auto-Einfügen)

[Service]
ExecStart=$YDOTOOLD_BIN -p %t/.ydotool_socket -P 0660
Restart=always

[Install]
WantedBy=default.target
EOF
  systemctl --user daemon-reload
  systemctl --user enable --now ydotoold.service || \
    echo "Hinweis: ydotoold startet sauber nach einer Neu-Anmeldung (input-Gruppe)."
else
  echo "ydotoold nicht gefunden (ydotool 0.1.8 braucht keinen Daemon) — überspringe Dienst."
fi

# ---------------------------------------------------------------------------
say "4/4  Programmstarter (.desktop) anlegen"
APPS_DIR="$HOME/.local/share/applications"
mkdir -p "$APPS_DIR"
cat > "$APPS_DIR/blitztext.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Schnacker
Comment=Sprache zu Text in der Menüleiste
Exec=$VENV_DIR/bin/python -m blitztext
Path=$PROJECT_DIR
Icon=$PROJECT_DIR/blitztext/resources/icon.png
Terminal=false
Categories=Utility;AudioVideo;
EOF
update-desktop-database "$APPS_DIR" 2>/dev/null || true

say "Fertig!"
echo "Starten mit:   $VENV_DIR/bin/python -m blitztext"
echo "Oder über das Anwendungsmenü: 'Schnacker'."
if [ "${NEED_RELOGIN:-0}" = "1" ]; then
  echo
  echo "WICHTIG: Bitte einmal ab- und wieder anmelden, damit das Auto-Einfügen (ydotool) funktioniert."
fi
