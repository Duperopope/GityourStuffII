import sys
import os
import shutil
import zipfile
import random
import threading
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QLabel, QFileDialog,
    QWidget, QVBoxLayout, QHBoxLayout, QGraphicsDropShadowEffect, QStyle
)
from PyQt5.QtCore import Qt, QTimer, QPointF, QPropertyAnimation, pyqtProperty, pyqtSignal, QEasingCurve, QSize, QObject, QUrl
from PyQt5.QtGui import QPainter, QColor, QFont, QRadialGradient, QPixmap, QFontDatabase, QImage
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

from requests_oauthlib import OAuth2Session
import requests  # Import pour télécharger l'avatar

# Constants pour l'OAuth GitHub
CLIENT_ID = 'Ov23lie1vc5lKwoGfgwK'  # Remplacez par votre Client ID GitHub OAuth App
CLIENT_SECRET = 'edbc3fdd01b4d0c9f5d1bc4408cf53b4cd07b520'  # Remplacez par votre Client Secret GitHub OAuth App
AUTHORIZATION_BASE_URL = 'https://github.com/login/oauth/authorize'
TOKEN_URL = 'https://github.com/login/oauth/access_token'
SCOPE = ['repo', 'user']
REDIRECT_URI = 'http://localhost:8000/callback'


# Les classes StarField, GlowingButton, NotificationArea, AnimatedLabel restent inchangées

class OAuthCallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Parse the URL and extract the authorization code
        parsed_path = urlparse(self.path)
        if parsed_path.path == '/callback':
            query_params = parse_qs(parsed_path.query)
            if 'code' in query_params:
                self.server.auth_code = query_params['code'][0]
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'Authentication successful. You can close this window.')
            else:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b'Authentication failed.')
        else:
            self.send_response(404)
            self.end_headers()


class OAuthCallbackServer(HTTPServer):
    def __init__(self, server_address, RequestHandlerClass):
        super().__init__(server_address, RequestHandlerClass)
        self.auth_code = None


class GitHubOAuth(QObject):
    auth_completed = pyqtSignal(bool, str, str)

    def __init__(self):
        super().__init__()
        self.client_id = CLIENT_ID
        self.client_secret = CLIENT_SECRET
        self.redirect_uri = REDIRECT_URI
        self.scope = SCOPE
        self.session = None
        self.username = ''
        self.avatar_url = ''
        self.token = ''

    def start_authentication(self):
        def run_auth():
            try:
                self.session = OAuth2Session(self.client_id, redirect_uri=self.redirect_uri, scope=self.scope)
                authorization_url, state = self.session.authorization_url(AUTHORIZATION_BASE_URL)
                webbrowser.open(authorization_url)
                print(f"URL d'autorisation OAuth : {authorization_url}")

                # Start a local server to receive the callback
                self.server = OAuthCallbackServer(('localhost', 8000), OAuthCallbackHandler)
                self.server_thread = threading.Thread(target=self.server.serve_forever)
                self.server_thread.daemon = True
                self.server_thread.start()
                print("Serveur OAuth démarré sur http://localhost:8000/callback")

                # Wait until the auth code is received
                while not self.server.auth_code:
                    pass
                print(f"Code d'autorisation reçu : {self.server.auth_code}")

                # Shutdown the server
                self.server.shutdown()
                self.server_thread.join()
                print("Échange du code d'autorisation contre le token d'accès.")

                # Fetch the access token without passing the scope
                token = self.session.fetch_token(
                    TOKEN_URL,
                    client_secret=self.client_secret,
                    code=self.server.auth_code,
                    include_client_id=True
                )

                self.token = token.get('access_token', '')
                self.get_user_info()
                # Emit signal to indicate success
                self.auth_completed.emit(True, self.username, self.avatar_url)
            except Exception as e:
                print(f"Exception lors de l'authentification OAuth : {str(e)}")
                # Emit signal to indicate failure
                self.auth_completed.emit(False, str(e), '')
        threading.Thread(target=run_auth).start()

    def get_user_info(self):
        if self.token:
            headers = {'Authorization': f'token {self.token}'}
            response = requests.get('https://api.github.com/user', headers=headers)
            if response.status_code == 200:
                user_data = response.json()
                self.username = user_data.get('login', '')
                self.avatar_url = user_data.get('avatar_url', '')
            else:
                self.username = ''
                self.avatar_url = ''
        else:
            self.username = ''
            self.avatar_url = ''

    def disconnect(self):
        self.session = None
        self.username = ''
        self.avatar_url = ''
        self.token = ''


class VersionManagerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.project_dir = ''
        self.archive_dir = ''
        self.github_oauth = GitHubOAuth()
        self.github_oauth.auth_completed.connect(self.on_auth_completed)
        self.network_manager = QNetworkAccessManager()
        self.init_ui()

    def init_ui(self):
        # Charger la police personnalisée ou utiliser la police système par défaut
        if os.path.exists('Roboto-Regular.ttf'):
            QFontDatabase.addApplicationFont("Roboto-Regular.ttf")
            font_family = 'Roboto'
        else:
            print("Avertissement : Le fichier de police 'Roboto-Regular.ttf' est introuvable. Utilisation de la police par défaut.")
            font_family = self.font().family()

        # Set window flags for borderless window with rounded corners
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle('GIT YOUR STUFF')
        self.setGeometry(200, 200, 800, 600)

        # Create a central widget
        self.central_widget = QWidget()
        self.central_widget.setStyleSheet("background: transparent;")
        self.setCentralWidget(self.central_widget)

        # Create the star field in the background
        self.star_field = StarField(self.central_widget)
        self.star_field.setGeometry(0, 0, self.width(), self.height())
        self.star_field.lower()  # Send to background

        # Create a main layout
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setAlignment(Qt.AlignTop)
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        self.main_layout.setSpacing(10)

        # Add a close button
        self.close_button = QPushButton()
        self.close_button.setFixedSize(30, 30)
        # Utiliser une icône standard pour le bouton de fermeture
        close_icon = self.style().standardIcon(QStyle.SP_TitleBarCloseButton)
        self.close_button.setIcon(close_icon)
        self.close_button.setIconSize(QSize(24, 24))
        self.close_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
            }
            QPushButton:hover {
                background-color: rgba(255, 0, 0, 150);
                border-radius: 15px;
            }
        """)
        self.close_button.setCursor(Qt.PointingHandCursor)
        self.close_button.clicked.connect(self.close)

        # Create a layout for the top bar (user info and close button)
        top_bar_layout = QHBoxLayout()
        top_bar_layout.setContentsMargins(0, 0, 0, 0)
        top_bar_layout.setSpacing(10)

        # Avatar and username
        self.avatar_label = QLabel()
        self.avatar_label.setFixedSize(64, 64)
        self.avatar_label.hide()  # Hide initially
        self.username_label = QLabel()
        self.username_label.setStyleSheet(f"""
            QLabel {{
                color: white;
                font-size: 18px;
                font-family: '{font_family}', sans-serif;
            }}
        """)
        self.username_label.hide()  # Hide initially

        user_info_layout = QHBoxLayout()
        user_info_layout.setAlignment(Qt.AlignLeft)
        user_info_layout.addWidget(self.avatar_label)
        user_info_layout.addWidget(self.username_label)
        user_info_widget = QWidget()
        user_info_widget.setLayout(user_info_layout)

        top_bar_layout.addWidget(user_info_widget)
        top_bar_layout.addStretch()
        top_bar_layout.addWidget(self.close_button)

        self.main_layout.addLayout(top_bar_layout)

        # Add the application name with animation
        self.app_name_label = AnimatedLabel('GIT YOUR STUFF')
        self.app_name_label.setAlignment(Qt.AlignCenter)
        self.main_layout.addWidget(self.app_name_label)

        # Add a color animation to the application name
        self.color_animation = QPropertyAnimation(self.app_name_label, b"color")
        self.color_animation.setDuration(2000)  # Duration in milliseconds
        self.color_animation.setStartValue(QColor('white'))
        self.color_animation.setKeyValueAt(0.5, QColor('cyan'))
        self.color_animation.setEndValue(QColor('white'))
        self.color_animation.setEasingCurve(QEasingCurve.Linear)
        self.color_animation.setLoopCount(-1)  # Infinite loop
        self.color_animation.start()

        # Add a notification area
        self.notification = NotificationArea()
        self.main_layout.addWidget(self.notification)

        # Create a layout for the buttons
        self.button_layout = QVBoxLayout()
        self.button_layout.setAlignment(Qt.AlignCenter)
        self.button_layout.setSpacing(10)

        # Button to connect/disconnect to GitHub
        self.github_btn = GlowingButton('Connecter à GitHub')
        self.github_btn.clicked.connect(self.github_auth)
        self.button_layout.addWidget(self.github_btn)

        # Button to select the project folder
        self.select_project_btn = GlowingButton('Sélectionner le dossier du projet')
        self.select_project_btn.clicked.connect(self.select_project_folder)
        self.button_layout.addWidget(self.select_project_btn)

        # Button to select the archive folder
        self.select_archive_btn = GlowingButton('Sélectionner le dossier d\'archive')
        self.select_archive_btn.clicked.connect(self.select_archive_folder)
        self.select_archive_btn.setEnabled(False)
        self.button_layout.addWidget(self.select_archive_btn)

        # Button to create a development branch
        self.create_branch_btn = GlowingButton('Créer une branche de développement')
        self.create_branch_btn.clicked.connect(self.create_development_branch)
        self.create_branch_btn.hide()  # Hide initially
        self.button_layout.addWidget(self.create_branch_btn)

        # Button to synchronize with Visual Studio
        self.sync_vs_btn = GlowingButton('Synchroniser avec Visual Studio')
        self.sync_vs_btn.clicked.connect(self.sync_with_visual_studio)
        self.sync_vs_btn.hide()  # Hide initially
        self.button_layout.addWidget(self.sync_vs_btn)

        # Add the buttons to the main layout
        self.main_layout.addLayout(self.button_layout)

        # Add the "Duperopope" signature
        self.signature_label = QLabel('Duperopope')
        self.signature_label.setAlignment(Qt.AlignRight | Qt.AlignBottom)
        self.signature_label.setStyleSheet("""
            QLabel {
                color: #555555;
                font-size: 12px;
                font-style: italic;
            }
        """)
        # Adjust margins to push the signature to the bottom
        self.main_layout.addStretch()
        self.main_layout.addWidget(self.signature_label)

        # Variable for window dragging
        self.old_pos = self.pos()

    # Ajout de la méthode manquante on_auth_completed
    def on_auth_completed(self, success, username_or_error, avatar_url):
        if success:
            self.github_btn.setText('Changer d\'utilisateur')
            self.show_notification(f'Connecté à GitHub en tant que {username_or_error}.')
            self.github_oauth.username = username_or_error
            self.github_oauth.avatar_url = avatar_url
            # Load and display the avatar using QNetworkAccessManager
            if avatar_url:
                self.download_avatar(avatar_url)
            else:
                self.avatar_label.hide()

            self.username_label.setText(username_or_error)
            self.username_label.show()
        else:
            self.show_notification(f'Erreur lors de l\'authentification GitHub : {username_or_error}')

    def download_avatar(self, avatar_url):
        request = QNetworkRequest(QUrl(avatar_url))
        self.avatar_reply = self.network_manager.get(request)
        self.avatar_reply.finished.connect(self.handle_avatar_download)

    def handle_avatar_download(self):
        err = self.avatar_reply.error()
        if err == QNetworkReply.NoError:
            data = self.avatar_reply.readAll()
            pixmap = QPixmap()
            pixmap.loadFromData(data)
            pixmap = pixmap.scaled(self.avatar_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.avatar_label.setPixmap(pixmap)
            self.avatar_label.setToolTip(self.github_oauth.username)  # Show username on hover
            self.avatar_label.show()
        else:
            self.show_notification('Impossible de charger l\'image de l\'avatar.')
        self.avatar_reply.deleteLater()

    # Les autres méthodes de VersionManagerApp restent inchangées

    def resizeEvent(self, event):
        # Resize the star field widget when the window is resized
        self.star_field.setGeometry(0, 0, self.width(), self.height())
        super().resizeEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()
        # Draw a semi-transparent background with rounded corners
        painter.setBrush(QColor(0, 0, 0, 200))  # Semi-transparent black
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(rect, 15, 15)
        super().paintEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.old_pos = event.globalPos()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            delta = event.globalPos() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPos()

    def show_notification(self, message):
        self.notification.show_message(message)

    def select_project_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Sélectionner le dossier du projet")
        if folder:
            self.project_dir = folder
            self.select_archive_btn.setEnabled(True)
            self.create_branch_btn.show()
            self.sync_vs_btn.show()
            self.show_notification(f'Dossier du projet sélectionné : {folder}')
        else:
            self.show_notification('Aucun dossier sélectionné.')

    def select_archive_folder(self):
        if not self.project_dir:
            self.show_notification('Veuillez sélectionner un dossier de projet d\'abord.')
            return
        folder = QFileDialog.getExistingDirectory(self, "Sélectionner le dossier d'archive")
        if folder:
            self.archive_dir = folder
            self.show_notification(f'Dossier d\'archive sélectionné : {folder}')
        else:
            self.show_notification('Aucun dossier sélectionné.')

    def github_auth(self):
        if self.github_oauth.token:
            # If already authenticated, provide option to change user
            self.github_oauth.disconnect()
            self.github_btn.setText('Connecter à GitHub')
            self.avatar_label.hide()
            self.username_label.hide()
            self.show_notification('Déconnecté de GitHub.')
            return
        else:
            # Start OAuth authentication
            self.show_notification('Ouverture de GitHub OAuth... Veuillez autoriser l\'application.')
            self.github_oauth.start_authentication()

    def create_development_branch(self):
        if not self.project_dir:
            self.show_notification('Veuillez sélectionner un dossier de projet d\'abord.')
            return
        import subprocess
        branch_name = "development"
        try:
            subprocess.check_call(['git', 'init'], cwd=self.project_dir)  # Initialize git if not already a repo
            subprocess.check_call(['git', 'checkout', '-b', branch_name], cwd=self.project_dir)
            self.show_notification(f'Branche "{branch_name}" créée et activée.')
        except subprocess.CalledProcessError as e:
            self.show_notification(f'Erreur lors de la création de la branche : {str(e)}')

    def sync_with_visual_studio(self):
        if not self.project_dir:
            self.show_notification('Veuillez sélectionner un dossier de projet d\'abord.')
            return
        # Attempt to open the project in Visual Studio
        # This assumes that Visual Studio is installed and associated with the project files
        try:
            os.startfile(self.project_dir)  # Works on Windows
            self.show_notification('Projet ouvert dans Visual Studio.')
        except Exception as e:
            self.show_notification(f'Erreur lors de l\'ouverture de Visual Studio : {str(e)}')

    def save_version(self):
        if not self.project_dir:
            self.show_notification('Veuillez sélectionner un dossier de projet.')
            return
        if not self.archive_dir:
            self.show_notification('Veuillez sélectionner un dossier d\'archive.')
            return
        try:
            self.concat_cs_files_to_txt()
            self.show_notification('Nouvelle version sauvegardée avec succès.')
        except Exception as e:
            self.show_notification(f'Erreur lors de la sauvegarde de la version : {str(e)}')

    def concat_cs_files_to_txt(self):
        current_datetime = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        versions_dir = os.path.join(self.archive_dir, "versions")
        os.makedirs(versions_dir, exist_ok=True)
        version = self.get_next_version(versions_dir)

        version_folder = os.path.join(versions_dir, f"version_{version}_{current_datetime}")
        os.makedirs(version_folder, exist_ok=True)

        source_copy_folder = os.path.join(version_folder, "Source")
        os.makedirs(source_copy_folder, exist_ok=True)

        output_file = os.path.join(version_folder, f"concat_files_v{version}_{current_datetime}.txt")

        with open(output_file, 'w', encoding='utf-8') as outfile:
            outfile.write(f"// Version: {version}\n")
            outfile.write(f"// Date: {current_datetime}\n")
            outfile.write("=" * 50 + "\n")

        for foldername, subfolders, filenames in os.walk(self.project_dir):
            # Skip the versions folder
            if 'versions' in foldername:
                continue
            for filename in filenames:
                if filename.endswith(".cs"):
                    file_path = os.path.join(foldername, filename)
                    with open(file_path, 'r', encoding='utf-8') as infile:
                        with open(output_file, 'a', encoding='utf-8') as outfile:
                            outfile.write(f"\n// File: {filename}\n")
                            outfile.write(infile.read())
                            outfile.write("\n" + "=" * 50 + "\n")

                    destination_file = os.path.join(source_copy_folder, f"{filename}.txt")
                    shutil.copy(file_path, destination_file)

        zip_file_name = os.path.join(version_folder, f"backup_project_v{version}_{current_datetime}.zip")
        with zipfile.ZipFile(zip_file_name, 'w', zipfile.ZIP_DEFLATED) as backup_zip:
            for foldername, subfolders, filenames in os.walk(self.project_dir):
                if 'versions' in foldername:
                    continue
                for filename in filenames:
                    if not filename.endswith('.zip'):
                        file_path = os.path.join(foldername, filename)
                        arcname = os.path.relpath(file_path, self.project_dir)
                        backup_zip.write(file_path, arcname)

    def get_next_version(self, versions_dir):
        version_folders = [folder for folder in os.listdir(versions_dir) if folder.startswith('version_')]
        versions = []
        for folder in version_folders:
            try:
                version_str = folder.split('_')[1]
                versions.append(float(version_str))
            except (IndexError, ValueError):
                continue

        if not versions:
            return "0.01"
        return f"{max(versions) + 0.01:.2f}"


def main():
    # Vérifiez si CLIENT_ID et CLIENT_SECRET ont été définis
    if CLIENT_ID == 'YOUR_CLIENT_ID' or CLIENT_SECRET == 'YOUR_CLIENT_SECRET':
        print("Veuillez définir votre Client ID et Client Secret GitHub OAuth App dans le script.")
        sys.exit(1)

    app = QApplication(sys.argv)
    window = VersionManagerApp()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
