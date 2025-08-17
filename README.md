# Mini-Cursor

This project demonstrates a GPT-powered chat agent with **Langfuse tracing** and a simple **Streamlit UI**.

---

⚡ Features

GPT-4o powered chat agent

Context storage

Real-time Langfuse tracing

Streamlit-based frontend

## 🚀 Setup Instructions

### 1. Clone the Repository
```bash
git clone https://github.com/Vinayak-kumar132/mini-cursor.git
cd mini-cursor
```
### 2. Create and Activate Virtual Environment
On Windows:
```bash
python -m venv venv
.\venv\Scripts\activate
```
On Linux / macOS:
```bash
python3 -m venv venv
source venv/bin/activate
```
### 3. Install Dependencies
```bash
pip install -r requirements.txt
```
### 4. Setup Langfuse Locally with Docker Compose

Make sure you have Docker and Docker Compose installed.
Run the following command to start Langfuse:
```bash
docker compose -f docker-compose-langfuse.yml up -d
```
This will start the Langfuse server locally. You can also use langfuse on the cloud and skip step 4

### 5. Create and .env file
Mentioned all the env variable
```env
LANGFUSE_SECRET_KEY=sk-….
LANGFUSE_PUBLIC_KEY=pk-….
LANGFUSE_HOST="https://cloud.langfuse.com"
LANGFUSE_HOST="http://localhost:3000"      if hosted langfuse locally
OPENAI_API_KEY=….
```

### 6. Run the Applications
Start the Backend (FastAPI server):
```bash
uvicorn cursor:app --reload --port 8000
```
Start the UI (Streamlit app):
```bash
streamlit run streamlit_ui.py
```
### You are ready to chat with the Application
