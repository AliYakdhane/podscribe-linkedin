# 🤖 Production Cron Job Setup for Podcast Puller

## 🎯 **Goal**: Automatically pull new episodes every 6 hours in production

Since Streamlit Community Cloud doesn't support scheduled tasks, we need external services to trigger your app.

## 🚀 **Option 1: GitHub Actions (Recommended - Free)**

### **Setup Steps:**

1. **Create GitHub Actions Workflow**
   - Go to your GitHub repository
   - Create `.github/workflows/podcast-cron.yml`

2. **Workflow Configuration:**
```yaml
name: Podcast Auto Puller
on:
  schedule:
    # Run every 6 hours (0, 6, 12, 18 UTC)
    - cron: '0 */6 * * *'
  workflow_dispatch: # Allow manual trigger

jobs:
  pull-episodes:
    runs-on: ubuntu-latest
    steps:
      - name: Trigger Streamlit App
        run: |
          curl -X POST "https://your-app-name.streamlit.app/api/trigger" \
            -H "Content-Type: application/json" \
            -d '{"openai_key": "${{ secrets.OPENAI_API_KEY }}"}'
```

### **Pros:**
- ✅ **Free** for public repositories
- ✅ **Reliable** GitHub infrastructure
- ✅ **Easy to set up**
- ✅ **Manual trigger option**

### **Cons:**
- ❌ **Requires API endpoint** in your Streamlit app
- ❌ **Limited to public repos** for free tier

## 🌐 **Option 2: External Cron Services**

### **A. Cron-job.org (Free)**
1. **Sign up** at [cron-job.org](https://cron-job.org)
2. **Create new cron job**:
   - **URL**: `https://your-app-name.streamlit.app/api/trigger`
   - **Schedule**: `0 */6 * * *` (every 6 hours)
   - **Method**: POST
   - **Body**: `{"openai_key": "your-key"}`

### **B. EasyCron (Free tier available)**
1. **Sign up** at [easycron.com](https://easycron.com)
2. **Create cron job** with same settings

### **C. UptimeRobot (Free)**
1. **Sign up** at [uptimerobot.com](https://uptimerobot.com)
2. **Create HTTP(s) monitor**
3. **Set to ping every 6 hours**

## 🔧 **Option 3: Add API Endpoint to Streamlit App**

We need to add an API endpoint to your Streamlit app that can be triggered externally.

### **Step 1: Create API Handler**

Create `api_handler.py`:
```python
import streamlit as st
import subprocess
import os
import json

def handle_api_request():
    """Handle API requests for cron job triggers"""
    if st.request.method == "POST":
        try:
            # Get request data
            data = st.request.json or {}
            openai_key = data.get("openai_key")
            
            if not openai_key:
                return {"error": "OpenAI API key required"}, 400
            
            # Set environment variables
            env = os.environ.copy()
            env["OPENAI_API_KEY"] = openai_key
            env["MAX_EPISODES_PER_RUN"] = "3"  # Pull up to 3 episodes
            
            # Run the main script
            result = subprocess.run(
                ["python", "-m", "src.main"],
                env=env,
                capture_output=True,
                text=True,
                timeout=1800  # 30 minutes timeout
            )
            
            return {
                "success": True,
                "output": result.stdout,
                "error": result.stderr if result.stderr else None
            }
            
        except Exception as e:
            return {"error": str(e)}, 500
    else:
        return {"error": "Method not allowed"}, 405
```

### **Step 2: Update streamlit_app.py**

Add to the top of your `streamlit_app.py`:
```python
# API endpoint for cron jobs
if st.request and hasattr(st.request, 'method'):
    if st.request.method == "POST" and st.request.path == "/api/trigger":
        from api_handler import handle_api_request
        response, status = handle_api_request()
        st.json(response)
        st.stop()
```

## 📱 **Option 4: Streamlit Cloud + External Trigger**

### **Simplified Approach:**
1. **Create a simple trigger page** in your Streamlit app
2. **Use external cron service** to visit the trigger page
3. **Auto-execute** the podcast puller

### **Implementation:**
```python
# Add to streamlit_app.py
if st.query_params.get("trigger") == "auto":
    st.title("🤖 Auto-triggered Podcast Pull")
    st.info("This page was triggered by cron job")
    
    # Auto-run the podcast puller
    if st.button("🚀 Run Podcast Puller", key="auto_run"):
        # Your existing podcast puller logic here
        pass
```

**Cron URL**: `https://your-app-name.streamlit.app/?trigger=auto`

## 🎯 **Recommended Solution: GitHub Actions**

### **Why GitHub Actions?**
- ✅ **Free** and reliable
- ✅ **No external dependencies**
- ✅ **Easy to monitor**
- ✅ **Version controlled**
- ✅ **Manual trigger option**

### **Complete Setup:**

1. **Create `.github/workflows/podcast-cron.yml`**:
```yaml
name: Podcast Auto Puller
on:
  schedule:
    - cron: '0 */6 * * *'  # Every 6 hours
  workflow_dispatch:

jobs:
  pull-episodes:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
      
      - name: Run podcast puller
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
        run: |
          python -m src.main
```

2. **Add secrets to GitHub**:
   - Go to your repo → Settings → Secrets
   - Add `OPENAI_API_KEY`
   - Add `SUPABASE_URL`
   - Add `SUPABASE_SERVICE_ROLE_KEY`

3. **Enable GitHub Actions**:
   - Go to Actions tab in your repo
   - Enable workflows

## 🔍 **Monitoring & Logs**

### **GitHub Actions Logs:**
- View run history in Actions tab
- See detailed logs for each run
- Get email notifications on failures

### **Streamlit App Logs:**
- Check Streamlit logs in your dashboard
- Monitor for errors and successes

## ⚙️ **Configuration Options**

### **Schedule Variations:**
```yaml
# Every 6 hours
- cron: '0 */6 * * *'

# Every 4 hours
- cron: '0 */4 * * *'

# Every 12 hours (twice daily)
- cron: '0 */12 * * *'

# Daily at 9 AM UTC
- cron: '0 9 * * *'
```

### **Error Handling:**
```yaml
- name: Run podcast puller
  run: |
    python -m src.main || echo "Podcast puller failed"
```

## 🎉 **Benefits of Automation:**

1. **Always Up-to-Date**: New episodes pulled automatically
2. **No Manual Work**: Set it and forget it
3. **Reliable**: Runs even when you're not around
4. **Scalable**: Easy to adjust frequency
5. **Monitorable**: Full logging and error handling

Choose the option that works best for your setup! GitHub Actions is recommended for most users. 🚀
