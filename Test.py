import sys
import os
import shutil
import zipfile
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QLabel, QComboBox, 
    QMessageBox, QFileDialog, QWidget, QVBoxLayout, QHBoxLayout, 
    QTabWidget, QGroupBox, QGridLayout, QFrame
)
from PyQt5.QtCore import Qt, QTimer, QPoint, QRect
from PyQt5.QtGui import QPixmap, QPainterPath, QPainter, QColor, QFont
import requests
from io import BytesIO
from flask import Flask, request
import threading
import webbrowser
from dotenv import load_dotenv  # Assurez-vous que python-dotenv est installé
import random

# Charger les variables d'environnement depuis le fichier .env
load_dotenv()

# Informations OAuth de l'application GitHub
CLIENT_ID = 'Ov23lie1vc5lKwoGfgwK'
CLIENT_SECRET = 'ce71a9ced8e3464ef9f68b1710d1487bfd224a77'
REDIRECT_URI = 'http://localhost:5000/callback'

# Vérifier que les informations OAuth sont disponibles
if not CLIENT_ID or not CLIENT_SECRET:
    raise EnvironmentError("Les variables d'environnement GITHUB_CLIENT_ID et GITHUB_CLIENT_SECRET doivent être définies.")

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
        return token_response.json().get('access_token')
    except requests.RequestException as e:
        QMessageBox.critical(None, 'Erreur', f'Erreur lors de la récupération du jeton : {e}')
        return None

