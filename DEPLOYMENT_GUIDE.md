# MedCheck AI - Deployment Guide (Vercel + Render)

## Overview

This guide covers deploying the full MedCheck AI stack:
- **Frontend**: Vercel (React + TypeScript + Vite)
- **Backend**: Render (FastAPI + SQLAlchemy)

## Part 1: Deploy Backend to Render

### Step 1: Create Render Account
1. Go to https://render.com and sign up
2. Connect your GitHub account

### Step 2: Create a Web Service
1. In Render Dashboard, click **New +** → **Web Service**
2. Select **vamsi-ds/MedCheck-AI** repository
3. Configure:
   - **Name**: `medcheck-ai-backend`
   - **Root Directory**: (leave blank)
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r backend/requirements.txt`
   - **Start Command**: `cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Instance Type**: Free (or Starter+ for persistence)

### Step 3: Set Environment Variables in Render

In the Web Service settings, go to **Environment** and add:

```
MEDCHECK_SECRET_KEY=your-secure-random-string-here-min-32-chars
MEDCHECK_ALLOWED_ORIGINS=https://your-vercel-domain.vercel.app,https://your-custom-domain.com
MEDCHECK_DATABASE_URL=sqlite:////tmp/medcheck.db
MEDCHECK_UPLOAD_DIR=/tmp/uploads
MEDCHECK_DEV_ADMIN_BOOTSTRAP=1
```

**Important Notes:**
- Replace `https://your-vercel-domain.vercel.app` with your actual Vercel domain (you'll get this after deploying frontend)
- For production: use PostgreSQL instead of SQLite by setting `MEDCHECK_DATABASE_URL=postgresql://...`
- Generate a secure `MEDCHECK_SECRET_KEY` with: `python -c "import secrets; print(secrets.token_urlsafe(32))"`

### Step 4: Get Backend URL

After deployment completes:
1. Render assigns a URL like: `https://medcheck-ai-backend.onrender.com`
2. Test it: `https://medcheck-ai-backend.onrender.com/api/health`
3. **Save this URL** for the frontend configuration

---

## Part 2: Deploy Frontend to Vercel

### Step 1: Create Vercel Account
1. Go to https://vercel.com and sign up
2. Connect your GitHub account

### Step 2: Create a Project
1. Click **Add New** → **Project**
2. Select **vamsi-ds/MedCheck-AI**
3. Configure:
   - **Framework**: Vite
   - **Root Directory**: `frontend`
   - **Build Command**: `npm run build`
   - **Output Directory**: `dist`
   - **Install Command**: `npm install`

### Step 3: Set Environment Variables

In Vercel Project Settings → **Environment Variables**, add:

```
VITE_API_BASE_URL=https://medcheck-ai-backend.onrender.com
```

Replace with your actual Render backend URL from Part 1, Step 4.

### Step 4: Deploy

1. Click **Deploy**
2. Wait for build to complete (usually 1-2 minutes)
3. Vercel assigns you a domain: `https://your-project-name.vercel.app`

### Step 5: Update Backend CORS

1. Go back to your Render service
2. Update the `MEDCHECK_ALLOWED_ORIGINS` environment variable to include your Vercel URL:
   ```
   MEDCHECK_ALLOWED_ORIGINS=https://your-project-name.vercel.app,https://your-vercel-domain.vercel.app
   ```
3. Click **Save** (this will trigger a redeploy)

---

## Part 3: Test the Deployment

### Test Backend Health
```bash
curl https://medcheck-ai-backend.onrender.com/api/health
```

Expected response:
```json
{
  "status": "ok",
  "database": "connected",
  "ocr_available": false,
  "version": "1.0.0"
}
```

### Test Frontend
1. Open your Vercel domain in a browser
2. You should see the MedCheck AI login page
3. Sign in with demo credentials:
   - Username: `doctor1`
   - Password: `Doctor123!`

---

## Environment Variables Reference

### Backend (Render)

| Variable | Purpose | Example |
|----------|---------|----------|
| `MEDCHECK_SECRET_KEY` | JWT signing key (MUST be set for production) | `abc123...def456` |
| `MEDCHECK_ALLOWED_ORIGINS` | CORS origins (comma-separated) | `https://myapp.vercel.app,https://mydomain.com` |
| `MEDCHECK_DATABASE_URL` | Database connection | `sqlite:////tmp/medcheck.db` or `postgresql://user:pass@host/db` |
| `MEDCHECK_UPLOAD_DIR` | File upload directory | `/tmp/uploads` |
| `MEDCHECK_MAX_UPLOAD_BYTES` | Max upload size (bytes) | `10485760` (10 MB) |
| `MEDCHECK_DEV_ADMIN_BOOTSTRAP` | Allow dev admin creation | `1` (development only) |

### Frontend (Vercel)

| Variable | Purpose | Example |
|----------|---------|----------|
| `VITE_API_BASE_URL` | Backend API URL | `https://medcheck-ai-backend.onrender.com` |

---

## Troubleshooting

### Backend deployment fails
- Check Render logs: Go to your service → **Logs**
- Ensure `requirements.txt` is in the `backend/` directory
- Verify Python version compatibility (3.11 recommended)

### Frontend won't connect to backend
- Check browser console for CORS errors
- Verify `MEDCHECK_ALLOWED_ORIGINS` includes your Vercel domain
- Test backend health endpoint from browser

### Database errors
- SQLite is volatile on Render (resets on redeploy)
- For persistence, migrate to PostgreSQL:
  1. Create a PostgreSQL database (Render, Supabase, or Railway)
  2. Set `MEDCHECK_DATABASE_URL` to the Postgres connection string
  3. Redeploy

### Uploads disappearing
- SQLite `db` and `/tmp/uploads` persist only until redeploy
- For production, add persistent storage (Render Disk) or use external object storage (AWS S3)

---

## Next Steps (Production)

1. **Add a custom domain** to both services
2. **Upgrade Render plan** (Free tier has limitations; Starter+ recommended)
3. **Enable PostgreSQL** for persistent database
4. **Add S3/Blob storage** for file uploads
5. **Set up monitoring** (Render has native logging)
6. **Enable HTTPS** (automatic on both platforms)
7. **Generate new JWT secret** in production environment

---

## Quick Reference URLs

- Render Dashboard: https://dashboard.render.com
- Vercel Dashboard: https://vercel.com/dashboard
- Backend Health: `https://medcheck-ai-backend.onrender.com/api/health`
- Backend Docs: `https://medcheck-ai-backend.onrender.com/docs`
- Frontend: `https://your-project-name.vercel.app`
