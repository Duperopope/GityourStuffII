import sys
import os
import shutil
import zipfile
import json
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QLabel, QComboBox, 
    QMessageBox, QFileDialog, QWidget, QVBoxLayout, QHBoxLayout, 
    QTabWidget, QGroupBox, QGridLayout, QFrame, QInputDialog
)
from PyQt5.QtCore import Qt, QTimer, QPoint, QRect
from PyQt5.QtGui import QPixmap, QPainterPath, QPainter, QColor, QFont, QIcon
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
load_dotenv()

# Charger les textes de localisation
def load_localization():
    try:
        with open('localization_en.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        QMessageBox.critical(None, 'Erreur', 'Fichier de localisation manquant.')
        sys.exit(1)

loc = load_localization()

# Charger les variables d'environnement
CLIENT_ID = os.getenv('GITHUB_CLIENT_ID')
CLIENT_SECRET = os.getenv('GITHUB_CLIENT_SECRET')
REDIRECT_URI = 'http://localhost:5000/callback'

# Ajouter des messages de débogage
if not CLIENT_ID or not CLIENT_SECRET:
    raise EnvironmentError("Les variables d'environnement GITHUB_CLIENT_ID et GITHUB_CLIENT_SECRET doivent être définies.")
else:
    print(f"GITHUB_CLIENT_ID: {CLIENT_ID}")
    print(f"GITHUB_CLIENT_SECRET: {CLIENT_SECRET}")

# Flask app to handle OAuth callback
app = Flask(__name__)

# Variables globales pour stocker le code d'authentification
auth_code = None
auth_token = None

@app.route("/callback")
def github_callback():
    global auth_code
    auth_code = request.args.get("code")
    if auth_code:
        return "Authentication successful! You can close this window."
    else:
        return "No code received", 400

def run_flask_app():
    app.run(port=5000)

def open_github_auth():
    auth_url = f"https://github.com/login/oauth/authorize?client_id={CLIENT_ID}&scope=repo&redirect_uri={REDIRECT_URI}"
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
        token_response = requests.post(token_url, data=token_data, headers=headers)
        token_response.raise_for_status()
        return token_response.json().get('access_token'), None
    except requests.RequestException as e:
        return None, str(e)

def get_github_user_info(access_token):
    user_url = "https://api.github.com/user"
    headers = {'Authorization': f'token {access_token}'}
    try:
        response = requests.get(user_url, headers=headers)
        response.raise_for_status()
        return response.json(), None
    except requests.RequestException as e:
        return None, str(e)

def get_github_last_push(access_token):
    repos_url = "https://api.github.com/user/repos"
    headers = {'Authorization': f'token {access_token}'}
    try:
        response = requests.get(repos_url, headers=headers)
        response.raise_for_status()
        return response.json(), None
    except requests.RequestException as e:
        return None, str(e)

class Star:
    def __init__(self, x, y, size, speed, is_shooting=False, shooting_length=0):
        self.x = x
        self.y = y
        self.size = size
        self.speed = speed
        self.is_shooting = is_shooting
        self.shooting_length = shooting_length  # Distance restante pour la trajectoire de l'étoile filante

class Starfield(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.stars = []
        self.num_stars = 200  # Augmenté pour plus d'étoiles
        self.init_stars()
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_animation)
        self.timer.start(30)  # Met à jour toutes les 30 ms pour plus de fluidité

    def init_stars(self):
        for _ in range(self.num_stars):
            x = random.randint(0, self.width() if self.width() > 0 else 800)
            y = random.randint(0, self.height() if self.height() > 0 else 600)
            size = random.randint(1, 3)
            speed = random.uniform(0.5, 2.5)
            self.stars.append(Star(x, y, size, speed))

    def resizeEvent(self, event):
        # Reinitialiser les étoiles lors du redimensionnement
        self.stars = []
        self.init_stars()
        super().resizeEvent(event)

    def update_animation(self):
        # Déplacer les étoiles
        for star in self.stars:
            if not star.is_shooting:
                star.y += star.speed
                if star.y > self.height():
                    star.y = 0
                    star.x = random.randint(0, self.width())
                    # Probabilité de transformer l'étoile en étoile filante
                    if random.random() < 0.03:  # 3% de chance à chaque mise à jour
                        star.is_shooting = True
                        star.shooting_length = random.randint(50, 200)
            else:
                # Déplacer l'étoile filante en diagonale
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
        painter.fillRect(self.rect(), QColor(0, 0, 0, 200))  # Fond noir légèrement transparent

        for star in self.stars:
            painter.setPen(QColor(255, 255, 255))
            if not star.is_shooting:
                painter.drawPoint(int(star.x), int(star.y))
            else:
                # Dessiner une ligne pour représenter l'étoile filante
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
                border-radius: 24px;
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
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(10)
        self.setLayout(layout)

        # Titre
        self.title = QLabel(loc["app_title"])
        self.title.setStyleSheet("color: white;")
        font = QFont()
        font.setPointSize(14)
        font.setBold(True)
        self.title.setFont(font)
        layout.addWidget(self.title)

        layout.addStretch()

        # Bouton Minimiser
        self.min_btn = QPushButton('-')
        self.min_btn.setFixedSize(30, 30)
        self.min_btn.setCursor(Qt.PointingHandCursor)
        self.min_btn.clicked.connect(self.minimize)
        # Ajouter une ombre portée
        shadow_min = QGraphicsDropShadowEffect()
        shadow_min.setBlurRadius(5)
        shadow_min.setXOffset(0)
        shadow_min.setYOffset(2)
        shadow_min.setColor(QColor(0, 0, 0, 160))
        self.min_btn.setGraphicsEffect(shadow_min)
        layout.addWidget(self.min_btn)

        # Bouton Fermer
        self.close_btn = QPushButton('X')
        self.close_btn.setFixedSize(30, 30)
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.clicked.connect(self.close)
        # Ajouter une ombre portée
        shadow_close = QGraphicsDropShadowEffect()
        shadow_close.setBlurRadius(5)
        shadow_close.setXOffset(0)
        shadow_close.setYOffset(2)
        shadow_close.setColor(QColor(0, 0, 0, 160))
        self.close_btn.setGraphicsEffect(shadow_close)
        layout.addWidget(self.close_btn)

    def minimize(self):
        self.parent.showMinimized()

    def close(self):
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
        self.init_ui()

    def init_ui(self):
        # Rendre la fenêtre frameless avec bords arrondis
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground)

        # Configuration de la fenêtre
        self.setWindowTitle(loc["app_title"])
        self.setGeometry(200, 200, 900, 700)

        # Layout principal
        self.main_widget = QWidget()
        self.setCentralWidget(self.main_widget)
        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(15, 15, 15, 15)
        self.main_widget.setLayout(self.main_layout)

        # Ajouter la barre de titre personnalisée
        self.title_bar = TitleBar(self)
        self.main_layout.addWidget(self.title_bar)

        # Starfield en arrière-plan
        self.starfield = Starfield(self)
        self.starfield.setStyleSheet("background-color: transparent;")
        self.starfield.setGeometry(0, 40, self.width(), self.height() - 55)
        self.starfield.show()

        # Overlay semi-transparent pour l'effet "verre mouillé"
        self.overlay_widget = QFrame(self)
        self.overlay_widget.setStyleSheet("""
            QFrame {
                background-color: rgba(255, 255, 255, 100);  /* Semi-transparent */
                border-radius: 15px;
            }
        """)
        # Positionnement centré avec des bords arrondis
        overlay_width = 700
        overlay_height = 550
        self.overlay_widget.setGeometry(
            (self.width() - overlay_width) // 2,
            (self.height() - overlay_height) // 2,
            overlay_width,
            overlay_height
        )
        self.overlay_widget.setAttribute(Qt.WA_TranslucentBackground, False)

        # Appliquer une ombre portée à l'overlay
        shadow_overlay = QGraphicsDropShadowEffect()
        shadow_overlay.setBlurRadius(15)
        shadow_overlay.setXOffset(0)
        shadow_overlay.setYOffset(0)
        shadow_overlay.setColor(QColor(0, 0, 0, 160))
        self.overlay_widget.setGraphicsEffect(shadow_overlay)

        # Layout pour l'overlay
        self.overlay_layout = QVBoxLayout()
        self.overlay_layout.setContentsMargins(20, 20, 20, 20)
        self.overlay_widget.setLayout(self.overlay_layout)

        # Ajouter un titre dans l'overlay
        self.title_label = QLabel(loc["title_label"])
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet("color: #1b2a38; font-size: 22px;")
        self.overlay_layout.addWidget(self.title_label)

        # Créer des onglets
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
                /* Omitting box-shadow as QSS ne le supporte pas */
            }
        """)
        self.overlay_layout.addWidget(self.tabs)

        # Onglet Gestion des Versions
        self.versions_tab = QWidget()
        self.tabs.addTab(self.versions_tab, loc["tab_versions"])
        self.init_versions_tab()

        # Onglet GitHub
        self.github_tab = QWidget()
        self.tabs.addTab(self.github_tab, loc["tab_github"])
        self.init_github_tab()

        # Notification Area en bas de la fenêtre
        self.notification_label = QLabel("")
        self.notification_label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                background-color: rgba(0, 0, 0, 150);
                padding: 10px;
                border-radius: 5px;
            }
        """)
        self.notification_label.setAlignment(Qt.AlignCenter)
        self.notification_label.hide()  # Caché par défaut
        self.main_layout.addWidget(self.notification_label)

    def resizeEvent(self, event):
        overlay_width = 700
        overlay_height = 550
        self.overlay_widget.setGeometry(
            (self.width() - overlay_width) // 2,
            (self.height() - overlay_height) // 2,
            overlay_width,
            overlay_height
        )
        self.starfield.setGeometry(0, 40, self.width(), self.height() - 55)
        super().resizeEvent(event)

    def init_versions_tab(self):
        layout = QVBoxLayout()
        self.versions_tab.setLayout(layout)

        # Boutons de gestion des versions avec un layout en grille
        grid = QGridLayout()
        grid.setSpacing(20)

        # Styliser les boutons selon le modèle fourni
        button_style = """
            QPushButton {
                background-color: #FFFFFF;
                color: #3c4043;
                border-radius: 24px;
                padding: 2px 24px;
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

        # Bouton Sauvegarder la Version
        self.save_version_btn = QPushButton(loc["button_save_version"])
        self.save_version_btn.setStyleSheet(button_style)
        self.save_version_btn.clicked.connect(self.sauvegarder_version)
        grid.addWidget(self.save_version_btn, 0, 0)
        self.add_shadow(self.save_version_btn)

        # Bouton Restaurer la Version
        self.restore_version_btn = QPushButton(loc["button_restore_version"])
        self.restore_version_btn.setStyleSheet(button_style)
        self.restore_version_btn.clicked.connect(self.restaurer_version)
        grid.addWidget(self.restore_version_btn, 0, 1)
        self.add_shadow(self.restore_version_btn)

        # Bouton Archiver la Version
        self.archive_version_btn = QPushButton(loc["button_archive_version"])
        self.archive_version_btn.setStyleSheet(button_style)
        self.archive_version_btn.clicked.connect(self.archiver_version)
        grid.addWidget(self.archive_version_btn, 1, 0)
        self.add_shadow(self.archive_version_btn)

        # Bouton Extraire la Version
        self.extract_version_btn = QPushButton(loc["button_extract_version"])
        self.extract_version_btn.setStyleSheet(button_style)
        self.extract_version_btn.clicked.connect(self.extraire_version)
        grid.addWidget(self.extract_version_btn, 1, 1)
        self.add_shadow(self.extract_version_btn)

        layout.addLayout(grid)

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

        # Boutons d'authentification GitHub stylisés
        button_style = """
            QPushButton {
                background-color: #FFFFFF;
                color: #3c4043;
                border-radius: 24px;
                padding: 2px 24px;
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

        # Bouton Connecter à GitHub
        self.github_btn = QPushButton(loc["button_connect_github"])
        self.github_btn.setStyleSheet(button_style)
        self.github_btn.clicked.connect(self.se_connecter_github)
        layout.addWidget(self.github_btn)
        self.add_shadow(self.github_btn)

        # Bouton Déconnecter
        self.deconnexion_btn = QPushButton(loc["button_disconnect_github"])
        self.deconnexion_btn.setStyleSheet(button_style)
        self.deconnexion_btn.clicked.connect(self.deconnecter_github)
        self.deconnexion_btn.hide()
        layout.addWidget(self.deconnexion_btn)
        self.add_shadow(self.deconnexion_btn)

        # Label pour les informations GitHub
        self.github_info_label = QLabel("")
        self.github_info_label.setAlignment(Qt.AlignCenter)
        self.github_info_label.setStyleSheet("color: #1b2a38; font-size: 16px;")
        layout.addWidget(self.github_info_label)

    def se_connecter_github(self):
        open_github_auth()
        self.check_authentication()

    def check_authentication(self):
        global auth_token, auth_code
        if auth_code:
            access_token, error = get_access_token(auth_code)
            if access_token:
                user_info, error = get_github_user_info(access_token)
                if user_info:
                    repos, error = get_github_last_push(access_token)
                    self.afficher_github_info(user_info, repos)
                    auth_token = access_token
                else:
                    self.show_notification(loc["notification_error"].format(error=error))
            else:
                self.show_notification(loc["notification_error"].format(error=error))
        else:
            # Attendre et vérifier de nouveau après 1 seconde
            QTimer.singleShot(1000, self.check_authentication)

    def afficher_github_info(self, user_info, repos):
        if not user_info:
            return
        username = user_info.get('login', 'N/A')
        fullname = user_info.get('name', 'N/A')
        self.github_info_label.setText(loc["github_user"].format(username=username, fullname=fullname))
        self.github_btn.hide()
        self.deconnexion_btn.show()

        # Télécharger l'avatar et l'afficher en rond
        avatar_url = user_info.get('avatar_url', '')
        if avatar_url:
            try:
                response = requests.get(avatar_url)
                response.raise_for_status()
                img_data = BytesIO(response.content)
                pixmap = QPixmap()
                pixmap.loadFromData(img_data.read())
                self.display_rounded_image(pixmap)
            except requests.RequestException as e:
                self.show_notification(loc["notification_error"].format(error=str(e)))

        # Afficher les derniers push
        if repos:
            repos_group = QGroupBox("Derniers Push des Dépôts")
            repos_layout = QVBoxLayout()
            repos_group.setLayout(repos_layout)

            for repo in repos[:5]:
                repo_name = repo.get('name', 'N/A')
                pushed_at = repo.get('pushed_at', 'N/A')
                repo_label = QLabel(loc["github_push"].format(repo_name=repo_name, pushed_at=pushed_at))
                repo_label.setStyleSheet("color: #1b2a38;")
                repos_layout.addWidget(repo_label)

            self.tabs.currentWidget().layout().addWidget(repos_group)
        else:
            self.show_notification(loc["notification_error"].format(error="No repositories found."))

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

        image_label = QLabel(self)
        image_label.setPixmap(rounded_pixmap)
        image_label.setAlignment(Qt.AlignCenter)
        image_label.setStyleSheet("background-color: transparent;")
        self.github_tab.layout().addWidget(image_label)

    def deconnecter_github(self):
        global auth_token, auth_code
        auth_token = None
        auth_code = None
        self.github_info_label.clear()
        self.github_btn.show()
        self.deconnexion_btn.hide()
        self.show_notification("Disconnected from GitHub.")

    # Fonctions de gestion des versions
    def sauvegarder_version(self):
        directory = QFileDialog.getExistingDirectory(self, loc["button_save_version"], os.path.expanduser("~"))
        if directory:
            folder_name = os.path.basename(directory)
            repo_name = folder_name
            # Vérifier si le repo existe déjà
            if self.check_repo_exists(repo_name):
                # Demander à l'utilisateur de choisir un autre nom
                new_repo_name, ok = self.get_repo_name()
                if ok and new_repo_name:
                    repo_name = new_repo_name
                else:
                    self.show_notification("Repository creation cancelled.")
                    return
            # Créer le repository
            success, error = self.create_github_repo(repo_name)
            if success:
                # Initialiser git localement si nécessaire
                self.init_git(directory, repo_name)
                self.show_notification(loc["notification_save_success"])
            else:
                self.show_notification(loc["notification_error"].format(error=error))

    def check_repo_exists(self, repo_name):
        if not auth_token:
            return False
        headers = {'Authorization': f'token {auth_token}'}
        user_info, error = get_github_user_info(auth_token)
        if user_info:
            username = user_info.get('login', '')
            repo_url = f"https://api.github.com/repos/{username}/{repo_name}"
            response = requests.get(repo_url, headers=headers)
            if response.status_code == 200:
                return True
        return False

    def get_repo_name(self):
        repo_name, ok = QInputDialog.getText(self, "Repository Exists", "Enter a new repository name:")
        return repo_name, ok

    def create_github_repo(self, repo_name):
        headers = {'Authorization': f'token {auth_token}'}
        data = {
            "name": repo_name,
            "auto_init": True
        }
        try:
            response = requests.post("https://api.github.com/user/repos", json=data, headers=headers)
            if response.status_code == 201:
                return True, None
            else:
                return False, response.json().get('message', 'Unknown error')
        except requests.RequestException as e:
            return False, str(e)

    def init_git(self, directory, repo_name):
        try:
            # Initialiser git
            subprocess.run(['git', 'init'], cwd=directory, check=True)
            # Ajouter remote
            user_info, error = get_github_user_info(auth_token)
            if user_info:
                username = user_info.get('login', '')
                remote_url = f"https://github.com/{username}/{repo_name}.git"
                subprocess.run(['git', 'remote', 'add', 'origin', remote_url], cwd=directory, check=True)
            # Ajouter tous les fichiers
            subprocess.run(['git', 'add', '.'], cwd=directory, check=True)
            # Commit initial
            commit_message = "Initial commit"  # Vous pouvez personnaliser cela si nécessaire
            subprocess.run(['git', 'commit', '-m', commit_message], cwd=directory, check=True)
            # Pousser vers GitHub
            subprocess.run(['git', 'push', '-u', 'origin', 'master'], cwd=directory, check=True)
        except subprocess.CalledProcessError as e:
            self.show_notification(f"Git error: {str(e)}")

    def restaurer_version(self):
        versions_dir = QFileDialog.getExistingDirectory(self, loc["button_restore_version"], os.path.expanduser("~"))
        if versions_dir:
            versions = [folder for folder in os.listdir(versions_dir) if folder.startswith('version_')]
            if not versions:
                self.show_notification("No versions available for restoration.")
                return

            version, ok = self.select_version(versions, loc["button_restore_version"])
            if ok and version:
                self.restore_version_from_dir(os.path.join(versions_dir, version))
                self.show_notification(loc["notification_restore_success"])

    def archiver_version(self):
        directory = QFileDialog.getExistingDirectory(self, loc["button_archive_version"], os.path.expanduser("~"))
        if directory:
            archive_path, _ = QFileDialog.getSaveFileName(self, "Save Archive", '', 'ZIP Files (*.zip)')
            if archive_path:
                try:
                    with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as backup_zip:
                        for foldername, subfolders, filenames in os.walk(directory):
                            for filename in filenames:
                                file_path = os.path.join(foldername, filename)
                                backup_zip.write(file_path, arcname=os.path.relpath(file_path, directory))
                    self.show_notification(loc["notification_archive_success"])
                except Exception as e:
                    self.show_notification(loc["notification_error"].format(error=str(e)))

    def extraire_version(self):
        zip_file, _ = QFileDialog.getOpenFileName(self, loc["button_extract_version"], '', 'ZIP Files (*.zip)')
        if zip_file:
            extract_folder = QFileDialog.getExistingDirectory(self, "Choose Destination Folder", os.path.expanduser("~"))
            if extract_folder:
                try:
                    with zipfile.ZipFile(zip_file, 'r') as zip_ref:
                        zip_ref.extractall(extract_folder)
                    self.show_notification(loc["notification_extract_success"])
                except zipfile.BadZipFile:
                    self.show_notification("The ZIP file is corrupted or invalid.")
                except Exception as e:
                    self.show_notification(loc["notification_error"].format(error=str(e)))

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
                            self.show_notification(loc["notification_error"].format(error=str(e)))

    def select_version(self, versions, action_name):
        combo = QComboBox(self)
        combo.addItems(versions)

        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(f"{action_name} a Version")
        msg_box.setText("Select a version:")
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
                except Exception as e:
                    self.show_notification(loc["notification_error"].format(error=str(e)))

    def show_notification(self, message):
        self.notification_label.setText(message)
        self.notification_label.show()
        # Masquer après 5 secondes
        QTimer.singleShot(5000, self.notification_label.hide)

# Lancer l'application Flask dans un thread séparé
def run_flask_app():
    app.run(port=5000)

if __name__ == '__main__':
    # Démarrer Flask dans un thread séparé
    flask_thread = threading.Thread(target=run_flask_app)
    flask_thread.daemon = True
    flask_thread.start()

    app_qt = QApplication(sys.argv)
    window = VersionManagerApp()
    window.show()
    sys.exit(app_qt.exec_())
