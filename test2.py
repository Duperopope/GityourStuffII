import sys
import os
import shutil
import zipfile
import json
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QLabel, QComboBox, 
    QMessageBox, QFileDialog, QWidget, QVBoxLayout, QHBoxLayout, 
    QTabWidget, QGroupBox, QGridLayout, QFrame, QInputDialog,
    QTextEdit, QCheckBox, QLineEdit
)
from PyQt5.QtCore import Qt, QTimer, QPoint, pyqtSignal, QObject
from PyQt5.QtGui import QPixmap, QPainterPath, QPainter, QColor, QFont
from PyQt5.QtWidgets import QGraphicsDropShadowEffect
import requests
from io import BytesIO
from flask import Flask, request
import threading
import webbrowser
from dotenv import load_dotenv  # Assurez-vous que python-dotenv est installé
import random
import subprocess

# Charger les variables d'environnement depuis le fichier .env
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path)

# Charger les textes de localisation
def load_localization():
    try:
        with open('localization_en.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print('Error: Localization file missing.')
        sys.exit(1)

loc = load_localization()

# Charger les variables d'environnement
CLIENT_ID = os.getenv('GITHUB_CLIENT_ID')
CLIENT_SECRET = os.getenv('GITHUB_CLIENT_SECRET')
REDIRECT_URI = 'http://localhost:5000/callback'

# Vérification des variables d'environnement
if not CLIENT_ID or not CLIENT_SECRET:
    raise EnvironmentError("Environment variables GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET must be set.")
else:
    print(f"GITHUB_CLIENT_ID: {CLIENT_ID}")
    # Pour des raisons de sécurité, évitez d'imprimer le CLIENT_SECRET en production
    print(f"GITHUB_CLIENT_SECRET: {'*' * len(CLIENT_SECRET)}")

# Flask app to handle OAuth callback
app = Flask(__name__)

# Définition de la classe AuthHandler avec un signal pour communiquer avec PyQt
class AuthHandler(QObject):
    auth_received = pyqtSignal(str)

# Instance globale de AuthHandler
auth_handler = AuthHandler()

@app.route("/callback")
def github_callback():
    code = request.args.get("code")
    if code:
        print(f"Received code: {code}")  # Débogage
        auth_handler.auth_received.emit(code)  # Émission du signal avec le code d'authentification
        return "Authentication successful! You can close this window."
    else:
        return "No code received", 400

def run_flask_app():
    print("Starting Flask app on port 5000...")  # Débogage
    app.run(port=5000)

def open_github_auth():
    # MODIFICATION: Ajout du scope delete_repo
    auth_url = f"https://github.com/login/oauth/authorize?client_id={CLIENT_ID}&scope=repo%20delete_repo&redirect_uri={REDIRECT_URI}"
    print(f"Opening GitHub auth URL: {auth_url}")  # Débogage
    webbrowser.open(auth_url)

def get_access_token(code):
    token_url = 'https://github.com/login/oauth/access_token'
    token_data = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'code': code,
        'redirect_uri': REDIRECT_URI
    }
    headers = {'Accept': 'application/json'}
    try:
        print("Requesting access token...")  # Débogage
        token_response = requests.post(token_url, data=token_data, headers=headers)
        token_response.raise_for_status()
        access_token = token_response.json().get('access_token')
        print(f"Access token received: {access_token}")  # Débogage
        return access_token, None
    except requests.RequestException as e:
        print(f"Error getting access token: {e}")  # Débogage
        return None, str(e)

def get_github_user_info(access_token):
    user_url = "https://api.github.com/user"
    headers = {'Authorization': f'token {access_token}'}
    try:
        print("Fetching GitHub user info...")  # Débogage
        response = requests.get(user_url, headers=headers)
        response.raise_for_status()
        return response.json(), None
    except requests.RequestException as e:
        print(f"Error fetching user info: {e}")  # Débogage
        return None, str(e)

def get_github_last_push(access_token):
    repos_url = "https://api.github.com/user/repos?per_page=100"  # Augmentation du nombre de dépôts récupérés
    headers = {'Authorization': f'token {access_token}'}
    try:
        print("Fetching GitHub repositories...")  # Débogage
        response = requests.get(repos_url, headers=headers)
        response.raise_for_status()
        return response.json(), None
    except requests.RequestException as e:
        print(f"Error fetching repositories: {e}")  # Débogage
        return None, str(e)

class Star:
    def __init__(self, x, y, size, speed, is_shooting=False, shooting_length=0):
        self.x = x
        self.y = y
        self.size = size
        self.speed = speed
        self.is_shooting = is_shooting
        self.shooting_length = shooting_length  # Remaining distance for shooting star trajectory

