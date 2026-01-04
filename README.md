# DreamMesh - AI-Powered 3D Model Generator

<p align="center">
  <img src="https://img.shields.io/badge/Blender-4+-orange?style=for-the-badge&logo=blender" alt="Blender Version">
  <img src="https://img.shields.io/badge/n8n-Workflow_Automation-red?style=for-the-badge" alt="n8n">
  <img src="https://img.shields.io/badge/AI-LLM_Powered-blue?style=for-the-badge" alt="AI Powered">
  <img src="https://img.shields.io/badge/Python-3.10+-green?style=for-the-badge&logo=python" alt="Python">
</p>

**DreamMesh** is an innovative Blender addon that transforms natural language prompts into sophisticated 3D models using AI. Simply describe what you want to create, and watch as the AI generates production-ready 3D geometry directly in your Blender scene.

**NOTE-** Create 3d models under 5 Rupees(with model like DeepseekV3.2)

## ✨ Features

- 🗣️ **Natural Language to 3D**: Describe your model in plain English
- 🔄 **Two Modes**: Generate new models or update existing scene objects
- 🧠 **Multi-Agent AI Pipeline**: Layout planning → Code generation → Syntax checking → Error fixing
- 🔁 **Auto Error Recovery**: Automatic retry with intelligent error fixing (up to 3 attempts)
- 📊 **Scene Context Awareness**: AI understands your current scene for better results
- ⚡ **Real-time Execution**: Synchronous code execution with immediate visual feedback
- 🎯 **Advanced Geometry**: Uses bmesh for procedural mesh generation (no primitive operators)

---

## 📋 Table of Contents

