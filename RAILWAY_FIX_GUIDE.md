# Railway Deployment Fix Guide

## Problem

Your Railway app is showing "Application failed to respond" error. This typically happens due to:

1. Port binding issues (app not listening on Railway's `$PORT`)
2. Health check timeouts
3. Build/startup timeouts (Camoufox/Playwright installation)

## What Was Fixed

### 1. Created `railway.toml` Configuration

- Configured proper health check with 300s timeout
- Set restart policy for resilience
- Specified Dockerfile build

### 2. Updated `Dockerfile`

- Changed to use `$PORT` environment variable (Railway requirement)
- Added timeout to Camoufox fetch to prevent build hangs
- Removed HEALTHCHECK (Railway handles this)
- Simplified CMD to use shell form for env variable expansion

### 3. Key Changes

**Before:**

```dockerfile
EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.port=8501", ...]
```

**After:**

```dockerfile
ENV PORT=8501
EXPOSE $PORT
CMD streamlit run app.py --server.port=$PORT ...
```

## How to Deploy

### Option 1: Using PowerShell Script (Recommended)

```powershell
.\deploy-to-railway.ps1
```

### Option 2: Manual Steps

```bash
# 1. Link to your project
railway link
# Select "AI-Scrapping" when prompted

# 2. Deploy
railway up

# 3. Monitor logs
railway logs

# 4. Get your app URL
railway domain
```

## Verify Deployment

After deployment, check:

1. **Build logs** - Ensure Playwright and Camoufox install successfully

   ```bash
   railway logs --deployment
   ```

2. **Runtime logs** - Check for Streamlit startup

   ```bash
   railway logs
   ```

3. **Health check** - Should respond at `/_stcore/health`

## Common Issues & Solutions

### Issue: Build timeout

**Solution:** The Dockerfile now has a 300s timeout for Camoufox fetch. If it still times out, Camoufox will fetch at runtime.

### Issue: Port binding error

**Solution:** Fixed - now using `$PORT` environment variable that Railway provides.

### Issue: Health check failing

**Solution:** Increased health check timeout to 300s in railway.toml.

### Issue: App crashes on startup

**Solution:** Check logs with `railway logs` to see specific error. Common causes:

- Missing environment variables
- Playwright/Camoufox installation issues
- Memory limits (upgrade Railway plan if needed)

## Environment Variables

Railway automatically provides:

- `PORT` - The port your app should listen on
- `RAILWAY_ENVIRONMENT` - Current environment (production/staging)

No additional env vars needed for basic deployment.

## Next Steps

1. Run the deployment script
2. Wait for build to complete (may take 5-10 minutes first time)
3. Check logs for any errors
4. Access your app via the Railway-provided URL

## Monitoring

```bash
# Watch live logs
railway logs --follow

# Check deployment status
railway status

# List all deployments
railway list

# Get app URL
railway domain
```

## Rollback (if needed)

If deployment fails, Railway keeps previous working deployment active. You can:

1. Check previous deployments: `railway list`
2. Rollback via Railway dashboard
3. Or fix issues and redeploy

## Support

If issues persist:

1. Check Railway logs: `railway logs`
2. Check Railway dashboard for detailed error messages
3. Verify Dockerfile builds locally: `docker build -t test .`
4. Check Railway status page: https://status.railway.app/