class Starfield(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.stars = []
        self.num_stars = 200  # Increased for more stars
        self.init_stars()
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_animation)
        self.timer.start(30)  # Update every 30 ms for smoother animation

    def init_stars(self):
        width = self.width() if self.width() > 0 else 800
        height = self.height() if self.height() > 0 else 600
        for _ in range(self.num_stars):
            x = random.randint(0, width)
            y = random.randint(0, height)
            size = random.randint(1, 3)
            speed = random.uniform(0.5, 2.5)
            self.stars.append(Star(x, y, size, speed))

    def resizeEvent(self, event):
        # Reinitialize stars on resize
        self.stars = []
        self.init_stars()
        super().resizeEvent(event)

    def update_animation(self):
        # Move stars
        for star in self.stars:
            if not star.is_shooting:
                star.y += star.speed
                if star.y > self.height():
                    star.y = 0
                    star.x = random.randint(0, self.width())
                    # Probability to become a shooting star
                    if random.random() < 0.03:  # 3% chance each update
                        star.is_shooting = True
                        star.shooting_length = random.randint(50, 200)
            else:
                # Move shooting star diagonally
                star.x += star.speed
                star.y += star.speed
                star.shooting_length -= star.speed * 2
                if star.shooting_length <= 0 or star.x > self.width() or star.y > self.height():
                    star.is_shooting = False
                    star.y = 0
                    star.x = random.randint(0, self.width())
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 200))  # Slightly transparent black background

        for star in self.stars:
            painter.setPen(QColor(255, 255, 255))
            if not star.is_shooting:
                painter.drawPoint(int(star.x), int(star.y))
            else:
                # Draw a line to represent the shooting star
                painter.drawLine(int(star.x), int(star.y),
                                 int(star.x - star.shooting_length * 0.5),
                                 int(star.y - star.shooting_length * 0.5))
        painter.end()

class TitleBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.init_ui()
        self.old_pos = None

    def init_ui(self):
        self.setFixedHeight(40)
        self.setStyleSheet("""
            QWidget {
                background-color: rgba(36, 57, 73, 180);
                border-top-left-radius: 15px;
                border-top-right-radius: 15px;
            }
            QPushButton {
                background-color: #FFFFFF;
                color: #3c4043;
                border-radius: 12px;
                padding: 5px 10px;
                font-size: 14px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: #F6F9FE;
                color: #174ea6;
            }
            QPushButton:pressed {
                background: #F6F9FE;
                color: #174ea6;
            }
            QPushButton:focus {
                outline: none;
                border: 2px solid #4285f4;
            }
        """)
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 2, 10, 0)  # Ajustement des marges (haut: 2 pixels)
        layout.setSpacing(10)
        self.setLayout(layout)

        # Title
        self.title = QLabel(loc.get("app_title", "Git Your Stuff"))
        self.title.setStyleSheet("color: white;")
        font = QFont()
        font.setPointSize(14)
        font.setBold(True)
        self.title.setFont(font)
        layout.addWidget(self.title)

        layout.addStretch()

        # Minimize Button
        self.min_btn = QPushButton('-')
        self.min_btn.setFixedSize(30, 30)
        self.min_btn.setCursor(Qt.PointingHandCursor)
        self.min_btn.clicked.connect(self.minimize)
        self.add_shadow(self.min_btn)
        layout.addWidget(self.min_btn)

        # Close Button
        self.close_btn = QPushButton('X')
        self.close_btn.setFixedSize(30, 30)
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.clicked.connect(self.close_window)
        self.add_shadow(self.close_btn)
        layout.addWidget(self.close_btn)

    def add_shadow(self, widget):
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(5)
        shadow.setXOffset(0)
        shadow.setYOffset(2)
        shadow.setColor(QColor(0, 0, 0, 160))
        widget.setGraphicsEffect(shadow)

    def minimize(self):
        print("Minimize button clicked")  # Débogage
        self.parent.showMinimized()

    def close_window(self):
        print("Close button clicked")  # Débogage
        QApplication.instance().quit()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.old_pos = event.globalPos()

    def mouseMoveEvent(self, event):
        if not self.old_pos:
            return
        delta = QPoint(event.globalPos() - self.old_pos)
        self.parent.move(self.parent.x() + delta.x(), self.parent.y() + delta.y())
        self.old_pos = event.globalPos()

    def mouseReleaseEvent(self, event):
        self.old_pos = None

class VersionManagerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.created_repos = []  # To keep track of created repositories
        self.avatar_label = None  # For avatar display
        self.repos_group = None  # To avoid creating multiple groups
        self.auth_code = None  # Encapsulated auth_code
        self.auth_token = None  # Encapsulated auth_token
        self.init_ui()

        # Connect AuthHandler signal to slot
        auth_handler.auth_received.connect(self.on_auth_received)

    def init_ui(self):
        # Make the window frameless with rounded corners
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground)

        # Window configuration
        self.setWindowTitle(loc.get("app_title", "Git Your Stuff"))
        self.setGeometry(200, 200, 900, 700)

        # Main layout
        self.main_widget = QWidget()
        self.setCentralWidget(self.main_widget)
        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(15, 15, 15, 15)
        self.main_layout.setSpacing(10)
        self.main_widget.setLayout(self.main_layout)

        # Add custom title bar
        self.title_bar = TitleBar(self)
        self.main_layout.addWidget(self.title_bar)

        # Starfield as background
        self.starfield = Starfield(self)
        self.starfield.setStyleSheet("background-color: transparent;")
        self.main_layout.addWidget(self.starfield)

        # Semi-transparent overlay for "wet glass" effect
        self.overlay_widget = QFrame(self)
        self.overlay_widget.setStyleSheet("""
            QFrame {
                background-color: rgba(255, 255, 255, 100);  /* Semi-transparent */
                border-radius: 15px;
            }
        """)
        # Layout for the overlay
        self.overlay_layout = QVBoxLayout()
        self.overlay_layout.setContentsMargins(20, 20, 20, 20)
        self.overlay_widget.setLayout(self.overlay_layout)

        # Add title inside the overlay
        self.title_label = QLabel(loc.get("title_label", "Git Your Stuff"))
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet("color: #1b2a38; font-size: 22px;")
        self.overlay_layout.addWidget(self.title_label)

        # Create tabs
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { /* The tab widget frame */
                border: 1px solid #C2C7CB;
                background: transparent;
            }
            QTabBar::tab {
                background: #FFFFFF;
                color: #3c4043;
                padding: 10px;
                border: 1px solid #C4C4C3;
                border-bottom-color: #C2C7CB; /* same as the pane color */
                margin-right: 2px;
                border-radius: 5px;
            }
            QTabBar::tab:selected, QTabBar::tab:hover {
                background: #F6F9FE;
                color: #174ea6;
                /* Omitting box-shadow as QSS does not support it */
            }
        """)
        self.overlay_layout.addWidget(self.tabs)

        # Version Management Tab
        self.versions_tab = QWidget()
        self.tabs.addTab(self.versions_tab, loc.get("tab_versions", "Version Management"))
        self.init_versions_tab()

        # GitHub Tab
        self.github_tab = QWidget()
        self.tabs.addTab(self.github_tab, loc.get("tab_github", "GitHub"))
        self.init_github_tab()

        # Add the overlay to the main layout
        self.main_layout.addWidget(self.overlay_widget)

        # Internal Console for Logs
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setStyleSheet("""
            QTextEdit {
                background-color: #2e2e2e;
                color: #00FF00;
                font-family: Consolas, monospace;
                font-size: 12px;
                border: none;
                border-radius: 10px;
            }
        """)
        self.console.setFixedHeight(150)
        self.main_layout.addWidget(self.console)

    def init_versions_tab(self):
        layout = QVBoxLayout()
        self.versions_tab.setLayout(layout)

        # Version management buttons with grid layout
        grid = QGridLayout()
        grid.setSpacing(20)

        # Button styles
        button_style = """
            QPushButton {
                background-color: #FFFFFF;
                color: #3c4043;
                border-radius: 24px;
                padding: 10px 24px;
                font-family: "Google Sans", Roboto, Arial, sans-serif;
                font-size: 14px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: #F6F9FE;
                color: #174ea6;
            }
            QPushButton:pressed {
                background: #F6F9FE;
                color: #174ea6;
            }
            QPushButton:focus {
                outline: none;
                border: 2px solid #4285f4;
            }
        """

        # Save Version Button
        self.save_version_btn = QPushButton(loc.get("button_save_version", "Save Version"))
        self.save_version_btn.setStyleSheet(button_style)
        self.save_version_btn.clicked.connect(self.sauvegarder_version)
        grid.addWidget(self.save_version_btn, 0, 0)
        self.add_shadow(self.save_version_btn)

        # Restore Version Button
        self.restore_version_btn = QPushButton(loc.get("button_restore_version", "Restore Version"))
        self.restore_version_btn.setStyleSheet(button_style)
        self.restore_version_btn.clicked.connect(self.restaurer_version)
        grid.addWidget(self.restore_version_btn, 0, 1)
        self.add_shadow(self.restore_version_btn)

        # Archive Version Button
        self.archive_version_btn = QPushButton(loc.get("button_archive_version", "Archive Version"))
        self.archive_version_btn.setStyleSheet(button_style)
        self.archive_version_btn.clicked.connect(self.archiver_version)
        grid.addWidget(self.archive_version_btn, 1, 0)
        self.add_shadow(self.archive_version_btn)

        # Extract Version Button
        self.extract_version_btn = QPushButton(loc.get("button_extract_version", "Extract Version from ZIP"))
        self.extract_version_btn.setStyleSheet(button_style)
        self.extract_version_btn.clicked.connect(self.extraire_version)
        grid.addWidget(self.extract_version_btn, 1, 1)
        self.add_shadow(self.extract_version_btn)

        # **Suppression du bouton "Delete Last Git Repository"**
        # Commenté ou supprimé pour éviter la redondance
        # self.delete_last_git_btn = QPushButton(loc.get("button_delete_last_git", "Delete Last Git Repository"))
        # self.delete_last_git_btn.setStyleSheet(button_style)
        # self.delete_last_git_btn.clicked.connect(self.delete_last_git_repository)
        # grid.addWidget(self.delete_last_git_btn, 2, 0, 1, 2)
        # self.add_shadow(self.delete_last_git_btn)

        layout.addLayout(grid)

        # Ajouter une case à cocher pour définir la visibilité du dépôt
        self.repo_visibility_checkbox = QCheckBox(loc.get("checkbox_private_repo", "Create repository as private"))
        self.repo_visibility_checkbox.setStyleSheet("color: #1b2a38; font-size: 14px;")
        layout.addWidget(self.repo_visibility_checkbox)

        # **Ajout de la case à cocher pour l'auto-génération du nom du dépôt**
        self.auto_generate_checkbox = QCheckBox(loc.get("checkbox_auto_generate_repo", "Auto-generate repository name based on folder"))
        self.auto_generate_checkbox.setChecked(True)  # Par défaut activé
        self.auto_generate_checkbox.setStyleSheet("color: #1b2a38; font-size: 14px;")
        layout.addWidget(self.auto_generate_checkbox)

    def add_shadow(self, widget):
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(10)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 160))
        widget.setGraphicsEffect(shadow)

    def init_github_tab(self):
        layout = QVBoxLayout()
        self.github_tab.setLayout(layout)

        # GitHub authentication buttons
        button_style = """
            QPushButton {
                background-color: #FFFFFF;
                color: #3c4043;
                border-radius: 24px;
                padding: 10px 24px;
                font-family: "Google Sans", Roboto, Arial, sans-serif;
                font-size: 14px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: #F6F9FE;
                color: #174ea6;
            }
            QPushButton:pressed {
                background: #F6F9FE;
                color: #174ea6;
            }
            QPushButton:focus {
                outline: none;
                border: 2px solid #4285f4;
            }
        """

        # Connect to GitHub Button
        self.github_btn = QPushButton(loc.get("button_connect_github", "Connect to GitHub"))
        self.github_btn.setStyleSheet(button_style)
        self.github_btn.clicked.connect(self.se_connecter_github)
        layout.addWidget(self.github_btn)
        self.add_shadow(self.github_btn)

        # Disconnect GitHub Button
        self.deconnexion_btn = QPushButton(loc.get("button_disconnect_github", "Disconnect"))
        self.deconnexion_btn.setStyleSheet(button_style)
        self.deconnexion_btn.clicked.connect(self.deconnecter_github)
        self.deconnexion_btn.hide()
        layout.addWidget(self.deconnexion_btn)
        self.add_shadow(self.deconnexion_btn)

        # GitHub User Info Label
        self.github_info_label = QLabel("")
        self.github_info_label.setAlignment(Qt.AlignCenter)
        self.github_info_label.setStyleSheet("color: #1b2a38; font-size: 16px;")
        layout.addWidget(self.github_info_label)

        # GitHub Repositories Group
        self.repos_group = QGroupBox(loc.get("github_last_pushes", "Latest Pushes"))
        self.repos_layout = QVBoxLayout()
        self.repos_group.setLayout(self.repos_layout)
        self.repos_group.hide()  # Hide initially
        layout.addWidget(self.repos_group)

    def se_connecter_github(self):
        print("Connect to GitHub button clicked")  # Débogage
        open_github_auth()
        self.log("Opened GitHub authentication page.")
        # La vérification de l'authentification est maintenant gérée via des signaux
        # Il n'est donc plus nécessaire d'appeler check_authentication ici

    def on_auth_received(self, code):
        print(f"Authentication code received: {code}")  # Débogage
        self.auth_code = code
        self.check_authentication()

    def check_authentication(self):
        if self.auth_code:
            access_token, error = get_access_token(self.auth_code)
            if access_token:
                user_info, error = get_github_user_info(access_token)
                if user_info:
                    repos, error = get_github_last_push(access_token)
                    self.afficher_github_info(user_info, repos)
                    self.auth_token = access_token
                    self.auth_code = None  # Reset auth_code after use
                    self.log("Successfully authenticated with GitHub.")
                else:
                    self.show_notification(loc.get("notification_error", "An error occurred: {error}").format(error=error))
                    self.log(f"Error fetching user info: {error}")
            else:
                self.show_notification(loc.get("notification_error", "An error occurred: {error}").format(error=error))
                self.log(f"Error fetching access token: {error}")
        else:
            # Wait and check again after 1 second
            QTimer.singleShot(1000, self.check_authentication)

    def afficher_github_info(self, user_info, repos):
        if not user_info:
            return
        username = user_info.get('login', 'N/A')
        fullname = user_info.get('name', 'N/A')
        self.github_info_label.setText(loc.get("github_user", "Username: {username}\nFull Name: {fullname}").format(username=username, fullname=fullname))
        self.github_btn.hide()
        self.deconnexion_btn.show()
        self.log(f"Connected as {username} ({fullname}).")

        # Téléchargement et affichage de l'avatar comme image ronde
        avatar_url = user_info.get('avatar_url', '')
        if avatar_url:
            try:
                response = requests.get(avatar_url)
                response.raise_for_status()
                img_data = BytesIO(response.content)
                pixmap = QPixmap()
                pixmap.loadFromData(img_data.read())
                self.display_rounded_image(pixmap)
                self.log("Avatar downloaded and displayed.")
            except requests.RequestException as e:
                self.show_notification(loc.get("notification_error", "An error occurred: {error}").format(error=str(e)))
                self.log(f"Error downloading avatar: {e}")

        # Afficher les derniers pushs
        if repos:
            # Trier les dépôts par date de dernier push
            sorted_repos = sorted(repos, key=lambda x: x.get('pushed_at', ''), reverse=True)
            latest_repos = sorted_repos[:5]  # Obtenir les 5 derniers pushs

            if not latest_repos:
                self.show_notification(loc.get("notification_error", "An error occurred: {error}").format(error="No repositories found."))
                self.log("No repositories found.")
                return

            # Assurez-vous que repos_group et repos_layout existent
            if not self.repos_group:
                self.repos_group = QGroupBox(loc.get("github_last_pushes", "Latest Pushes"))
                self.repos_layout = QVBoxLayout()
                self.repos_group.setLayout(self.repos_layout)
                self.github_tab.layout().addWidget(self.repos_group)

            # Effacer les entrées précédentes des dépôts pour éviter les duplications
            while self.repos_layout.count():
                child = self.repos_layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()

            self.repos_layout.addWidget(QLabel(loc.get("github_last_pushes_description", "Here are your latest pushes:")))
            for repo in latest_repos:
                repo_name = repo.get('name', 'N/A')
                pushed_at = repo.get('pushed_at', 'N/A')
                if pushed_at != 'N/A':
                    pushed_at_formatted = datetime.strptime(pushed_at, "%Y-%m-%dT%H:%M:%SZ").strftime("%Y-%m-%d %H:%M:%S")
                else:
                    pushed_at_formatted = 'N/A'
                
                # Create a horizontal layout for each repository with a delete button
                repo_widget = QWidget()
                repo_layout = QHBoxLayout()
                repo_widget.setLayout(repo_layout)

                repo_label = QLabel(loc.get("github_push", "{repo_name} - Last push: {pushed_at}").format(repo_name=repo_name, pushed_at=pushed_at_formatted))
                repo_label.setStyleSheet("color: #1b2a38;")
                repo_layout.addWidget(repo_label)

                # Add stretch to push the button to the right
                repo_layout.addStretch()

                # Delete button
                delete_btn = QPushButton("Supprimer")
                delete_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #FF4C4C;
                        color: white;
                        border-radius: 5px;
                        padding: 5px 10px;
                    }
                    QPushButton:hover {
                        background-color: #FF1A1A;
                    }
                    QPushButton:pressed {
                        background-color: #CC0000;
                    }
                """)
                delete_btn.setCursor(Qt.PointingHandCursor)
                delete_btn.clicked.connect(lambda checked, r=repo: self.delete_repository(r))
                repo_layout.addWidget(delete_btn)

                self.repos_layout.addWidget(repo_widget)
                self.log(f"Repo: {repo_name}, Last Push: {pushed_at_formatted}")
            self.repos_group.show()
        else:
            self.show_notification(loc.get("notification_error", "An error occurred: {error}").format(error="No repositories found."))
            self.log("No repositories found.")

    def display_rounded_image(self, pixmap):
        size = 100
        rounded_pixmap = QPixmap(size, size)
        rounded_pixmap.fill(Qt.transparent)

        painter = QPainter(rounded_pixmap)
        path = QPainterPath()
        path.addEllipse(0, 0, size, size)
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, size, size, pixmap)
        painter.end()

        if self.avatar_label:
            self.github_tab.layout().removeWidget(self.avatar_label)
            self.avatar_label.deleteLater()
            self.avatar_label = None  # Assurez-vous de réinitialiser l'attribut

        self.avatar_label = QLabel()
        self.avatar_label.setPixmap(rounded_pixmap)
        self.avatar_label.setAlignment(Qt.AlignCenter)
        self.avatar_label.setStyleSheet("background-color: transparent;")
        self.github_tab.layout().addWidget(self.avatar_label)

    def deconnecter_github(self):
        print("Disconnect from GitHub button clicked")  # Débogage
        self.auth_token = None
        self.auth_code = None
        self.github_info_label.clear()
        self.github_btn.show()
        self.deconnexion_btn.hide()

        # Supprimer l'image d'avatar si elle existe
        if self.avatar_label:
            self.github_tab.layout().removeWidget(self.avatar_label)
            self.avatar_label.deleteLater()
            self.avatar_label = None

        # Masquer le groupe des dépôts
        if self.repos_group:
            # Effacer les éléments du layout pour éviter les duplications
            while self.repos_layout.count():
                child = self.repos_layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()
            self.repos_group.hide()

        self.show_notification("Disconnected from GitHub.")
        self.log("Disconnected from GitHub.")

    # Fonctions de gestion des versions
    def sauvegarder_version(self):
        print("Save Version button clicked")  # Débogage
        directory = QFileDialog.getExistingDirectory(self, loc.get("button_save_version", "Save Version"), os.path.expanduser("~"))
        if directory:
            folder_name = os.path.basename(directory)
            auto_generate = self.auto_generate_checkbox.isChecked()

            if auto_generate:
                repo_name = folder_name
                self.log(f"Auto-generating repository name: {repo_name}")
                # Vérifier si le dépôt existe déjà
                if self.check_repo_exists(repo_name):
                    # Demander à l'utilisateur de saisir un nouveau nom
                    self.show_notification(loc.get("notification_repo_exists", f"The repository name '{repo_name}' already exists. Please enter a new name.").format(repo_name=repo_name))
                    self.log(f"Repository name '{repo_name}' already exists.")
                    repo_name, ok = self.get_repo_name(default_name=repo_name)
                    if not ok or not repo_name:
                        self.show_notification(loc.get("notification_cancelled", "Repository creation cancelled."))
                        self.log("Repository creation cancelled by user.")
                        return
            else:
                # Demander à l'utilisateur de saisir un nom de dépôt
                repo_name, ok = self.get_repo_name()
                if not ok or not repo_name:
                    self.show_notification(loc.get("notification_cancelled", "Repository creation cancelled."))
                    self.log("Repository creation cancelled by user.")
                    return
                # Vérifier si le dépôt existe déjà
                if self.check_repo_exists(repo_name):
                    self.show_notification(loc.get("notification_repo_exists", f"The repository name '{repo_name}' already exists. Please enter a new name.").format(repo_name=repo_name))
                    self.log(f"Repository name '{repo_name}' already exists.")
                    repo_name, ok = self.get_repo_name(default_name=repo_name)
                    if not ok or not repo_name:
                        self.show_notification(loc.get("notification_cancelled", "Repository creation cancelled."))
                        self.log("Repository creation cancelled by user.")
                        return

            # Déterminer la visibilité du dépôt
            is_private = self.repo_visibility_checkbox.isChecked()
            # Créer le dépôt
            success, error = self.create_github_repo(repo_name, is_private)
            if success:
                # Initialiser git localement
                self.init_git(directory, repo_name)
                self.created_repos.append(repo_name)  # Garder une trace des dépôts créés
                self.show_notification(loc.get("notification_save_success", "Version saved successfully."))
                self.log(f"Repository '{repo_name}' created and initialized as {'private' if is_private else 'public'}.")
            else:
                self.show_notification(loc.get("notification_error", "An error occurred: {error}").format(error=error))
                self.log(f"Error creating repository '{repo_name}': {error}")

    def check_repo_exists(self, repo_name):
        if not self.auth_token:
            self.log("Not authenticated. Cannot check repository existence.")
            return False
        headers = {'Authorization': f'token {self.auth_token}'}
        user_info, error = get_github_user_info(self.auth_token)
        if user_info:
            username = user_info.get('login', '')
            repo_url = f"https://api.github.com/repos/{username}/{repo_name}"
            response = requests.get(repo_url, headers=headers)
            if response.status_code == 200:
                self.log(f"Repository '{repo_name}' already exists.")
                return True
        return False

    def get_repo_name(self, default_name=""):
        if default_name:
            prompt = loc.get("dialog_new_repo_default", "Enter a new repository name:")
        else:
            prompt = loc.get("dialog_new_repo", "New Repository Name")
        repo_name, ok = QInputDialog.getText(
            self, 
            loc.get("dialog_new_repo_title", "New Repository Name"),
            prompt,
            QLineEdit.Normal,
            default_name
        )
        return repo_name.strip(), ok

    def create_github_repo(self, repo_name, is_private=False):
        headers = {'Authorization': f'token {self.auth_token}'}
        data = {
            "name": repo_name,
            "auto_init": True,
            "private": is_private  # Définir la visibilité
        }
        try:
            print(f"Creating GitHub repository '{repo_name}'...")  # Débogage
            response = requests.post("https://api.github.com/user/repos", json=data, headers=headers)
            if response.status_code == 201:
                print(f"Repository '{repo_name}' created successfully.")  # Débogage
                return True, None
            else:
                error_message = response.json().get('message', 'Unknown error')
                print(f"Error creating repository '{repo_name}': {error_message}")  # Débogage
                return False, error_message
        except requests.RequestException as e:
            print(f"Error creating repository '{repo_name}': {e}")  # Débogage
            return False, str(e)

    def init_git(self, directory, repo_name):
        try:
            print(f"Initializing git in directory '{directory}'...")  # Débogage
            # Initialiser git
            subprocess.run(['git', 'init'], cwd=directory, check=True)
            # Ajouter le remote
            user_info, error = get_github_user_info(self.auth_token)
            if user_info:
                username = user_info.get('login', '')
                remote_url = f"https://github.com/{username}/{repo_name}.git"
                # MODIFICATION: Vérifier si 'origin' existe déjà
                result = subprocess.run(['git', 'remote', 'get-url', 'origin'], cwd=directory, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if result.returncode == 0:
                    # 'origin' existe, mettre à jour son URL
                    subprocess.run(['git', 'remote', 'set-url', 'origin', remote_url], cwd=directory, check=True)
                    self.log(f"Remote 'origin' URL updated to {remote_url}.")
                    print(f"Remote 'origin' URL updated to {remote_url}.")  # Débogage
                else:
                    # 'origin' n'existe pas, l'ajouter
                    subprocess.run(['git', 'remote', 'add', 'origin', remote_url], cwd=directory, check=True)
                    self.log(f"Remote 'origin' added with URL {remote_url}.")
                    print(f"Remote 'origin' added with URL {remote_url}.")  # Débogage
            # Ajouter tous les fichiers
            subprocess.run(['git', 'add', '.'], cwd=directory, check=True)
            # Commit initial
            commit_message = "Initial commit"
            subprocess.run(['git', 'commit', '-m', commit_message], cwd=directory, check=True)
            # Pousser sur GitHub
            subprocess.run(['git', 'push', '-u', 'origin', 'master'], cwd=directory, check=True)
            self.log(f"Git initialized and pushed to GitHub repository '{repo_name}'.")
            print(f"Git initialized and pushed to GitHub repository '{repo_name}'.")  # Débogage
        except subprocess.CalledProcessError as e:
            self.show_notification(f"Git error: {str(e)}")
            self.log(f"Git error: {str(e)}")
            print(f"Git error: {str(e)}")  # Débogage

    def restaurer_version(self):
        print("Restore Version button clicked")  # Débogage
        versions_dir = QFileDialog.getExistingDirectory(self, loc.get("button_restore_version", "Restore Version"), os.path.expanduser("~"))
        if versions_dir:
            versions = [folder for folder in os.listdir(versions_dir) if folder.startswith('version_')]
            if not versions:
                self.show_notification(loc.get("notification_no_versions", "No versions available for restoration."))
                self.log("No versions available for restoration.")
                return

            version, ok = self.select_version(versions, loc.get("button_restore_version", "Restore Version"))
            if ok and version:
                self.restore_version_from_dir(os.path.join(versions_dir, version))
                self.show_notification(loc.get("notification_restore_success", "Version restored successfully."))
                self.log(f"Version '{version}' restored successfully.")

    def archiver_version(self):
        print("Archive Version button clicked")  # Débogage
        directory = QFileDialog.getExistingDirectory(self, loc.get("button_archive_version", "Archive Version"), os.path.expanduser("~"))
        if directory:
            archive_path, _ = QFileDialog.getSaveFileName(self, loc.get("dialog_save_archive", "Save Archive"), '', 'ZIP Files (*.zip)')
            if archive_path:
                try:
                    print(f"Archiving directory '{directory}' to '{archive_path}'...")  # Débogage
                    with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as backup_zip:
                        for foldername, subfolders, filenames in os.walk(directory):
                            for filename in filenames:
                                file_path = os.path.join(foldername, filename)
                                backup_zip.write(file_path, arcname=os.path.relpath(file_path, directory))
                    self.show_notification(loc.get("notification_archive_success", "Version archived successfully."))
                    self.log(f"Directory '{directory}' archived successfully to '{archive_path}'.")
                    print(f"Directory '{directory}' archived successfully to '{archive_path}'.")  # Débogage
                except Exception as e:
                    self.show_notification(loc.get("notification_error", "An error occurred: {error}").format(error=str(e)))
                    self.log(f"Error archiving directory '{directory}': {e}")
                    print(f"Error archiving directory '{directory}': {e}")  # Débogage

    def extraire_version(self):
        print("Extract Version button clicked")  # Débogage
        zip_file, _ = QFileDialog.getOpenFileName(self, loc.get("button_extract_version", "Extract Version from ZIP"), '', 'ZIP Files (*.zip)')
        if zip_file:
            extract_folder = QFileDialog.getExistingDirectory(self, loc.get("dialog_choose_destination", "Choose Destination Folder"), os.path.expanduser("~"))
            if extract_folder:
                try:
                    print(f"Extracting archive '{zip_file}' to '{extract_folder}'...")  # Débogage
                    with zipfile.ZipFile(zip_file, 'r') as zip_ref:
                        zip_ref.extractall(extract_folder)
                    self.show_notification(loc.get("notification_extract_success", "Version extracted successfully."))
                    self.log(f"Archive '{zip_file}' extracted successfully to '{extract_folder}'.")
                    print(f"Archive '{zip_file}' extracted successfully to '{extract_folder}'.")  # Débogage
                except zipfile.BadZipFile:
                    self.show_notification(loc.get("notification_bad_zip", "The ZIP file is corrupted or invalid."))
                    self.log("Failed to extract archive: Bad ZIP file.")
                    print("Failed to extract archive: Bad ZIP file.")  # Débogage
                except Exception as e:
                    self.show_notification(loc.get("notification_error", "An error occurred: {error}").format(error=str(e)))
                    self.log(f"Error extracting archive '{zip_file}': {e}")
                    print(f"Error extracting archive '{zip_file}': {e}")  # Débogage

    def delete_last_git_repository(self):
        # **Cette méthode peut être supprimée ou laissée si vous souhaitez la conserver**
        print("Delete Last Git Repository button clicked")  # Débogage
        if not self.created_repos:
            self.show_notification(loc.get("notification_no_repos_delete", "No Git repositories to delete."))
            self.log("No Git repositories to delete.")
            return

        last_repo = self.created_repos.pop()
        headers = {'Authorization': f'token {self.auth_token}'}
        user_info, error = get_github_user_info(self.auth_token)
        if user_info:
            username = user_info.get('login', '')
            repo_url = f"https://api.github.com/repos/{username}/{last_repo}"
            try:
                response = requests.delete(repo_url, headers=headers)
                if response.status_code == 204:
                    self.show_notification(loc.get("notification_delete_success", "Last Git repository deleted successfully."))
                    self.log(f"Repository '{last_repo}' deleted successfully.")
                    print(f"Repository '{last_repo}' deleted successfully.")  # Débogage
                else:
                    error_message = response.json().get('message', 'Unknown error')
                    self.show_notification(loc.get("notification_error", "An error occurred: {error}").format(error=error_message))
                    self.log(f"Error deleting repository '{last_repo}': {error_message}")
                    print(f"Error deleting repository '{last_repo}': {error_message}")  # Débogage
            except requests.RequestException as e:
                self.show_notification(loc.get("notification_error", "An error occurred: {error}").format(error=str(e)))
                self.log(f"Error deleting repository '{last_repo}': {e}")
                print(f"Error deleting repository '{last_repo}': {e}")  # Débogage
        else:
            self.show_notification(loc.get("notification_error", "An error occurred: {error}").format(error="Unable to fetch user info."))
            self.log("Error fetching user info while attempting to delete repository.")
            print("Error fetching user info while attempting to delete repository.")  # Débogage

    def concat_cs_files_to_txt(self, directory):
        current_datetime = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output_file = os.path.join(directory, f"concat_files_{current_datetime}.txt")

        with open(output_file, 'w', encoding='utf-8') as outfile:
            for foldername, subfolders, filenames in os.walk(directory):
                for filename in filenames:
                    if filename.endswith(".cs"):
                        file_path = os.path.join(foldername, filename)
                        try:
                            with open(file_path, 'r', encoding='utf-8') as infile:
                                outfile.write(f"\n// File: {filename}\n")
                                outfile.write(infile.read())
                                outfile.write("\n" + "=" * 50 + "\n")
                        except Exception as e:
                            self.show_notification(loc.get("notification_error", "An error occurred: {error}").format(error=str(e)))
                            self.log(f"Error concatenating file '{file_path}': {e}")
                            print(f"Error concatenating file '{file_path}': {e}")  # Débogage

    def select_version(self, versions, action_name):
        combo = QComboBox(self)
        combo.addItems(versions)

        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(f"{action_name} a Version")
        msg_box.setText(loc.get("dialog_select_version", "Select a version:"))
        msg_box.layout().addWidget(combo)
        msg_box.addButton(QMessageBox.Ok)
        msg_box.addButton(QMessageBox.Cancel)

        result = msg_box.exec_()

        if result == QMessageBox.Ok:
            return combo.currentText(), True
        return None, False

    def restore_version_from_dir(self, version_dir):
        project_dir = os.path.abspath(os.path.join(version_dir, '..'))
        for foldername, subfolders, filenames in os.walk(version_dir):
            for filename in filenames:
                source_file = os.path.join(foldername, filename)
                dest_file = os.path.join(project_dir, filename.replace(".txt", ""))
                try:
                    shutil.copy(source_file, dest_file)
                    self.log(f"File '{source_file}' copied to '{dest_file}'.")
                    print(f"File '{source_file}' copied to '{dest_file}'.")  # Débogage
                except Exception as e:
                    self.show_notification(loc.get("notification_error", "An error occurred: {error}").format(error=str(e)))
                    self.log(f"Error restoring file '{source_file}': {e}")
                    print(f"Error restoring file '{source_file}': {e}")  # Débogage

    def show_notification(self, message):
        QMessageBox.information(self, loc.get("notification_title", "Notification"), message)
        self.log(f"Notification: {message}")
        print(f"Notification: {message}")  # Débogage

    def log(self, message):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.console.append(f"[{timestamp}] {message}")
        print(f"[{timestamp}] {message}")  # Débogage

    def delete_repository(self, repo):
        repo_name = repo.get('name', 'N/A')
        try:
            username = self.github_info_label.text().split('\n')[0].split(': ')[1]  # Extract username from label
        except IndexError:
            self.show_notification(loc.get("notification_error", "Failed to extract username."))
            self.log("Failed to extract username from user info label.")
            print("Failed to extract username from user info label.")  # Débogage
            return

        # Confirmation Dialog
        reply = QMessageBox.question(
            self,
            loc.get("confirmation_title", "Confirm Deletion"),
            loc.get("confirmation_delete_repo", f"Are you sure you want to delete the repository '{repo_name}'? This action cannot be undone.").format(repo_name=repo_name),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            headers = {'Authorization': f'token {self.auth_token}'}
            repo_url = f"https://api.github.com/repos/{username}/{repo_name}"
            try:
                print(f"Deleting repository '{repo_name}'...")  # Débogage
                response = requests.delete(repo_url, headers=headers)
                if response.status_code == 204:
                    self.show_notification(loc.get("notification_delete_success", f"Repository '{repo_name}' deleted successfully."))
                    self.log(f"Repository '{repo_name}' deleted successfully.")
                    print(f"Repository '{repo_name}' deleted successfully.")  # Débogage
                    # Refresh the repository list
                    self.refresh_repositories()
                else:
                    error_message = response.json().get('message', 'Unknown error')
                    self.show_notification(loc.get("notification_error", f"An error occurred: {error_message}"))
                    self.log(f"Error deleting repository '{repo_name}': {error_message}")
                    print(f"Error deleting repository '{repo_name}': {error_message}")  # Débogage
            except requests.RequestException as e:
                self.show_notification(loc.get("notification_error", f"An error occurred: {str(e)}"))
                self.log(f"Error deleting repository '{repo_name}': {e}")
                print(f"Error deleting repository '{repo_name}': {e}")  # Débogage
        else:
            self.log(f"Deletion of repository '{repo_name}' cancelled by user.")
            print(f"Deletion of repository '{repo_name}' cancelled by user.")  # Débogage

    def refresh_repositories(self):
        if not self.auth_token:
            self.log("Not authenticated. Cannot refresh repositories.")
            return
        repos, error = get_github_last_push(self.auth_token)
        if repos:
            user_info, error = get_github_user_info(self.auth_token)
            if user_info:
                self.afficher_github_info(user_info, repos)
        else:
            self.show_notification(loc.get("notification_error", f"An error occurred: {error}"))
            self.log(f"Error fetching repositories: {error}")
            print(f"Error fetching repositories: {error}")  # Débogage

# Start Flask app in a separate thread
if __name__ == '__main__':
    try:
        # Start Flask in a daemon thread
        flask_thread = threading.Thread(target=run_flask_app)
        flask_thread.daemon = True
        flask_thread.start()

        app_qt = QApplication(sys.argv)
        window = VersionManagerApp()
        window.show()
        print("Launching PyQt5 application...")  # Débogage
        sys.exit(app_qt.exec_())
    except Exception as e:
        print(f"An unexpected error occurred: {e}")  # Débogage
