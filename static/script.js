// Global state
let currentView = 'dashboard';
let projects = [];
let tasks = [];
let editingProject = null;
let editingTask = null;

// API Base URL
const API_BASE = '/api';

// Initialize the app
document.addEventListener('DOMContentLoaded', () => {
    // Navigation handling
    document.querySelectorAll('.nav-link').forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            switchView(link.dataset.view);
        });
    });

    // Button event listeners
    document.getElementById('refresh-stats').addEventListener('click', loadDashboard);
    document.getElementById('add-project-btn').addEventListener('click', () => openProjectModal());
    document.getElementById('add-task-btn').addEventListener('click', () => openTaskModal());
    document.getElementById('send-message').addEventListener('click', sendChatMessage);
    
    // Form submissions
    document.getElementById('project-form').addEventListener('submit', handleProjectSubmit);
    document.getElementById('task-form').addEventListener('submit', handleTaskSubmit);
    
    // Filter listeners
    document.getElementById('project-status-filter').addEventListener('change', filterProjects);
    document.getElementById('project-priority-filter').addEventListener('change', filterProjects);
    document.getElementById('task-project-filter').addEventListener('change', filterTasks);
    document.getElementById('task-status-filter').addEventListener('change', filterTasks);
    
    // Chat input enter key
    document.getElementById('chat-input').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            sendChatMessage();
        }
    });

    // Initial load
    loadDashboard();
});

// View switching
function switchView(view) {
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
    
    document.getElementById(`${view}-view`).classList.add('active');
    document.querySelector(`[data-view="${view}"]`).classList.add('active');
    
    currentView = view;
    
    // Load data for the view
    switch(view) {
        case 'dashboard':
            loadDashboard();
            break;
        case 'projects':
            loadProjects();
            break;
        case 'tasks':
            loadTasks();
            break;
    }
}

// Dashboard functions
async function loadDashboard() {
    try {
        const response = await fetch(`${API_BASE}/stats`);
        if (!response.ok) throw new Error('Failed to load stats');
        
        const stats = await response.json();
        
        document.getElementById('total-projects').textContent = stats.total_projects;
        document.getElementById('active-projects').textContent = stats.active_projects;
        document.getElementById('total-tasks').textContent = stats.total_tasks;
        document.getElementById('completed-tasks').textContent = stats.completed_tasks;
        
        // Load recent activity
        await loadRecentActivity();
    } catch (error) {
        console.error('Error loading dashboard:', error);
        showNotification('Failed to load dashboard', 'error');
    }
}

async function loadRecentActivity() {
    try {
        // Get recent projects
        const projectsResponse = await fetch(`${API_BASE}/projects`);
        const allProjects = await projectsResponse.json();
        
        // Get recent tasks
        const tasksResponse = await fetch(`${API_BASE}/tasks`);
        const allTasks = await tasksResponse.json();
        
        // Combine and sort by creation date
        const activities = [];
        
        allProjects.slice(0, 3).forEach(project => {
            activities.push({
                type: 'project',
                title: project.name,
                description: `New project created: ${project.description}`,
                date: project.created_at || new Date().toISOString()
            });
        });
        
        allTasks.slice(0, 3).forEach(task => {
            activities.push({
                type: 'task',
                title: task.title,
                description: `Task added to ${task.project_name}`,
                date: task.created_at || new Date().toISOString()
            });
        });
        
        // Sort by date
        activities.sort((a, b) => new Date(b.date) - new Date(a.date));
        
        // Display activities
        const activityContainer = document.getElementById('recent-activity');
        activityContainer.innerHTML = activities.slice(0, 5).map(activity => `
            <div class="activity-item">
                <strong>${activity.title}</strong>
                <p>${activity.description}</p>
                <small>${formatDate(activity.date)}</small>
            </div>
        `).join('') || '<p>No recent activity</p>';
    } catch (error) {
        console.error('Error loading recent activity:', error);
    }
}

// Projects functions
async function loadProjects() {
    try {
        const response = await fetch(`${API_BASE}/projects`);
        if (!response.ok) throw new Error('Failed to load projects');
        
        projects = await response.json();
        displayProjects(projects);
    } catch (error) {
        console.error('Error loading projects:', error);
        showNotification('Failed to load projects', 'error');
    }
}

