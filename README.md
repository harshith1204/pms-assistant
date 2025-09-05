# MongoDB Project Management System

A modern web-based project management system powered by MongoDB, FastAPI, and an AI assistant using LangGraph and MCP (Model Context Protocol).

## Features

### 🎯 Core Features
- **Project Management**: Create, update, delete, and track projects with status, priority, team members, and budget
- **Task Management**: Manage tasks across projects with assignment, due dates, and status tracking
- **AI Assistant**: Natural language interface for querying and managing your data
- **Real-time Dashboard**: View statistics and recent activity at a glance
- **Responsive Design**: Works seamlessly on desktop and mobile devices

### 🤖 AI Capabilities
- Natural language queries to find projects and tasks
- Intelligent data filtering and searching
- Automated task suggestions and insights
- Context-aware responses using MongoDB data

## Prerequisites

- Python 3.8+
- MongoDB instance (local or cloud)
- Ollama (for AI model) - Install from https://ollama.ai
- Node.js and npm (for MCP server)

## Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd pms-assistant
   ```

2. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up Ollama**
   ```bash
   # Install Ollama from https://ollama.ai
   # Pull the required model
   ollama pull qwen3:0.6b-fp16
   ```

4. **Configure MongoDB connection**
   
   Update the MongoDB connection string in `mongodb_agent.py`:
   ```python
   "MONGODB_CONNECTION_STRING": "your_connection_string_here"
   ```
   
   Or use the Smithery configuration (already configured in the code).

## Running the Application

1. **Start the web server**
   ```bash
   python app.py
   ```
   
   Or with uvicorn for development:
   ```bash
   uvicorn app:app --reload --host 0.0.0.0 --port 8000
   ```

2. **Access the application**
   
   Open your browser and navigate to: http://localhost:8000

## Usage

### Dashboard
- View overall statistics of your projects and tasks
- See recent activity and updates
- Quick access to all major features

### Projects
- Click "New Project" to create a project
- Set status: Planning, Active, In Progress, Completed, or On Hold
- Assign team members and set budgets
- Track progress with visual progress bars
- Filter by status and priority

### Tasks
- Create tasks and assign them to projects
- Set priorities and due dates
- Assign tasks to team members
- Track status: Pending, In Progress, Completed, or Blocked
- Filter by project and status

### AI Assistant
- Ask natural language questions like:
  - "Show me all active projects"
  - "Find high priority tasks"
  - "List projects with budget over 50000"
  - "What tasks are assigned to John?"
- The AI understands context and can perform complex queries

## API Endpoints

### Projects
- `GET /api/projects` - Get all projects
- `POST /api/projects` - Create a new project
- `GET /api/projects/{project_name}` - Get specific project
- `PUT /api/projects/{project_name}` - Update project
- `DELETE /api/projects/{project_name}` - Delete project

### Tasks
- `GET /api/tasks` - Get all tasks
- `POST /api/tasks` - Create a new task
- `PUT /api/tasks/{task_id}` - Update task
- `DELETE /api/tasks/{task_id}` - Delete task

### Other
- `GET /api/stats` - Get database statistics
- `POST /api/agent/query` - Send query to AI assistant

## Architecture

### Backend
- **FastAPI**: Modern, fast web framework for building APIs
- **MongoDB**: NoSQL database for flexible data storage
- **LangGraph**: AI agent orchestration framework
- **MCP**: Model Context Protocol for MongoDB integration
- **Ollama**: Local LLM for natural language processing

### Frontend
- **HTML5/CSS3**: Modern, semantic markup
- **JavaScript**: Vanilla JS for dynamic interactions
- **Responsive Design**: Mobile-first approach
- **Font Awesome**: Icon library

## Development

### Running in Interactive Mode
```bash
python example_usage.py --interactive
```

### Running Example Operations
```bash
python example_usage.py
```

## Troubleshooting

### MongoDB Connection Issues
- Ensure MongoDB is running and accessible
- Check connection string format
- Verify database permissions

### AI Assistant Not Responding
- Ensure Ollama is running: `ollama serve`
- Check if the model is downloaded: `ollama list`
- Verify the model name in `mongodb_agent.py`

### Web Interface Issues
- Clear browser cache
- Check browser console for errors
- Ensure all static files are served correctly

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License.

## Acknowledgments

- Built with LangGraph and LangChain
- MongoDB MCP server by MongoDB
- UI inspired by modern project management tools