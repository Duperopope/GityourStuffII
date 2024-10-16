import sys
import os
import shutil
import zipfile
from datetime import datetime
from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QLabel, QComboBox, QMessageBox, QFileDialog, QWidget, QVBoxLayout, QHBoxLayout
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap, QPainterPath, QPainter
import requests
from io import BytesIO
from flask import Flask, request
import threading
import webbrowser

# Informations OAuth de l'application GitHub
CLIENT_ID = 'Ov23lie1vc5lKwoGfgwK'
CLIENT_SECRET = 'ce71a9ced8e3464ef9f68b1710d1487bfd224a77'
REDIRECT_URI = 'http://localhost:5000/callback'

# Flask app to handle OAuth callback
app = Flask(__name__)

# Variable globale pour stocker le code d'authentification
auth_code = None

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
    token_response = requests.post(token_url, data=token_data, headers=headers)
    return token_response.json().get('access_token')

def get_github_user_info(access_token):
    user_url = "https://api.github.com/user"
    headers = {'Authorization': f'token {access_token}'}
    response = requests.get(user_url, headers=headers)
    return response.json()

def get_github_last_push(access_token):
    repos_url = "https://api.github.com/user/repos"
    headers = {'Authorization': f'token {access_token}'}
    response = requests.get(repos_url, headers=headers)
    return response.json()

class VersionManagerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle('Gestion des Versions et Authentification GitHub')
        self.setGeometry(200, 200, 600, 500)

        # Style général de l'interface avec QSS (similaire à CSS)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1b2a38;
            }
            QPushButton {
                background-color: #517fa4;
                color: white;
                padding: 10px;
                border-radius: 5px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #243949;
            }
            QLabel {
                color: white;
                font-size: 18px;
                padding: 5px;
            }
            QComboBox {
                background-color: #ffffff;
                color: #000000;
                padding: 5px;
                font-size: 14px;
            }
        """)

        self.main_widget = QWidget()
        self.setCentralWidget(self.main_widget)
        self.layout = QVBoxLayout()
        self.main_widget.setLayout(self.layout)

        # Ajouter un titre
        self.title_label = QLabel('Gestion des Versions du Projet & Authentification GitHub', self)
        self.title_label.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.title_label)

        # Ajouter les boutons pour la gestion des versions
        self.sauvegarder_btn = QPushButton('Sauvegarder la version', self)
        self.sauvegarder_btn.clicked.connect(self.sauvegarder_version)
        self.layout.addWidget(self.sauvegarder_btn)

        self.restaurer_btn = QPushButton('Restaurer une version', self)
        self.restaurer_btn.clicked.connect(self.restaurer_version)
        self.layout.addWidget(self.restaurer_btn)

        self.archiver_btn = QPushButton('Archiver une version', self)
        self.archiver_btn.clicked.connect(self.archiver_version)
        self.layout.addWidget(self.archiver_btn)

        self.extraire_btn = QPushButton('Extraire une version d\'un ZIP', self)
        self.extraire_btn.clicked.connect(self.extraire_version)
        self.layout.addWidget(self.extraire_btn)

        # Section pour l'authentification GitHub
        self.github_btn = QPushButton('Se connecter à GitHub', self)
        self.github_btn.clicked.connect(self.se_connecter_github)
        self.layout.addWidget(self.github_btn)

        # Label pour afficher les informations de l'utilisateur
        self.github_info_label = QLabel(self)
        self.github_info_label.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.github_info_label)

    def se_connecter_github(self):
        open_github_auth()
        self.check_authentication()

    def check_authentication(self):
        if auth_code:
            access_token = get_access_token(auth_code)
            if access_token:
                user_info = get_github_user_info(access_token)
                repos = get_github_last_push(access_token)
                self.afficher_github_info(user_info, repos)
            else:
                QMessageBox.warning(self, 'Erreur', 'Échec de la récupération du jeton d\'accès.')
        else:
            # Attendre et vérifier de nouveau après 1 seconde
            QTimer.singleShot(1000, self.check_authentication)

    def afficher_github_info(self, user_info, repos):
        self.github_info_label.setText(f"Nom d'utilisateur : {user_info['login']}\nNom complet : {user_info.get('name', 'Non défini')}")

        # Télécharger l'avatar et l'afficher en rond
        avatar_url = user_info['avatar_url']
        response = requests.get(avatar_url)
        img_data = BytesIO(response.content)
        pixmap = QPixmap()
        pixmap.loadFromData(img_data.read())
        self.display_rounded_image(pixmap)

        # Afficher les derniers push
        for repo in repos[:5]:
            repo_label = QLabel(f"{repo['name']} - Dernier push : {repo['pushed_at']}")
            self.layout.addWidget(repo_label)

    def display_rounded_image(self, pixmap):
        size = 150
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
        self.layout.addWidget(image_label)

    # Les fonctions de gestion des versions restent inchangées
    def sauvegarder_version(self):
        # ... (code pour sauvegarder une version)
        pass

    def restaurer_version(self):
        # ... (code pour restaurer une version)
        pass

    def archiver_version(self):
        # ... (code pour archiver une version)
        pass

    def extraire_version(self):
        # ... (code pour extraire une version à partir d'un ZIP)
        pass

# Lancer l'application Flask dans un thread séparé
flask_thread = threading.Thread(target=run_flask_app)
flask_thread.daemon = True
flask_thread.start()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = VersionManagerApp()
    window.show()
    sys.exit(app.exec_())
