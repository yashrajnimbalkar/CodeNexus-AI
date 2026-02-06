import os
import base64
from fastapi import FastAPI, Request, HTTPException
from github import Github
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# Setup GitHub & Gemini
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# Your Render URL (The "Doctor's Address")
# REPLACE THIS with your actual Render URL (e.g., https://code-nexus...onrender.com)
WEBHOOK_URL = "https://codenexus-ai-nebs.onrender.com/github-webhook" 

if GITHUB_TOKEN:
    gh = Github(GITHUB_TOKEN)
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

app = FastAPI()

# --- 1. THE NEW FEATURE: Connect a new "Patient" Repo ---
@app.post("/track-repo")
def track_repository(repo_name: str):
    """
    Tells the AI to start watching a specific repository.
    Example repo_name: 'yashrajnimbalkar/My-New-Project'
    """
    try:
        user = gh.get_user()
        repo = user.get_repo(repo_name)
        
        # Check if we already hooked this repo
        hooks = repo.get_hooks()
        for hook in hooks:
            if "onrender.com" in hook.config.get("url", ""):
                return {"status": f"⚠️ Already watching {repo_name}!"}

        # Create the webhook automatically
        config = {
            "url": WEBHOOK_URL,
            "content_type": "json"
        }
        # Events we want to watch (push means code changes)
        repo.create_hook("web", config, ["push"], active=True)
        
        return {"status": f"✅ Success! Now protecting {repo_name} from bugs."}
        
    except Exception as e:
        return {"error": str(e)}

# --- 2. THE LISTENER: Catches the bugs ---
@app.post("/github-webhook")
async def handle_webhook(request: Request):
    payload = await request.json()
    
    # Logic to fix the code (same as before)
    if "commits" in payload:
        repo_name = payload["repository"]["full_name"]
        print(f"🚑 Received alert from patient: {repo_name}")
        
        repo = gh.get_repo(repo_name)
        for commit in payload["commits"]:
            # Now we look at ALL added or modified Python files
            files_to_check = commit.get("modified", []) + commit.get("added", [])
            
            for file_path in files_to_check:
                if file_path.endswith(".py"):
                    try:
                        print(f"Scanning file: {file_path}...")
                        file_content = repo.get_contents(file_path)
                        old_code = base64.b64decode(file_content.content).decode()
                        
                        # Ask Gemini to fix it
                        model = genai.GenerativeModel('gemini-1.5-flash')
                        prompt = f"Fix any bugs, syntax errors, or logic issues in this Python code. Return ONLY the corrected code, no markdown:\n\n{old_code}"
                        response = model.generate_content(prompt)
                        new_code = response.text.replace("```python", "").replace("```", "")
                        
                        if new_code.strip() != old_code.strip():
                            repo.update_file(
                                file_path, 
                                "🤖 AI Doctor: Fixed crash/syntax error", 
                                new_code, 
                                file_content.sha
                            )
                            print(f"✅ Fixed {file_path} in {repo_name}")
                    except Exception as e:
                        print(f"⚠️ Could not fix {file_path}: {e}")

    return {"status": "Analysis complete"}

@app.get("/")
def home():
    return {"message": "CodeNexus AI Doctor is Online 👨‍⚕️"}
