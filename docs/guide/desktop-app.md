# Desktop App

Veil includes a Gradio-based desktop application for privacy-preserving LLM chat.

## Launching the App

### From CLI

```bash
# Default launch
veil app

# Custom port
veil app --port 8080

# Create public shareable link
veil app --share
```

### From Python

```python
from veil.app import launch_app

# Launch with defaults
launch_app()

# Custom configuration
launch_app(
    share=False,
    server_port=7860,
    server_name="127.0.0.1",
)
```

## User Interface

The app has three main tabs:

### Chat Tab

The main chat interface where you interact with LLMs.

**Features:**

- **Message Input**: Type your message containing any sensitive information
- **Chat History**: View the conversation with the LLM
- **Status Bar**: Shows how many entities were anonymized
- **Anonymization Details Panel**:
  - **Anonymized Input**: What was actually sent to the LLM
  - **Raw Response**: The LLM's response (with tokens)
- **Clear Chat**: Reset the conversation and mappings

### Settings Tab

Configure your LLM provider and privacy settings.

#### LLM Configuration

| Setting | Description |
|---------|-------------|
| Provider | OpenAI, Anthropic, or Ollama |
| API Key | Your provider's API key |
| Model | Model to use (e.g., gpt-4o-mini) |
| Base URL | Custom endpoint (for Ollama or proxies) |
| Temperature | Response randomness (0-2) |
| Max Tokens | Maximum response length |

#### Privacy Settings

| Setting | Description |
|---------|-------------|
| Detection Profile | Paranoid, Balanced, or Minimal |
| Detection Mode | Hybrid or Standard |
| Replacement Mode | Token, Faker, or Semantic |
| Use Presidio | Enable Microsoft Presidio detection |
| System Prompt | Custom instructions for the AI |

### About Tab

Information about Veil and how it works.

## Configuration

Settings are automatically saved to:

- Linux: `~/.config/veil/settings.json`
- macOS: `~/Library/Application Support/veil/settings.json`
- Windows: `%APPDATA%/veil/settings.json`

## Using with Different Providers

### OpenAI

1. Go to Settings tab
2. Select "OpenAI" as provider
3. Enter your OpenAI API key
4. Select model (e.g., gpt-4o-mini, gpt-4)
5. Click "Save LLM Settings"

### Anthropic (Claude)

1. Select "Anthropic" as provider
2. Enter your Anthropic API key
3. Select model (e.g., claude-sonnet-4-20250514)
4. Click "Save LLM Settings"

### Ollama (Local)

1. Start Ollama server: `ollama serve`
2. Pull a model: `ollama pull llama3.2`
3. In Veil app:
   - Select "Ollama (Local)" as provider
   - No API key needed
   - Select or type model name
   - Base URL defaults to `http://localhost:11434`
4. Click "Test Connection" to verify

## Test Connection

Before chatting, use the "Test Connection" button to verify your LLM configuration works.

## Privacy Workflow

When you send a message:

1. **Detection**: Veil scans for sensitive entities
2. **Anonymization**: Entities are replaced with tokens
3. **Transmission**: Anonymized text is sent to the LLM
4. **Response**: LLM responds using the tokens
5. **Reconstruction**: Original values are restored in the response

You can see each step in the "Anonymization Details" panel.

## Example Session

**You type:**
```
My name is Sarah Connor, email sarah@skynet.com.
Help me write a professional bio.
```

**Anonymized (sent to LLM):**
```
My name is [PERSON_1], email [EMAIL_1].
Help me write a professional bio.
```

**Raw LLM Response:**
```
Here's a professional bio for [PERSON_1]:

[PERSON_1] is a dedicated professional who can be reached at [EMAIL_1]...
```

**Final Response (you see):**
```
Here's a professional bio for Sarah Connor:

Sarah Connor is a dedicated professional who can be reached at sarah@skynet.com...
```

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Enter | Send message |
| Shift+Enter | New line in message |

## Troubleshooting

### App won't start

```bash
# Check if port is in use
lsof -i :7860

# Try different port
veil app --port 8080
```

### Connection test fails

- Verify API key is correct
- Check internet connection
- For Ollama: ensure server is running (`ollama serve`)

### No entities detected

- Try "Paranoid" profile for more sensitive detection
- Enable "Hybrid" mode and "Use Presidio" for better coverage
