"""
Zoom to YouTube Auto Uploader
This script monitors a folder for new videos and automatically uploads them to YouTube.
Files remain in the original folder after upload.
"""

import os
import time
import pickle
from pathlib import Path
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# ===== CONFIGURATION =====
WATCH_FOLDER = os.environ.get("WATCH_FOLDER", r"C:\Users\Arunya Senadeera\Asian Institute of Technology\jirapas Sangsue - ZOOMRecording")
CLIENT_SECRETS_FILE = os.environ.get("CLIENT_SECRETS_FILE", "client_secrets.json")
TOKEN_FILE = os.environ.get("TOKEN_FILE", "token.pickle")
PROCESSED_FILES_LOG = os.environ.get("PROCESSED_FILES_LOG", "processed_videos.txt")

# Video settings
DEFAULT_TITLE = "Zoom Recording"  # Default title if filename isn't descriptive
DEFAULT_DESCRIPTION = "Automatically uploaded Zoom recording"
DEFAULT_CATEGORY = "27"  # Category 27 = "Education"
DEFAULT_PRIVACY = "unlisted"  # Options: "public", "private", "unlisted"

# Supported video formats
VIDEO_EXTENSIONS = ['.mp4', '.mov', '.avi', '.mkv', '.flv', '.wmv', '.webm']

# YouTube API scope
SCOPES = ['https://www.googleapis.com/auth/youtube.upload']


