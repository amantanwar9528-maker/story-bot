# 🎬 Story Bot — Fully Automated YouTube Story Channel

A zero-cost, fully automated system that generates, edits, and uploads children's stories and horror stories to YouTube and Instagram — running entirely on GitHub Actions so your laptop stays off.

## What This Bot Does

Every day at 12:30 AM IST, GitHub Actions automatically:

1. **Selects 3 story topics** (2 children's + 1 horror) from a curated database
2. **Writes full scripts** with scene-by-scene narration and visual prompts using Gemini API
3. **Generates human-like narration** with subtitles using Microsoft Edge TTS (edge-tts)
4. **Creates cartoon-style illustrations** for each scene via Hugging Face Stable Diffusion
5. **Fetches royalty-free stock videos** from Pexels and Pixabay APIs
6. **Downloads mood-matched background music** from Pixabay
7. **Assembles the final video** with FFmpeg — Ken Burns zoom effects, crossfade transitions, burned-in subtitles, ducked background music, and watermark
8. **Generates a Ghibli-style thumbnail** with title text overlay
9. **Uploads to YouTube** with scheduled publishing at 7 AM, 1 PM, and 6 PM IST
10. **Creates and posts Instagram Reels** (30-second vertical promos) linking back to YouTube

No face reveal. No manual editing. No laptop running. No money spent.

---

## Prerequisites — Free Accounts & API Keys

Create accounts and get API keys for each of these free services:

| Service | What You Get | Where to Sign Up |
|---------|-------------|------------------|
| Google Cloud Console | YouTube Data API v3 + Gemini API key | <https://console.cloud.google.com> |
| Hugging Face | Free AI image generation API token | <https://huggingface.co/settings/tokens> |
| Pexels | Free stock video/image API key | <https://www.pexels.com/api> |
| Pixabay | Free stock media + music API key | <https://pixabay.com/api/docs> |
| GitHub | Free repository + Actions (unlimited for public repos) | <https://github.com> |

You also need:
- A **YouTube channel** (linked to a Google account)
- An **Instagram account** (username and password)

---

## Step-by-Step Setup

### Step 1: Create the GitHub Repository

1. Go to <https://github.com/new>
2. Name it `story-bot` (or any name)
3. Set it to **Public** (required for unlimited free GitHub Actions minutes)
4. Do **not** initialize with a README (you'll add files manually)
5. Click **Create repository**

### Step 2: Add All Project Files

Upload all files from this project to your repository, maintaining the directory structure:

```
story-bot/
├── .github/workflows/
│   ├── generate-and-upload.yml
│   └── instagram-reels.yml
├── src/
│   ├── __init__.py
│   ├── config.py
│   ├── utils.py
│   ├── script_writer.py
│   ├── tts_engine.py
│   ├── image_generator.py
│   ├── media_fetcher.py
│   ├── music_fetcher.py
│   ├── video_editor.py
│   ├── thumbnail_gen.py
│   ├── youtube_uploader.py
│   ├── instagram_poster.py
│   └── content_manager.py
├── assets/
│   ├── fonts/
│   ├── music/
│   └── overlays/
├── data/
│   ├── topics.json
│   └── published.json
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

You can do this via the GitHub web UI (click **Add file → Upload files**) or by cloning and pushing:

```bash
git clone https://github.com/YOUR_USERNAME/story-bot.git
cd story-bot
# Copy all files here
git add .
git commit -m "Initial commit — Story Bot"
git push
```

### Step 3: Get API Keys

#### Google Cloud Console (YouTube API + Gemini)

1. Go to <https://console.cloud.google.com>
2. Create a new project (e.g., "Story Bot")
3. Enable **YouTube Data API v3**:
   - APIs & Services → Library → search "YouTube Data API v3" → Enable
4. Enable **Generative Language API** (for Gemini):
   - APIs & Services → Library → search "Generative Language API" → Enable
5. Create an API key for Gemini:
   - APIs & Services → Credentials → Create Credentials → API key
   - Name it "Gemini API Key"
   - Copy the key — this is your `GEMINI_API_KEY`
6. Create OAuth 2.0 credentials for YouTube:
   - APIs & Services → Credentials → Create Credentials → OAuth client ID
   - Application type: **Desktop app**
   - Name it "Story Bot YouTube"
   - Download the JSON file — rename it to `client_secrets.json`

#### Hugging Face

1. Go to <https://huggingface.co/settings/tokens>
2. Click **New token** → type: **Read** → name it "Story Bot"
3. Copy the token — this is your `HUGGINGFACE_API_KEY`

#### Pexels

1. Go to <https://www.pexels.com/api>
2. Click **Get Started** → fill the form
3. Copy your API key — this is your `PEXELS_API_KEY`

#### Pixabay

1. Go to <https://pixabay.com/api/docs>
2. Register and log in
3. Your API key is shown at the top of the page — this is your `PIXABAY_API_KEY`

### Step 4: Run the YouTube OAuth Flow (One-Time, Local)

This step generates a `token.json` refresh token that lets the bot upload to your YouTube channel automatically. You only do this **once** on your laptop.

1. Install Python 3.11+ from <https://python.org>
2. Clone your repo locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/story-bot.git
   cd story-bot
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Place the `client_secrets.json` file (downloaded in Step 3) in the project root
5. Run the OAuth flow:
   ```bash
   python -m src.youtube_uploader --auth
   ```
6. A browser window opens — log in with your Google account and authorize the app
7. A `token.json` file is created in the project root
8. Encode both files as base64 (for GitHub Secrets):
   ```bash
   base64 -w 0 client_secrets.json
   base64 -w 0 token.json
   ```
   Copy each output string — you'll paste them into GitHub Secrets.

> **Windows PowerShell alternative:**
> ```powershell
> [Convert]::ToBase64String([IO.File]::ReadAllBytes("client_secrets.json"))
> [Convert]::ToBase64String([IO.File]::ReadAllBytes("token.json"))
> ```

### Step 5: Configure GitHub Secrets

Secrets are encrypted and never visible in logs. Go to your repository → **Settings → Secrets and variables → Actions → New repository secret**. Add each one:

| Secret Name | Value |
|-------------|-------|
| `GEMINI_API_KEY` | Your Gemini API key |
| `HUGGINGFACE_API_KEY` | Your Hugging Face token |
| `PEXELS_API_KEY` | Your Pexels API key |
| `PIXABAY_API_KEY` | Your Pixabay API key |
| `YOUTUBE_CLIENT_SECRETS_B64` | Base64 output of `client_secrets.json` |
| `YOUTUBE_TOKEN_B64` | Base64 output of `token.json` |
| `INSTAGRAM_USERNAME` | Your Instagram username |
| `INSTAGRAM_PASSWORD` | Your Instagram password |
| `TIMEZONE` | Your timezone (e.g., `Asia/Kolkata`) |

### Step 6: Add Optional Assets

These are optional but improve quality:

- **Watermark logo**: Place a transparent PNG at `assets/overlays/watermark.png` (recommended size: 120px wide)
- **Background music**: Place royalty-free MP3s in `assets/music/` with mood prefixes (e.g., `happy_01.mp3`, `scary_01.mp3`, `bg_ambient.mp3`) as a fallback when Pixabay music is unavailable
- **Custom fonts**: Place `.ttf` files in `assets/fonts/` (the system uses DejaVu Sans by default, which is pre-installed on GitHub Actions)

### Step 7: Test the Pipeline Manually

Before enabling the daily schedule, test with a single video:

1. Go to your repository → **Actions** tab
2. Select **Daily Story Pipeline** from the left sidebar
3. Click **Run workflow**
4. Set `num_videos` to `1` for a faster test
5. Click **Run workflow**
6. Monitor the run — it takes 30–90 minutes per video
7. Check the **Artifacts** section at the bottom for generated files

If the run succeeds, you'll see:
- A new video on your YouTube channel (scheduled or published)
- An Instagram Reel posted to your account
- An updated `data/published.json` in the artifacts

### Step 8: Enable the Daily Schedule

The cron schedule is already in the workflow file. Once the workflow file is on your default branch (main), GitHub automatically runs it daily at 7 PM UTC (12:30 AM IST next day).

To verify the schedule is active:
1. Go to **Actions** tab
2. Click on **Daily Story Pipeline**
3. You should see "This workflow has a `schedule` event" with the next run time

> **Note:** GitHub disables scheduled workflows on repos with no activity for 60 days. Make a commit (even a small one) at least once every 60 days to keep it active.

---

## How the Schedule Works

```
12:30 AM IST  →  Pipeline starts (generates 3 videos)
    ↓
  ~4:00 AM IST  →  All 3 videos uploaded to YouTube
    ↓               with scheduled publish times:
    ↓               Video 1 → publishes at 7:00 AM IST
    ↓               Video 2 → publishes at 1:00 PM IST
    ↓               Video 3 → publishes at 6:00 PM IST
    ↓
  Instagram Reels posted as promos with YouTube links
```

YouTube handles the scheduled publishing automatically — your videos go public at the exact times even though they were uploaded hours earlier.

---

## Customization

### Change the Upload Schedule

Edit `UPLOAD_TIMES` in `src/config.py` and the cron schedule in `.github/workflows/generate-and-upload.yml`.

### Add More Story Topics

Edit `data/topics.json` — add entries to the `children` or `horror` arrays. Each entry needs a `title` and `description`.

### Change the Voice

Edit `DEFAULT_VOICE` in `src/config.py`. Popular options:
- `en-US-AriaNeural` — warm female voice (default)
- `en-US-GuyNeural` — deep male voice
- `en-GB-SoniaNeural` — British female voice
- `en-IN-NeerjaNeural` — Indian English female voice

Run `edge-tts --list-voices` to see all available voices.

### Change Video Resolution

Edit `VIDEO_RESOLUTION` in `src/config.py` (e.g., `1280x720` for faster rendering).

### Adjust Music Volume

Edit the `music_volume` parameter in `src/content_manager.py` (default: `0.12` — very quiet under narration).

---

## Troubleshooting

### Workflow doesn't trigger on schedule

- Ensure the repository is **public** (private repos have 2,000 min/month limit)
- Ensure the workflow file is on the **default branch** (usually `main`)
- GitHub cron can delay up to 15 minutes during high load
- Make a commit if the repo has been inactive for 60+ days

### YouTube upload fails

- Check that `YOUTUBE_TOKEN_B64` and `YOUTUBE_CLIENT_SECRETS_B64` secrets are set correctly
- The refresh token may expire after 6 months of non-use — re-run the OAuth flow locally and update the secret
- YouTube API quota: 10,000 units/day. Each upload costs ~1,600 units. 3 uploads = 4,800 units (well within limit)

### Hugging Face image generation fails

- The free tier is rate-limited. The bot has retry logic and fallback images built in
- If the model is loading (503), the bot waits and retries automatically
- Check that your `HUGGINGFACE_API_KEY` token has **Read** access

### Instagram login fails

- Instagram may require 2FA or email verification for new login locations
- Log in manually from a browser first, then try the bot again
- The session is cached between runs to reduce login frequency
- **If your account gets flagged**: Switch to Instagram's official Graph API (requires a Facebook Business account, but carries zero ban risk)

### FFmpeg rendering is too slow

- The workflow automatically sets FFmpeg to `ultrafast` preset for CI
- For even faster rendering, reduce `VIDEO_RESOLUTION` to `1280x720`
- Reduce the number of scenes by adjusting the prompt in `src/script_writer.py`

### Video is too long or too short

- Edit `TARGET_DURATION_MIN` and `TARGET_DURATION_MAX` in `src/config.py`
- The script writer targets approximately 6,000 words for a 40-minute video at 150 WPM

---

## Privacy & Security

- **All credentials are stored as GitHub Encrypted Secrets** — AES-128 encrypted at rest, automatically masked in logs
- **No secrets appear in code** — everything is read via `os.getenv()` at runtime
- **The `.gitignore` file** prevents `.env`, `client_secrets.json`, `token.json`, and output files from being committed
- **GitHub Secret Scanning** automatically alerts if a secret is accidentally pushed
- **YouTube OAuth refresh token** — the bot never stores your Google password; it uses a revocable refresh token
- **Instagram credentials** — stored as secrets but used via password login (see risk notice below)

### If you accidentally commit a secret

1. Go to repository **Settings → Secrets and variables → Actions**
2. Delete the exposed secret and create a new one with a fresh value
3. Rotate the compromised API key at the provider's website
4. Use `git filter-branch` or BFG Repo-Cleaner to remove it from history

---

## Important Risk Notices

### Instagram Automation Risk

This bot uses `instagrapi` with username/password login, which **violates Instagram's Terms of Service**. Instagram actively detects automated logins and may:
- Require email/phone verification
- Shadowban your account (reduced reach)
- Temporarily or permanently suspend your account

**Safer alternative**: Use Instagram's official Graph API with OAuth login (requires a Facebook Business account and Instagram Professional account). This carries zero ban risk but requires more setup.

### YouTube Content Policy

- The bot marks children's content as "made for kids" (COPPA compliance)
- Comments are disabled on made-for-kids videos by YouTube policy
- Ensure your content does not violate YouTube's Community Guidelines
- AI-generated content should follow YouTube's AI disclosure requirements

### GitHub Actions Limits

- **Public repositories**: Unlimited minutes per month
- **Private repositories**: 2,000 minutes/month (not enough for daily 3-video generation)
- **Job timeout**: 6 hours maximum per job
- **Scheduled workflow inactivity**: Disabled after 60 days of no repo activity

---

## Tech Stack Summary

| Component | Tool | Cost |
|-----------|------|------|
| Script writing | Gemini API | Free (user has paid tier) |
| Text-to-speech | edge-tts (Microsoft Edge TTS) | Free, no API key |
| AI images | Hugging Face Inference API | Free tier |
| Stock video/images | Pexels API + Pixabay API | Free |
| Background music | Pixabay API | Free |
| Video editing | FFmpeg + MoviePy | Free, open-source |
| YouTube upload | YouTube Data API v3 | Free (10K units/day) |
| Instagram Reels | instagrapi | Free (ToS risk) |
| Scheduling/CI | GitHub Actions (public repo) | Free, unlimited |
| Secrets management | GitHub Encrypted Secrets | Free |
| Core language | Python 3.11 | Free, open-source |

---

## File Reference

| File | Purpose |
|------|---------|
| `src/config.py` | Central configuration, loads env vars and secrets |
| `src/utils.py` | Logging, text processing, JSON parsing, safety checks |
| `src/script_writer.py` | Generates story scripts via Gemini API |
| `src/tts_engine.py` | Creates narration audio + SRT subtitles via edge-tts |
| `src/image_generator.py` | Generates cartoon scene images via Hugging Face |
| `src/media_fetcher.py` | Fetches stock videos/images from Pexels + Pixabay |
| `src/music_fetcher.py` | Fetches royalty-free background music from Pixabay |
| `src/video_editor.py` | Assembles final video with FFmpeg (transitions, effects, music) |
| `src/thumbnail_gen.py` | Generates Ghibli-style thumbnails with title overlay |
| `src/youtube_uploader.py` | Uploads videos + thumbnails to YouTube with scheduled publish |
| `src/instagram_poster.py` | Posts promotional Reels to Instagram via instagrapi |
| `src/content_manager.py` | Orchestrates the full pipeline (main entry point) |
| `.github/workflows/generate-and-upload.yml` | Main daily cron workflow |
| `.github/workflows/instagram-reels.yml` | Optional time-specific Reel posting |
| `data/topics.json` | Curated story topic database |
| `data/published.json` | Tracks published content (avoids duplicates) |