def get_github_user_info(access_token):
    user_url = "https://api.github.com/user"
    headers = {'Authorization': f'token {access_token}'}
    try:
        response = requests.get(user_url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        QMessageBox.critical(None, 'Erreur', f'Erreur lors de la récupération des informations utilisateur : {e}')
        return {}

def get_github_last_push(access_token):
    repos_url = "https://api.github.com/user/repos"
    headers = {'Authorization': f'token {access_token}'}
    try:
        response = requests.get(repos_url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        QMessageBox.critical(None, 'Erreur', f'Erreur lors de la récupération des dépôts : {e}')
        return []

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
        self.num_stars = 150  # Augmenté pour plus d'étoiles
        self.init_stars()
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_animation)
        self.timer.start(50)  # Met à jour toutes les 50 ms

    def init_stars(self):
        for _ in range(self.num_stars):
            x = random.randint(0, self.width() if self.width() > 0 else 800)
            y = random.randint(0, self.height() if self.height() > 0 else 600)
            size = random.randint(1, 3)
            speed = random.uniform(0.5, 2.0)
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
                    if random.random() < 0.02:  # 2% de chance à chaque mise à jour
                        star.is_shooting = True
                        star.shooting_length = random.randint(50, 150)
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
        painter.fillRect(self.rect(), QColor(0, 0, 0))  # Fond noir

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
        self.setFixedHeight(30)
        self.setStyleSheet("""
            QWidget {
                background-color: #243949;
            }
            QPushButton {
                background-color: #517fa4;
                color: white;
                border: none;
                padding: 5px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #1b2a38;
            }
        """)
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 0, 5, 0)
        self.setLayout(layout)

        # Titre
        self.title = QLabel('Gestion des Versions et Authentification GitHub')
        self.title.setStyleSheet("color: white;")
        font = QFont()
        font.setBold(True)
        self.title.setFont(font)
        layout.addWidget(self.title)

        layout.addStretch()

        # Bouton Minimiser
        self.min_btn = QPushButton('_')
        self.min_btn.setFixedSize(20, 20)
        self.min_btn.clicked.connect(self.minimize)
        layout.addWidget(self.min_btn)

        # Bouton Fermer
        self.close_btn = QPushButton('X')
        self.close_btn.setFixedSize(20, 20)
        self.close_btn.clicked.connect(self.close)
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
        # Rendre la fenêtre frameless
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground)

        # Configuration de la fenêtre
        self.setWindowTitle('Gestion des Versions et Authentification GitHub')
        self.setGeometry(200, 200, 800, 600)

        # Layout principal
        self.main_widget = QWidget()
        self.setCentralWidget(self.main_widget)
        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_widget.setLayout(self.main_layout)

        # Ajouter la barre de titre personnalisée
        self.title_bar = TitleBar(self)
        self.main_layout.addWidget(self.title_bar)

        # Starfield en arrière-plan
        self.starfield = Starfield(self)
        self.starfield.setFixedHeight(self.height() - 30)  # Ajuster la hauteur
        self.starfield.setStyleSheet("background-color: transparent;")
        self.main_layout.addWidget(self.starfield)

        # Superposer les widgets UI sur le starfield
        self.overlay_widget = QFrame(self.starfield)
        self.overlay_widget.setStyleSheet("""
            QFrame {
                background-color: rgba(255, 255, 255, 150);  /* Semi-transparent blanc */
                border-radius: 10px;
            }
        """)
        # Positionnement centré
        overlay_width = 600
        overlay_height = 400
        self.overlay_widget.setGeometry(
            (self.width() - overlay_width) // 2,
            (self.height() - overlay_height) // 2,
            overlay_width,
            overlay_height
        )
        self.overlay_widget.setAttribute(Qt.WA_TransparentForMouseEvents, False)

        # Appliquer un effet de flou pour l'effet "verre mouillé" (Retiré pour éviter le flou des éléments)
        # from PyQt5.QtWidgets import QGraphicsBlurEffect
        # blur = QGraphicsBlurEffect()
        # blur.setBlurRadius(10)
        # self.overlay_widget.setGraphicsEffect(blur)

        # Layout pour l'overlay
        self.overlay_layout = QVBoxLayout()
        self.overlay_layout.setContentsMargins(20, 20, 20, 20)
        self.overlay_widget.setLayout(self.overlay_layout)

        # Ajouter un titre dans l'overlay
        self.title_label = QLabel('Gestion des Versions du Projet & Authentification GitHub', self)
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet("color: #1b2a38; font-size: 18px;")
        self.overlay_layout.addWidget(self.title_label)

        # Créer des onglets
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { /* The tab widget frame */
                border: 1px solid #C2C7CB;
                background: transparent;
            }
            QTabBar::tab {
                background: #517fa4;
                color: white;
                padding: 10px;
                border: 1px solid #C4C4C3;
                border-bottom-color: #C2C7CB; /* same as the pane color */
                margin-right: 2px;
            }
            QTabBar::tab:selected, QTabBar::tab:hover {
                background: #1b2a38;
            }
        """)
        self.overlay_layout.addWidget(self.tabs)

        # Onglet Gestion des Versions
        self.versions_tab = QWidget()
        self.tabs.addTab(self.versions_tab, "Gestion des Versions")
        self.init_versions_tab()

        # Onglet GitHub
        self.github_tab = QWidget()
        self.tabs.addTab(self.github_tab, "GitHub")
        self.init_github_tab()

    def init_versions_tab(self):
        layout = QVBoxLayout()
        self.versions_tab.setLayout(layout)

        # Boutons de gestion des versions avec un layout en grille
        grid = QGridLayout()

        self.sauvegarder_btn = QPushButton('Sauvegarder la version')
        self.sauvegarder_btn.clicked.connect(self.sauvegarder_version)
        grid.addWidget(self.sauvegarder_btn, 0, 0)

        self.restaurer_btn = QPushButton('Restaurer une version')
        self.restaurer_btn.clicked.connect(self.restaurer_version)
        grid.addWidget(self.restaurer_btn, 0, 1)

        self.archiver_btn = QPushButton('Archiver une version')
        self.archiver_btn.clicked.connect(self.archiver_version)
        grid.addWidget(self.archiver_btn, 1, 0)

        self.extraire_btn = QPushButton('Extraire une version d\'un ZIP')
        self.extraire_btn.clicked.connect(self.extraire_version)
        grid.addWidget(self.extraire_btn, 1, 1)

        layout.addLayout(grid)

    def init_github_tab(self):
        layout = QVBoxLayout()
        self.github_tab.setLayout(layout)

        # Boutons d'authentification GitHub
        self.github_btn = QPushButton('Se connecter à GitHub')
        self.github_btn.clicked.connect(self.se_connecter_github)
        layout.addWidget(self.github_btn)

        self.deconnexion_btn = QPushButton('Se déconnecter')
        self.deconnexion_btn.clicked.connect(self.deconnecter_github)
        self.deconnexion_btn.setVisible(False)
        layout.addWidget(self.deconnexion_btn)

        # Label pour les informations GitHub
        self.github_info_label = QLabel(self)
        self.github_info_label.setAlignment(Qt.AlignCenter)
        self.github_info_label.setStyleSheet("color: #1b2a38;")
        layout.addWidget(self.github_info_label)

    def se_connecter_github(self):
        open_github_auth()
        self.check_authentication()

    def check_authentication(self):
        global auth_token
        if auth_code:
            auth_token = get_access_token(auth_code)
            if auth_token:
                user_info = get_github_user_info(auth_token)
                repos = get_github_last_push(auth_token)
                self.afficher_github_info(user_info, repos)
            else:
                QMessageBox.warning(self, 'Erreur', 'Échec de la récupération du jeton d\'accès.')
        else:
            # Attendre et vérifier de nouveau après 1 seconde
            QTimer.singleShot(1000, self.check_authentication)

    def afficher_github_info(self, user_info, repos):
        if not user_info:
            return
        self.github_info_label.setText(
            f"Nom d'utilisateur : {user_info['login']}\nNom complet : {user_info.get('name', 'Non défini')}"
        )
        self.github_btn.setVisible(False)
        self.deconnexion_btn.setVisible(True)

        # Télécharger l'avatar et l'afficher en rond
        avatar_url = user_info['avatar_url']
        try:
            response = requests.get(avatar_url)
            response.raise_for_status()
            img_data = BytesIO(response.content)
            pixmap = QPixmap()
            pixmap.loadFromData(img_data.read())
            self.display_rounded_image(pixmap)
        except requests.RequestException as e:
            QMessageBox.warning(self, 'Erreur', f'Erreur lors du téléchargement de l\'avatar : {e}')

        # Afficher les derniers push
        repos_group = QGroupBox("Derniers Push des Dépôts")
        repos_layout = QVBoxLayout()
        repos_group.setLayout(repos_layout)

        for repo in repos[:5]:
            repo_label = QLabel(f"{repo['name']} - Dernier push : {repo['pushed_at']}")
            repo_label.setStyleSheet("color: #1b2a38;")
            repos_layout.addWidget(repo_label)

        # Utiliser self.tabs directement au lieu de findChild
        if self.tabs and self.tabs.currentWidget():
            current_layout = self.tabs.currentWidget().layout()
            if current_layout:
                current_layout.addWidget(repos_group)
            else:
                QMessageBox.warning(self, 'Erreur', 'Le layout du widget actuel est introuvable.')
        else:
            QMessageBox.warning(self, 'Erreur', 'Le widget actuel des onglets est introuvable.')

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
        self.github_btn.setVisible(True)
        self.deconnexion_btn.setVisible(False)
        QMessageBox.information(self, 'Déconnexion', 'Vous êtes déconnecté de GitHub.')

    # Fonctions de gestion des versions
    def sauvegarder_version(self):
        directory = QFileDialog.getExistingDirectory(self, "Choisir le dossier à sauvegarder", os.path.expanduser("~"))
        if directory:
            self.concat_cs_files_to_txt(directory)
            QMessageBox.information(self, 'Succès', 'Version sauvegardée avec succès.')

    def restaurer_version(self):
        versions_dir = QFileDialog.getExistingDirectory(self, "Sélectionner le répertoire des versions", os.path.expanduser("~"))
        if versions_dir:
            versions = [folder for folder in os.listdir(versions_dir) if folder.startswith('version_')]
            if not versions:
                QMessageBox.warning(self, 'Aucune version', 'Aucune version disponible pour restauration.')
                return

            version, ok = self.select_version(versions, "Restaurer")
            if ok:
                self.restore_version(version)
                QMessageBox.information(self, 'Succès', f'Version {version} restaurée avec succès.')

    def archiver_version(self):
        directory = QFileDialog.getExistingDirectory(self, "Choisir le dossier à archiver", os.path.expanduser("~"))
        if directory:
            archive_path, _ = QFileDialog.getSaveFileName(self, "Enregistrer l'archive", '', 'ZIP Files (*.zip)')
            if archive_path:
                self.create_archive(directory, archive_path)
                QMessageBox.information(self, 'Succès', f'Version archivée avec succès à {archive_path}.')

    def extraire_version(self):
        zip_file, _ = QFileDialog.getOpenFileName(self, 'Choisir un fichier ZIP', '', 'Fichiers ZIP (*.zip)')
        if zip_file:
            extract_folder = QFileDialog.getExistingDirectory(self, "Choisir le dossier de destination", os.path.expanduser("~"))
            if extract_folder:
                self.extract_version(zip_file, extract_folder)
                QMessageBox.information(self, 'Succès', 'Version extraite avec succès.')

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
                            QMessageBox.warning(self, 'Erreur', f'Erreur lors de la lecture de {filename} : {e}')

    def select_version(self, versions, action_name):
        combo = QComboBox(self)
        combo.addItems(versions)

        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(f"{action_name} une version")
        msg_box.setText("Sélectionnez une version :")
        msg_box.layout().addWidget(combo)
        msg_box.addButton(QMessageBox.Ok)
        msg_box.addButton(QMessageBox.Cancel)

        result = msg_box.exec_()

        if result == QMessageBox.Ok:
            return combo.currentText(), True
        return None, False

    def restore_version(self, version):
        script_dir = QFileDialog.getExistingDirectory(self, "Sélectionner le répertoire où restaurer la version", os.path.expanduser("~"))
        if script_dir:
            version_folder = os.path.join(script_dir, version)
            project_dir = os.path.abspath(os.path.join(script_dir, '..'))
            for foldername, subfolders, filenames in os.walk(version_folder):
                for filename in filenames:
                    source_file = os.path.join(foldername, filename)
                    dest_file = os.path.join(project_dir, filename.replace(".txt", ""))
                    try:
                        shutil.copy(source_file, dest_file)
                    except Exception as e:
                        QMessageBox.warning(self, 'Erreur', f'Erreur lors de la copie de {filename} : {e}')

    def create_archive(self, directory, archive_path):
        try:
            with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as backup_zip:
                for foldername, subfolders, filenames in os.walk(directory):
                    for filename in filenames:
                        file_path = os.path.join(foldername, filename)
                        backup_zip.write(file_path, arcname=os.path.relpath(file_path, directory))
        except Exception as e:
            QMessageBox.warning(self, 'Erreur', f'Erreur lors de la création de l\'archive : {e}')

    def extract_version(self, zip_file, extract_folder):
        try:
            with zipfile.ZipFile(zip_file, 'r') as zip_ref:
                zip_ref.extractall(extract_folder)
        except zipfile.BadZipFile:
            QMessageBox.critical(self, 'Erreur', 'Le fichier ZIP est corrompu ou invalide.')
        except Exception as e:
            QMessageBox.warning(self, 'Erreur', f'Erreur lors de l\'extraction : {e}')

# Lancer l'application Flask dans un thread séparé
def run_flask_app():
    app.run(port=5000)

flask_thread = threading.Thread(target=run_flask_app)
flask_thread.daemon = True
flask_thread.start()

if __name__ == '__main__':
    app_qt = QApplication(sys.argv)
    window = VersionManagerApp()
    window.show()
    sys.exit(app_qt.exec_())
