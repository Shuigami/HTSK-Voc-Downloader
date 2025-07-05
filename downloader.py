import os
import asyncio
import aiohttp
import aiofiles
import re
import csv
from bs4 import BeautifulSoup, Tag
from urllib.parse import urljoin

async def download_mp3(session, mp3_url, filepath):
    """Télécharge un fichier MP3 de manière asynchrone"""
    filename = os.path.basename(filepath)
    print(f"Téléchargement de {filename}...")
    try:
        async with session.get(mp3_url) as response:
            response.raise_for_status()
            async with aiofiles.open(filepath, "wb") as f:
                async for chunk in response.content.iter_chunked(8192):
                    await f.write(chunk)
        print(f"{filename} téléchargé avec succès.")
        return True
    except Exception as e:
        print(f"Erreur lors du téléchargement de {filename}: {e}")
        return False

async def extract_mp3_links_from_url(session, url):
    """Extrait tous les liens MP3 d'une URL donnée ainsi que le mot coréen associé"""
    print(f"Analyse de l'URL: {url}")
    try:
        async with session.get(url) as response:
            response.raise_for_status()
            html_content = await response.text()
        
        soup = BeautifulSoup(html_content, "html.parser")
        
        # Extraire le numéro de leçon depuis l'URL
        lesson_match = re.search(r'lesson-(\d+)', url)
        lesson_number = lesson_match.group(1) if lesson_match else "unknown"
        
        # Trouver tous les liens vers des fichiers MP3
        mp3_links = []
        for link in soup.find_all("a", href=True):
            if isinstance(link, Tag):
                href = link.get("href")
                if href and isinstance(href, str) and href.lower().endswith(".mp3"):
                    # Vérifier si le mot coréen est présent et non vide
                    korean_word = link.text.strip()
                    if korean_word:
                        full_url = urljoin(url, href)
                        mp3_links.append((full_url, lesson_number, korean_word))
        
        print(f"Trouvé {len(mp3_links)} fichiers MP3 avec mots coréens sur {url} (Lesson {lesson_number})")
        return mp3_links
    
    except Exception as e:
        print(f"Erreur lors de l'analyse de {url}: {e}")
        return []

