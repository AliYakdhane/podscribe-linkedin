# 🚀 Deployment Guide - Streamlit Community Cloud

## ✅ Project Successfully Pushed to GitHub!

Your project has been successfully pushed to: **https://github.com/AliYakdhane/podscribe-linkedin.git**

## 🌐 Deploy to Streamlit Community Cloud

### Step 1: Go to Streamlit Community Cloud
1. Visit [share.streamlit.io](https://share.streamlit.io)
2. Sign in with your GitHub account
3. Click **"New app"**

### Step 2: Configure Your App
1. **Repository**: `AliYakdhane/podscribe-linkedin`
2. **Branch**: `main`
3. **Main file path**: `streamlit_app.py`
4. **App URL**: Choose a custom URL (e.g., `podscribe-linkedin`)

### Step 3: Set Environment Variables (Optional)
In the Streamlit Community Cloud dashboard, you can set these secrets:

```
OPENAI_API_KEY = your_openai_api_key_here
ASSEMBLYAI_API_KEY = your_assemblyai_api_key_here
SHOW_ID = 1680633614
```

### Step 4: Deploy!
Click **"Deploy!"** and wait for the deployment to complete.

## 🔧 Local Development

### Run Locally
```bash
# Install dependencies
pip install -r requirements.txt

# Run Streamlit app
streamlit run streamlit_app.py
```

### Run the Main Script
```bash
python -m src.main
```

## 📋 Features Available in the Deployed App

- ✅ **Interactive UI**: Pull podcast episodes with a web interface
- ✅ **Multiple Transcription Methods**: Podcasting 2.0, AssemblyAI, OpenAI Whisper
- ✅ **AI-Generated LinkedIn Posts**: 3 drafts per episode
- ✅ **Progress Tracking**: Avoids processing duplicate episodes
- ✅ **Real-time Status**: See run logs and results
- ✅ **File Management**: Browse transcripts and LinkedIn drafts

## 🎯 How Users Will Use Your App

1. **Visit your Streamlit app URL**
2. **Enter API keys** (OpenAI required, AssemblyAI optional)
3. **Configure podcast** (Apple Podcasts URL or Show ID)
4. **Click "Run Pull Now"** to fetch new episodes
5. **Browse results** in the transcripts and LinkedIn drafts sections

## 🔄 Automatic Scheduling (Local Only)

For automatic checking every 6 hours on your local machine:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\schedule_task_6hours.ps1 -StartHour 0
```

This creates a Windows Task Scheduler job that runs every 6 hours.

## 📊 Monitoring

- **Streamlit Community Cloud**: Provides built-in monitoring and logs
- **Local**: Check Windows Task Scheduler for scheduled runs
- **App Logs**: Available in the Streamlit interface

## 🛠️ Troubleshooting

### Common Issues:
1. **API Key Errors**: Make sure OpenAI API key is valid and has credits
2. **Network Issues**: Check internet connection for podcast feed access
3. **File Permissions**: Ensure the app can write to data directories

### Support:
- Check the Streamlit Community Cloud logs
- Review the app's "Last Run Output" section
- Verify API keys and network connectivity

## 🎉 Success!

Your podcast transcript puller is now live and ready to use! Users can access it from anywhere and automatically generate LinkedIn content from podcast episodes.
