# GitHub to Bitbucket Auto-Sync Setup

This guide helps you automatically sync your GitHub repository to Bitbucket.

## How It Works

```
Emergent → Save to GitHub → GitHub Actions → Auto-push to Bitbucket
```

Every time you push to GitHub (main/master branch), it automatically syncs to Bitbucket.

---

## Setup Steps

### Step 1: Create Bitbucket Repository

1. Go to [Bitbucket](https://bitbucket.org)
2. Create a new repository (e.g., `chess-coach`)
3. Note your workspace name and repo name

### Step 2: Create Bitbucket App Password

1. Go to **Bitbucket → Personal Settings → App Passwords**
2. Click **Create app password**
3. Give it a name (e.g., "GitHub Sync")
4. Select permissions: **Repositories: Write**
5. Click **Create**
6. **Copy the password** (you won't see it again!)

### Step 3: Add GitHub Secrets

1. Go to your **GitHub repository**
2. Click **Settings → Secrets and variables → Actions**
3. Click **New repository secret**
4. Add these 3 secrets:

| Secret Name | Value |
|-------------|-------|
| `BITBUCKET_USERNAME` | Your Bitbucket username |
| `BITBUCKET_APP_PASSWORD` | The app password from Step 2 |
| `BITBUCKET_REPO` | `workspace/repo-name` (e.g., `mycompany/chess-coach`) |

### Step 4: Done!

The workflow file (`.github/workflows/sync-to-bitbucket.yml`) is already in your repo.

Every push to `main` or `master` will now auto-sync to Bitbucket!

---

## Manual Sync (First Time)

If you need to do an initial sync before GitHub Actions kicks in:

### Option A: PowerShell (Windows)
```powershell
# Edit the script first with your repo details
.\scripts\sync-github-to-bitbucket.ps1
```

### Option B: Command Line (Any OS)
```bash
# Clone from GitHub
git clone --mirror https://github.com/YOUR_USER/YOUR_REPO.git temp-sync
cd temp-sync

# Add Bitbucket and push
git remote add bitbucket https://YOUR_BB_USER:YOUR_APP_PASSWORD@bitbucket.org/WORKSPACE/REPO.git
git push bitbucket --mirror

# Cleanup
cd ..
rm -rf temp-sync
```

---

## Trigger Manual Sync

You can manually trigger the sync from GitHub:

1. Go to your GitHub repo
2. Click **Actions** tab
3. Select **Sync to Bitbucket**
4. Click **Run workflow**

---

## Troubleshooting

### "Repository not found" error
- Make sure the Bitbucket repo exists
- Check workspace/repo name is correct

### "Permission denied" error  
- Verify app password has "Repositories: Write" permission
- Check username is correct (not email)

### Sync not triggering
- Check you're pushing to `main` or `master` branch
- Look at Actions tab for error logs