function displayProjects(projectsToDisplay) {
    const container = document.getElementById('projects-list');
    
    if (projectsToDisplay.length === 0) {
        container.innerHTML = '<p>No projects found. Create your first project!</p>';
        return;
    }
    
    container.innerHTML = projectsToDisplay.map(project => `
        <div class="project-card">
            <div class="project-header">
                <div>
                    <h3 class="project-title">${project.name}</h3>
                    <div class="project-badges">
                        <span class="status-badge status-${project.status}">${formatStatus(project.status)}</span>
                        <span class="priority-badge priority-${project.priority}">${project.priority}</span>
                    </div>
                </div>
                <div class="project-actions">
                    <button class="icon-btn" onclick="editProject('${project.name}')">
                        <i class="fas fa-edit"></i>
                    </button>
                    <button class="icon-btn danger" onclick="deleteProject('${project.name}')">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </div>
            
            <p class="project-description">${project.description}</p>
            
            <div class="project-meta">
                <div class="meta-item">
                    <i class="fas fa-calendar"></i>
                    ${formatDate(project.start_date)}
                </div>
                ${project.end_date ? `
                    <div class="meta-item">
                        <i class="fas fa-flag-checkered"></i>
                        ${formatDate(project.end_date)}
                    </div>
                ` : ''}
                ${project.budget ? `
                    <div class="meta-item">
                        <i class="fas fa-dollar-sign"></i>
                        ${formatCurrency(project.budget)}
                    </div>
                ` : ''}
            </div>
            
            ${project.team_members && project.team_members.length > 0 ? `
                <div class="project-team">
                    ${project.team_members.map(member => `
                        <span class="team-member">${member}</span>
                    `).join('')}
                </div>
            ` : ''}
            
            ${project.progress !== undefined ? `
                <div class="project-progress">
                    <div class="progress-label">
                        <span>Progress</span>
                        <span>${project.progress}%</span>
                    </div>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: ${project.progress}%"></div>
                    </div>
                </div>
            ` : ''}
        </div>
    `).join('');
}

function filterProjects() {
    const statusFilter = document.getElementById('project-status-filter').value;
    const priorityFilter = document.getElementById('project-priority-filter').value;
    
    let filtered = projects;
    
    if (statusFilter) {
        filtered = filtered.filter(p => p.status === statusFilter);
    }
    
    if (priorityFilter) {
        filtered = filtered.filter(p => p.priority === priorityFilter);
    }
    
    displayProjects(filtered);
}

// Tasks functions
async function loadTasks() {
    try {
        const response = await fetch(`${API_BASE}/tasks`);
        if (!response.ok) throw new Error('Failed to load tasks');
        
        tasks = await response.json();
        displayTasks(tasks);
        
        // Update project filter
        await updateProjectFilter();
    } catch (error) {
        console.error('Error loading tasks:', error);
        showNotification('Failed to load tasks', 'error');
    }
}

async function updateProjectFilter() {
    try {
        const response = await fetch(`${API_BASE}/projects`);
        const projects = await response.json();
        
        const filterSelect = document.getElementById('task-project-filter');
        const taskProjectSelect = document.getElementById('task-project');
        
        const projectOptions = projects.map(p => 
            `<option value="${p.name}">${p.name}</option>`
        ).join('');
        
        filterSelect.innerHTML = '<option value="">All Projects</option>' + projectOptions;
        taskProjectSelect.innerHTML = '<option value="">Select a project</option>' + projectOptions;
    } catch (error) {
        console.error('Error updating project filter:', error);
    }
}

