# Quick Start Guide

## 🚀 Get Started in 5 Minutes

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Install Ollama
Download from: https://ollama.ai

### 3. Pull AI Model
```bash
ollama pull qwen3:0.6b-fp16
```

### 4. Configure MongoDB
Option A: Use Smithery (already configured)
- No additional setup needed!

Option B: Use your own MongoDB
- Edit `mongodb_agent.py` line 20:
  ```python
  "MONGODB_CONNECTION_STRING": "your_connection_string_here"
  ```

### 5. Start the Application
```bash
./run.sh
```

Or manually:
```bash
python app.py
```

### 6. Open Your Browser
Navigate to: http://localhost:8000

## 🎯 First Steps

1. **Create Your First Project**
   - Click "New Project" in the Projects tab
   - Fill in project details
   - Click "Save Project"

2. **Add Tasks**
   - Go to Tasks tab
   - Click "New Task"
   - Select your project
   - Add task details

3. **Try the AI Assistant**
   - Click on "AI Assistant" tab
   - Ask questions like:
     - "Show me all projects"
     - "Find high priority tasks"
     - "Create a new project called Website Redesign"

## 🔧 Troubleshooting

**MongoDB Connection Failed?**
- Check your connection string
- Ensure MongoDB is running
- Try the Smithery option (pre-configured)

**AI Not Responding?**
```bash
# Check if Ollama is running
ollama list

# If not, start it
ollama serve
```

**Port Already in Use?**
```bash
# Use a different port
uvicorn app:app --port 8001
```

## 📱 Mobile Access
The UI is fully responsive! Access from any device on your network:
```
http://YOUR_IP_ADDRESS:8000
```

## 🎉 That's It!
You're ready to manage projects with AI assistance!