async def url_extraction():
    # URLs des pages à analyser
    urls = [
        # "https://www.howtostudykorean.com/unit1/unit-1-lessons-17-25-2/lesson-17/"
    ]

    for i in range(26, 34):
        urls.append(f"https://www.howtostudykorean.com/unit-2-lower-intermediate-korean-grammar/unit-2-lessons-26-33/lesson-{i}/")
    
    for i in range(34, 42):
        urls.append(f"https://www.howtostudykorean.com/unit-2-lower-intermediate-korean-grammar/unit-2-lessons-34-41/lesson-{i}/")

    for i in range(42, 51):
        urls.append(f"https://www.howtostudykorean.com/unit-2-lower-intermediate-korean-grammar/unit-2-lessons-42-50/lesson-{i}/")

    # Créer un dossier pour les fichiers audio
    os.makedirs("audios", exist_ok=True)
    
    # Préparer le fichier CSV
    csv_filepath = "vocabulary.csv"
    is_new_file = not os.path.exists(csv_filepath)
    
    headers = {"User-Agent": "Mozilla/5.0"}
    all_mp3_links = []
    
    # Extraire les liens MP3 de toutes les URLs
    async with aiohttp.ClientSession(headers=headers) as session:
        # Traiter toutes les URLs en parallèle
        extraction_tasks = [extract_mp3_links_from_url(session, url) for url in urls]
        url_results = await asyncio.gather(*extraction_tasks, return_exceptions=True)
        
        # Collecter tous les liens MP3
        for result in url_results:
            if isinstance(result, list):
                all_mp3_links.extend(result)
            else:
                print(f"Erreur lors de l'extraction: {result}")
    
    # Supprimer les doublons tout en préservant l'ordre
    unique_mp3_links = []
    seen_urls = set()
    for mp3_url, lesson_num, korean_word in all_mp3_links:
        if mp3_url not in seen_urls:
            unique_mp3_links.append((mp3_url, lesson_num, korean_word))
            seen_urls.add(mp3_url)
    
    print(f"\nTotal: {len(unique_mp3_links)} fichiers MP3 uniques à télécharger")
    
    if not unique_mp3_links:
        print("Aucun fichier MP3 trouvé.")
        return
    
    # Télécharger tous les fichiers MP3 de manière asynchrone
    async with aiohttp.ClientSession(headers=headers) as session:
        tasks = []
        download_info = []
        for mp3_url, lesson_num, korean_word in unique_mp3_links:
            # Créer un sous-dossier pour chaque leçon
            lesson_folder = os.path.join("audios", f"lesson_{lesson_num}")
            os.makedirs(lesson_folder, exist_ok=True)
            
            original_filename = os.path.basename(mp3_url)
            formatted_filename = await format_filename(original_filename)
            filepath = os.path.join(lesson_folder, formatted_filename)
            
            download_info.append({"filepath": filepath, "korean_word": korean_word})
            
            task = download_mp3(session, mp3_url, filepath)
            tasks.append(task)
        
        # Exécuter tous les téléchargements en parallèle
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Compter les succès et écrire dans le CSV
        successful_downloads = 0
        with open(csv_filepath, 'a', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            if is_new_file:
                writer.writerow(['filepath', 'korean_word'])
            
            for i, result in enumerate(results):
                if result is True:
                    writer.writerow([download_info[i]["filepath"], download_info[i]["korean_word"]])
                    successful_downloads += 1

        print(f"\nTéléchargement terminé: {successful_downloads}/{len(unique_mp3_links)} fichiers téléchargés avec succès")
        print(f"Les données ont été ajoutées à {csv_filepath}")

async def format_filename(filename):
    """
    Formate le nom de fichier pour convertir LessonXXvX.mp3 en LessonXXvXX.mp3
    Ajoute un zéro devant le numéro de version s'il n'y en a qu'un seul chiffre
    """
    # Pattern pour capturer LessonXX, v, X et .mp3
    pattern = r'^(Lesson\d+v)(\d)(\.mp3)$'
    match = re.match(pattern, filename)
    
    if match:
        prefix = match.group(1)  # "LessonXXv"
        version = match.group(2)  # "X"
        suffix = match.group(3)   # ".mp3"
        
        # Ajouter un zéro devant si la version n'a qu'un chiffre
        if len(version) == 1:
            formatted_version = f"0{version}"
            return f"{prefix}{formatted_version}{suffix}"
    
    # Retourner le nom original si le pattern ne correspond pas
    return filename

async def rename_existing_files():
    """
    Renomme tous les fichiers existants dans le dossier audios
    pour appliquer le formatage LessonXXvXX.mp3
    """
    audios_folder = "audios"
    
    if not os.path.exists(audios_folder):
        print(f"Le dossier {audios_folder} n'existe pas.")
        return
    
    renamed_count = 0
    
    # Parcourir tous les fichiers dans le dossier audios
    for filename in os.listdir(audios_folder):
        if filename.lower().endswith('.mp3'):
            old_filepath = os.path.join(audios_folder, filename)
            formatted_filename = await format_filename(filename)
            new_filepath = os.path.join(audios_folder, formatted_filename)
            
            # Renommer seulement si le nom change
            if filename != formatted_filename:
                try:
                    # Vérifier si le fichier de destination existe déjà
                    if os.path.exists(new_filepath):
                        print(f"Attention: {formatted_filename} existe déjà, fichier ignoré: {filename}")
                        continue
                    
                    os.rename(old_filepath, new_filepath)
                    print(f"Renommé: {filename} → {formatted_filename}")
                    renamed_count += 1
                except Exception as e:
                    print(f"Erreur lors du renommage de {filename}: {e}")
            else:
                print(f"Déjà formaté: {filename}")
    
    print(f"\nRenommage terminé: {renamed_count} fichiers renommés")


if __name__ == "__main__":
    # Pour télécharger de nouveaux fichiers:
    asyncio.run(url_extraction())
    
    # Pour renommer les fichiers existants dans le dossier audios:
    # asyncio.run(rename_existing_files())