function displayTasks(tasksToDisplay) {
    const container = document.getElementById('tasks-list');
    
    if (tasksToDisplay.length === 0) {
        container.innerHTML = '<p>No tasks found. Create your first task!</p>';
        return;
    }
    
    container.innerHTML = tasksToDisplay.map(task => `
        <div class="task-item">
            <div class="task-content">
                <h4 class="task-title">${task.title}</h4>
                ${task.description ? `<p>${task.description}</p>` : ''}
                <div class="task-meta">
                    <div class="meta-item">
                        <i class="fas fa-project-diagram"></i>
                        ${task.project_name}
                    </div>
                    ${task.assigned_to ? `
                        <div class="meta-item">
                            <i class="fas fa-user"></i>
                            ${task.assigned_to}
                        </div>
                    ` : ''}
                    ${task.due_date ? `
                        <div class="meta-item">
                            <i class="fas fa-calendar-alt"></i>
                            ${formatDate(task.due_date)}
                        </div>
                    ` : ''}
                </div>
            </div>
            
            <div class="task-actions">
                <span class="status-badge status-${task.status}">${formatStatus(task.status)}</span>
                <span class="priority-badge priority-${task.priority}">${task.priority}</span>
                <button class="icon-btn" onclick="editTask('${task._id || task.title}')">
                    <i class="fas fa-edit"></i>
                </button>
                <button class="icon-btn danger" onclick="deleteTask('${task._id || task.title}')">
                    <i class="fas fa-trash"></i>
                </button>
            </div>
        </div>
    `).join('');
}

function filterTasks() {
    const projectFilter = document.getElementById('task-project-filter').value;
    const statusFilter = document.getElementById('task-status-filter').value;
    
    let filtered = tasks;
    
    if (projectFilter) {
        filtered = filtered.filter(t => t.project_name === projectFilter);
    }
    
    if (statusFilter) {
        filtered = filtered.filter(t => t.status === statusFilter);
    }
    
    displayTasks(filtered);
}

// Modal functions
function openProjectModal(project = null) {
    editingProject = project;
    
    if (project) {
        document.getElementById('project-modal-title').textContent = 'Edit Project';
        document.getElementById('project-name').value = project.name;
        document.getElementById('project-description').value = project.description;
        document.getElementById('project-status').value = project.status;
        document.getElementById('project-priority').value = project.priority;
        document.getElementById('project-start-date').value = project.start_date;
        document.getElementById('project-end-date').value = project.end_date || '';
        document.getElementById('project-team').value = project.team_members ? project.team_members.join(', ') : '';
        document.getElementById('project-budget').value = project.budget || '';
        document.getElementById('project-name').disabled = true;
    } else {
        document.getElementById('project-modal-title').textContent = 'New Project';
        document.getElementById('project-form').reset();
        document.getElementById('project-name').disabled = false;
    }
    
    document.getElementById('project-modal').classList.add('active');
}

function closeProjectModal() {
    document.getElementById('project-modal').classList.remove('active');
    editingProject = null;
}

function openTaskModal(task = null) {
    editingTask = task;
    
    if (task) {
        document.getElementById('task-modal-title').textContent = 'Edit Task';
        document.getElementById('task-title').value = task.title;
        document.getElementById('task-description').value = task.description || '';
        document.getElementById('task-project').value = task.project_name;
        document.getElementById('task-status').value = task.status;
        document.getElementById('task-priority').value = task.priority;
        document.getElementById('task-assigned').value = task.assigned_to || '';
        document.getElementById('task-due-date').value = task.due_date || '';
    } else {
        document.getElementById('task-modal-title').textContent = 'New Task';
        document.getElementById('task-form').reset();
    }
    
    document.getElementById('task-modal').classList.add('active');
}

function closeTaskModal() {
    document.getElementById('task-modal').classList.remove('active');
    editingTask = null;
}