1. [Prerequisites](#-prerequisites)
2. [Installation](#-installation)
   - [Setting up n8n](#1-setting-up-n8n)
   - [Installing the Blender Addon](#2-installing-the-blender-addon)
   - [Configuring API Keys](#3-configuring-api-keys)
3. [Configuration](#-configuration)
4. [Usage Guide](#-usage-guide)
5. [Workflow Architecture](#-workflow-architecture)
6. [Troubleshooting](#-troubleshooting)

---

## 🔧 Prerequisites

Before you begin, ensure you have:

| Requirement | Minimum Version | Download |
|-------------|-----------------|----------|
| **Blender** | 4+ | [blender.org](https://www.blender.org/download/) |
| **n8n** | Latest | [n8n.io](https://n8n.io/) |
| **Python** | 3.10+ | Included with Blender |
| **OpenAI API Key** | - | [platform.openai.com](https://platform.openai.com/) |
| **OpenRouter API Key** | - | [openrouter.ai](https://openrouter.ai/) |

---

## 📥 Installation

### 1. Setting up n8n

#### Option A: Docker (Recommended)

```bash
docker run -it --rm \
  --name n8n \
  -p 5678:5678 \
  -v n8n_data:/home/node/.n8n \
  n8nio/n8n
```

#### Option B: npm Installation

```bash
npm install n8n -g
n8n start
```

#### Option C: Desktop App

Download the n8n desktop app from [n8n.io/get-started](https://n8n.io/get-started/)

After installation, access n8n at: **http://localhost:5678**

### 2. Importing the DreamMesh Workflow

1. Open n8n in your browser (`http://localhost:5678`)
2. Click **"Add workflow"** → **"Import from file"**
3. Select the workflow file: `N8N workflow/DreamMesh v0.2(final) (2).json`
4. Click **"Import"**

### 3. Configuring API Keys in n8n

The workflow requires two API credentials:

#### OpenAI API (for Layout Generator)

1. In n8n, go to **Settings** → **Credentials**
2. Click **"Add Credential"** → Search for **"OpenAI"**
3. Enter your OpenAI API key
4. Save the credential
5. Connect it to the **"OpenAI Chat Model"** node in the workflow

#### OpenRouter API (for Code Generation & Error Fixing)

1. In n8n, go to **Settings** → **Credentials**
2. Click **"Add Credential"** → Search for **"OpenRouter"**
3. Enter your OpenRouter API key
4. Save the credential
5. Connect it to all **"OpenRouter Chat Model"** nodes:
   - `OpenRouter Chat Model` (Error Fixer)
   - `OpenRouter Chat Model1` (Code Generator)
   - `OpenRouter Chat Model2` (Scene Update Agent)
   - `OpenRouter Chat Model3` (Syntax Checker)

### 4. Activating the Workflow

1. After configuring credentials, click the **"Save"** button
2. Toggle the workflow status to **"Active"** (switch in top-right corner)
3. The webhook will now be listening at: `http://localhost:5678/webhook/process`

### 5. Installing the Blender Addon

1. Open **Blender**
2. Go to **Edit** → **Preferences** → **Add-ons**
3. Click **"Install..."** button (top-right)
4. Navigate to and select: `Addon/addonF2.py`
5. Click **"Install Add-on"**
6. Enable the addon by checking the box next to **"3D View: MODEL GENERATOR"**

---

## ⚙️ Configuration

### Addon Preferences

After enabling the addon, expand it in the preferences to configure:

| Setting | Default | Description |
|---------|---------|-------------|
| **Webhook Port** | `8765` | Port for Blender to listen for n8n responses |
| **Result Webhook URL** | `http://localhost:5678/webhook-test/result` | URL to send results back to n8n |
| **n8n Workflow URL** | `http://localhost:5678/webhook-test/process` | URL to send prompts to n8n |
| **Auto-start Server** | `Off` | Automatically start webhook server on addon enable |
| **Enable Detailed Logging** | `On` | Print detailed logs to console |
| **Max Execution Time** | `30 seconds` | Maximum time for code execution |

### Recommended Settings for Production

```
Webhook Port: 8765
n8n Workflow URL: http://localhost:5678/webhook/process
Result Webhook URL: http://localhost:5678/webhook/result
Max Execution Time: 60
```

---

## 🚀 Usage Guide

### Step 1: Start the Webhook Server

1. In Blender, press `N` to open the sidebar
2. Navigate to the **"DreamMesh"** tab
3. Click **"Start Server"** in the Webhook Server section
4. You should see: *"Listening on port 8765"*

### Step 2: Generate a 3D Model

1. In the **"Generate Model"** section, enter your prompt in the text field
   
   **Example prompts:**
   - `"A medieval castle with towers and a drawbridge"`
   - `"A futuristic spaceship with sleek wings"`
   - `"A simple wooden chair with armrests"`
   - `"An ancient Greek temple with columns"`

2. Select **Complexity Level**:
   - **Simple**: Basic geometric shapes
   - **Medium**: Moderate detail level (recommended)
   - **Complex**: High detail level

3. Enable/disable **"Include Scene Context"** to let the AI understand your current scene

4. Click **"Generate"** to create new objects or **"Update"** to modify existing ones

### Step 3: Monitor Progress

- Watch the **Status** display for real-time feedback
- Check the Blender console (Window → Toggle System Console) for detailed logs
- The AI will automatically retry if errors occur (up to 3 times)

### Generate vs Update Mode

| Mode | Use Case | Scene Context |
|------|----------|---------------|
| **Generate** | Create new 3D models from scratch | Optional - helps with positioning |
| **Update** | Modify existing objects in scene | Required - AI reads current objects |

---

## 🏗️ Workflow Architecture

The DreamMesh workflow uses a multi-agent AI pipeline:

```
┌─────────────────┐
│  User Prompt    │
└────────┬────────┘
         ▼
┌─────────────────┐     ┌──────────────────┐
│ Update or       │────▶│ Scene Update     │ (if update=yes)
│ Create?         │     │ Agent            │
└────────┬────────┘     └──────────────────┘
         ▼ (if create)
┌─────────────────┐
│ Layout          │ ← GPT-5-mini
│ Generator       │   Breaks down into objects
└────────┬────────┘
         ▼
┌─────────────────┐
│ Objects         │ ← Check if objects generated
│ Generated?      │
└────────┬────────┘
         ▼
┌─────────────────┐
│ Loop Objects    │ ← Process each object
└────────┬────────┘
         ▼
┌─────────────────┐
│ Code Generator  │ ← Claude Sonnet 4.5
│                 │   Generates Blender Python
└────────┬────────┘
         ▼
┌─────────────────┐
│ Syntax Checker  │ ← GPT-5.2
│                 │   Validates Python code
└────────┬────────┘
         ▼
┌─────────────────┐
│ Send to         │ ← HTTP POST to Blender
│ Blender         │   Port 8765
└────────┬────────┘
         ▼
┌─────────────────┐     ┌──────────────────┐
│ Code Executed   │─No─▶│ Error Fixer      │ ← Claude Sonnet 4.5
│ OK?             │     │ Agent            │   (max 3 retries)
└────────┬────────┘     └────────┬─────────┘
         │ Yes                    │
         ▼                        │
┌─────────────────┐              │
│ Mark Success    │◀─────────────┘
└────────┬────────┘
         ▼
┌─────────────────┐
│ Merge Results   │ ← Continue to next object
└─────────────────┘
```

### AI Models Used

| Agent | Model | Purpose |
|-------|-------|---------|
| Layout Generator | GPT-5-mini | Breaks prompt into object hierarchy |
| Auto-fix LLM | GPT-5-mini | Fixes JSON parsing errors |
| Code Generator | Claude Sonnet 4.5 | Generates Blender Python code |
| Syntax Checker | GPT-5.2 | Validates and corrects syntax |
| Error Fixer | Claude Sonnet 4.5 | Fixes runtime errors |
| Scene Update Agent | Claude Sonnet 4.5 | Modifies existing objects |

---

## 🐛 Troubleshooting

### Common Issues

#### 1. "Webhook server not running"
**Solution**: Click "Start Server" in the DreamMesh panel before generating.

#### 2. "Failed to send to n8n"
**Solutions**:
- Ensure n8n is running (`http://localhost:5678`)
- Check the workflow is **Active** in n8n
- Verify the n8n Workflow URL in addon preferences
- Click "Test n8n" button to verify connection

#### 3. "Port already in use"
**Solution**: Change the Webhook Port in addon preferences to another value (e.g., 8766)

#### 4. Code execution errors
The addon automatically:
- Categorizes errors (SYNTAX_ERROR, ATTRIBUTE_ERROR, etc.)
- Provides fix suggestions
- Retries up to 3 times with AI-powered corrections

#### 5. n8n credential errors
**Solution**: 
- Go to n8n Settings → Credentials
- Verify all API keys are entered correctly
- Re-connect credentials to the appropriate nodes

### Viewing Logs

- **Blender Console**: Window → Toggle System Console
- **n8n Execution Log**: Click on any execution in n8n to see detailed logs
- **Enable Detailed Logging**: In addon preferences for verbose output

### Error Categories

The addon categorizes execution errors for intelligent retry:

| Category | Description | Auto-Fix Strategy |
|----------|-------------|-------------------|
| `SYNTAX_ERROR` | Python syntax issues | Fix indentation, brackets |
| `ATTRIBUTE_ERROR` | Wrong API calls | Use correct Blender 4.4 API |
| `NAME_ERROR` | Undefined variables | Add missing imports/definitions |
| `CONTEXT_ERROR` | Wrong Blender mode | Switch to correct mode |
| `BMESH_ERROR` | Mesh operation issues | Fix bmesh lifecycle |

---

## 📁 Project Structure

```
buildathon github/
├── Addon/
│   └── addonF2.py          # Blender addon (main file)
├── N8N workflow/
│   └── DreamMesh v0.2(final) (2).json  # n8n workflow
└── README.md               # This file
```

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

---

## 📄 License

This project is open source. See LICENSE file for details.

---

## 🙏 Acknowledgments

- **Blender Foundation** for the amazing 3D software
- **n8n** for the powerful workflow automation
- **OpenAI** and **Anthropic** for the AI models
- **OpenRouter** for unified API access

---

<p align="center">
  Made with ❤️ for the 3D creative community
</p>