def authenticate_youtube():
    """
    Authenticate with YouTube using OAuth 2.0
    Returns: YouTube API service object
    """
    creds = None
    
    # Load saved credentials if they exist
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'rb') as token:
            creds = pickle.load(token)
    
    # If no valid credentials, let user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # Check if client_secrets.json exists
            if not os.path.exists(CLIENT_SECRETS_FILE):
                print(f"\n❌ ERROR: {CLIENT_SECRETS_FILE} not found!")
                print(f"Please place your client_secrets.json file in the same folder as this script.")
                print(f"Current folder: {os.getcwd()}")
                input("\nPress Enter to exit...")
                exit()
            
            flow = InstalledAppFlow.from_client_secrets_file(
                CLIENT_SECRETS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save credentials for next time
        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(creds, token)
    
    return build('youtube', 'v3', credentials=creds)


def get_video_title(filename):
    """
    Generate a nice title from the filename
    Example: "Team_Meeting_2024-02-10.mp4" -> "Team Meeting 2024-02-10"
    """
    # Remove extension
    name = Path(filename).stem
    
    # Replace underscores and hyphens with spaces
    name = name.replace('_', ' ').replace('-', ' ')
    
    # If it's just numbers or too short, use default
    if len(name) < 3 or name.replace(' ', '').isdigit():
        return DEFAULT_TITLE
    
    return name


def load_processed_files():
    """
    Load list of already processed files from disk
    Returns: set of file paths that have been uploaded
    """
    if os.path.exists(PROCESSED_FILES_LOG):
        try:
            with open(PROCESSED_FILES_LOG, 'r', encoding='utf-8') as f:
                processed = set(line.strip() for line in f if line.strip())
            print(f"📋 Loaded {len(processed)} previously uploaded file(s)")
            return processed
        except Exception as e:
            print(f"⚠️  Could not load processed files log: {str(e)}")
            return set()
    return set()


def save_processed_file(file_path):
    """
    Add a file to the processed files log
    """
    try:
        with open(PROCESSED_FILES_LOG, 'a', encoding='utf-8') as f:
            f.write(file_path + '\n')
    except Exception as e:
        print(f"   ⚠️  Could not save to processed files log: {str(e)}")


def upload_video(youtube, video_file):
    """
    Upload a video to YouTube
    Returns: True if successful, False otherwise
    """
    try:
        print(f"\n📤 Uploading: {os.path.basename(video_file)}")
        
        # Prepare video metadata
        title = get_video_title(os.path.basename(video_file))
        
        body = {
            'snippet': {
                'title': title,
                'description': DEFAULT_DESCRIPTION,
                'categoryId': DEFAULT_CATEGORY
            },
            'status': {
                'privacyStatus': DEFAULT_PRIVACY,
                'selfDeclaredMadeForKids': False  # Mark as NOT for kids
            }
        }
        
        # Create media upload object
        media = MediaFileUpload(
            video_file,
            chunksize=1024*1024,  # 1MB chunks
            resumable=True
        )
        
        # Execute upload
        request = youtube.videos().insert(
            part=','.join(body.keys()),
            body=body,
            media_body=media
        )
        
        response = None
        print("   Uploading... ", end='', flush=True)
        
        while response is None:
            status, response = request.next_chunk()
            if status:
                progress = int(status.progress() * 100)
                print(f"\r   Uploading... {progress}%", end='', flush=True)
        
        print(f"\r   ✅ Upload complete!")
        print(f"   📺 Video ID: {response['id']}")
        print(f"   🔗 URL: https://www.youtube.com/watch?v={response['id']}")
        print(f"   🔒 Privacy: {DEFAULT_PRIVACY}")
        print(f"   👶 Made for kids: NO")
        print(f"   📁 File remains in: {WATCH_FOLDER}")
        
        return True
        
    except Exception as e:
        print(f"\n   ❌ Upload failed: {str(e)}")
        return False


def get_video_files():
    """
    Get list of video files in the watch folder
    Returns only files that aren't currently being written to
    """
    video_files = []
    
    if not os.path.exists(WATCH_FOLDER):
        return video_files
    
    for file in os.listdir(WATCH_FOLDER):
        file_path = os.path.join(WATCH_FOLDER, file)
        
        # Skip if it's a directory
        if os.path.isdir(file_path):
            continue
        
        # Check if it's a video file
        if Path(file).suffix.lower() in VIDEO_EXTENSIONS:
            # Check if file is being written to (wait if file is still growing)
            try:
                initial_size = os.path.getsize(file_path)
                time.sleep(2)
                final_size = os.path.getsize(file_path)
                
                # Only add if file size hasn't changed (not being written to)
                if initial_size == final_size:
                    video_files.append(file_path)
            except:
                # File might be locked, skip it
                pass
    
    return video_files


def setup_folders():
    """
    Create necessary folders if they don't exist
    """
    try:
        os.makedirs(WATCH_FOLDER, exist_ok=True)
        print(f"✅ Folder ready:")
        print(f"   📂 Watch folder: {WATCH_FOLDER}")
        return True
    except Exception as e:
        print(f"❌ Could not create folder: {str(e)}")
        return False


def main():
    """
    Main function - runs the upload monitor
    """
    print("=" * 60)
    print("  ZOOM TO YOUTUBE AUTO UPLOADER")
    print("=" * 60)
    print()
    
    # Setup folders
    if not setup_folders():
        input("\nPress Enter to exit...")
        return
    
    # Authenticate with YouTube
    print("\n🔐 Authenticating with YouTube...")
    try:
        youtube = authenticate_youtube()
        print("✅ Authentication successful!")
    except Exception as e:
        print(f"❌ Authentication failed: {str(e)}")
        input("\nPress Enter to exit...")
        return
    
    print("\n" + "=" * 60)
    print("  🎬 Monitoring for new videos...")
    print(f"  📂 Watch folder: {WATCH_FOLDER}")
    print("  ℹ️  Files remain in folder after upload")
    print("  🔒 Duplicate upload prevention: ENABLED")
    print("  👶 Made for kids: NO (automatic)")
    print("  Press Ctrl+C to stop")
    print("=" * 60)
    
    # Load previously processed files
    processed_files = load_processed_files()
    
    try:
        while True:
            # Check for new video files
            video_files = get_video_files()
            
            for video_file in video_files:
                # Skip if already processed
                if video_file in processed_files:
                    continue
                
                # Upload the video
                success = upload_video(youtube, video_file)
                
                if success:
                    # Mark as processed and save to disk
                    processed_files.add(video_file)
                    save_processed_file(video_file)
                    print(f"   ✅ File kept in original location")
                    print(f"   📝 Marked as uploaded (won't upload again)")
                else:
                    print("   ⚠️  Keeping file in folder for retry")
            
            # Wait before checking again
            time.sleep(10)
            
    except KeyboardInterrupt:
        print("\n\n⏹️  Stopping monitor...")
        print("Goodbye!")


if __name__ == "__main__":
    main()