// Form handlers
async function handleProjectSubmit(e) {
    e.preventDefault();
    
    const formData = new FormData(e.target);
    const projectData = {
        name: formData.get('name'),
        description: formData.get('description'),
        status: formData.get('status'),
        priority: formData.get('priority'),
        start_date: formData.get('start_date'),
        end_date: formData.get('end_date') || null,
        team_members: formData.get('team_members') ? 
            formData.get('team_members').split(',').map(m => m.trim()) : [],
        budget: formData.get('budget') ? parseFloat(formData.get('budget')) : null
    };
    
    try {
        let response;
        if (editingProject) {
            // Update existing project
            response = await fetch(`${API_BASE}/projects/${editingProject.name}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(projectData)
            });
        } else {
            // Create new project
            response = await fetch(`${API_BASE}/projects`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(projectData)
            });
        }
        
        if (!response.ok) throw new Error('Failed to save project');
        
        showNotification('Project saved successfully', 'success');
        closeProjectModal();
        loadProjects();
    } catch (error) {
        console.error('Error saving project:', error);
        showNotification('Failed to save project', 'error');
    }
}

async function handleTaskSubmit(e) {
    e.preventDefault();
    
    const formData = new FormData(e.target);
    const taskData = {
        title: formData.get('title'),
        description: formData.get('description') || null,
        project_name: formData.get('project_name'),
        status: formData.get('status'),
        priority: formData.get('priority'),
        assigned_to: formData.get('assigned_to') || null,
        due_date: formData.get('due_date') || null
    };
    
    try {
        let response;
        if (editingTask) {
            // Update existing task
            response = await fetch(`${API_BASE}/tasks/${editingTask._id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(taskData)
            });
        } else {
            // Create new task
            response = await fetch(`${API_BASE}/tasks`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(taskData)
            });
        }
        
        if (!response.ok) throw new Error('Failed to save task');
        
        showNotification('Task saved successfully', 'success');
        closeTaskModal();
        loadTasks();
    } catch (error) {
        console.error('Error saving task:', error);
        showNotification('Failed to save task', 'error');
    }
}

// Edit functions
async function editProject(projectName) {
    const project = projects.find(p => p.name === projectName);
    if (project) {
        openProjectModal(project);
    }
}

async function editTask(taskId) {
    const task = tasks.find(t => t._id === taskId || t.title === taskId);
    if (task) {
        openTaskModal(task);
    }
}

// Delete functions
async function deleteProject(projectName) {
    if (!confirm(`Are you sure you want to delete the project "${projectName}"?`)) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/projects/${projectName}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) throw new Error('Failed to delete project');
        
        showNotification('Project deleted successfully', 'success');
        loadProjects();
    } catch (error) {
        console.error('Error deleting project:', error);
        showNotification('Failed to delete project', 'error');
    }
}

async function deleteTask(taskId) {
    if (!confirm('Are you sure you want to delete this task?')) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/tasks/${taskId}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) throw new Error('Failed to delete task');
        
        showNotification('Task deleted successfully', 'success');
        loadTasks();
    } catch (error) {
        console.error('Error deleting task:', error);
        showNotification('Failed to delete task', 'error');
    }
}

// Chat functions
async function sendChatMessage() {
    const input = document.getElementById('chat-input');
    const message = input.value.trim();
    
    if (!message) return;
    
    // Add user message to chat
    addChatMessage(message, 'user');
    input.value = '';
    
    // Send to API
    try {
        const response = await fetch(`${API_BASE}/agent/query`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query: message })
        });
        
        if (!response.ok) throw new Error('Failed to get response');
        
        const data = await response.json();
        addChatMessage(data.response, 'assistant');
    } catch (error) {
        console.error('Error sending message:', error);
        addChatMessage('Sorry, I encountered an error processing your request.', 'assistant');
    }
}

function addChatMessage(content, type) {
    const messagesContainer = document.getElementById('chat-messages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `chat-message ${type}`;
    
    messageDiv.innerHTML = `
        <div class="message-content">
            <p>${content}</p>
        </div>
    `;
    
    messagesContainer.appendChild(messageDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

// Utility functions
function formatDate(dateString) {
    if (!dateString) return '';
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', { 
        year: 'numeric', 
        month: 'short', 
        day: 'numeric' 
    });
}

function formatCurrency(amount) {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD'
    }).format(amount);
}

function formatStatus(status) {
    return status.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
}

function showNotification(message, type = 'info') {
    // Simple notification (you can enhance this with a proper notification library)
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 1rem 2rem;
        background: ${type === 'success' ? '#2dce89' : type === 'error' ? '#f5365c' : '#11cdef'};
        color: white;
        border-radius: 0.375rem;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        z-index: 3000;
    `;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.remove();
    }, 3000);
}