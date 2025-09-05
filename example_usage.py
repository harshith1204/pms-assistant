#!/usr/bin/env python3
"""
Example usage of the MongoDB Agent for Project Management
"""
import asyncio
from mongodb_agent import MongoDBAgent

async def main():
    """Demonstrate MongoDB Agent capabilities"""

    agent = MongoDBAgent()

    try:
        # Connect to MongoDB
        print("🔌 Connecting to MongoDB...")
        await agent.connect()

        print("📊 Starting Project Management Database Operations...\n")

        # Example 1: List collections
        print("1. Listing collections in ProjectManagement database:")
        response = await agent.run("List all collections in the ProjectManagement database")
        print(f"Response: {response}\n")

        # Example 2: Create a projects collection
        print("2. Creating projects collection:")
        response = await agent.run("Create a collection called 'projects' in the ProjectManagement database")
        print(f"Response: {response}\n")

        # Example 3: Insert sample project data
        print("3. Inserting sample project:")
        response = await agent.run("""
        Insert a document into the projects collection with the following data:
        - name: "AI Assistant Development"
        - description: "Building an intelligent assistant for project management"
        - status: "active"
        - priority: "high"
        - start_date: "2024-01-15"
        - team_members: ["Alice", "Bob", "Charlie"]
        - budget: 50000
        """)
        print(f"Response: {response}\n")

        # Example 4: Insert another project
        print("4. Inserting another project:")
        response = await agent.run("""
        Insert a document into the projects collection with:
        - name: "Mobile App Redesign"
        - description: "Redesigning the mobile application UI/UX"
        - status: "planning"
        - priority: "medium"
        - start_date: "2024-02-01"
        - team_members: ["Diana", "Eve"]
        - budget: 75000
        """)
        print(f"Response: {response}\n")

        # Example 5: Find active projects
        print("5. Finding active projects:")
        response = await agent.run("Find all projects with status 'active' in the projects collection")
        print(f"Response: {response}\n")

        # Example 6: Update a project
        print("6. Updating project status:")
        response = await agent.run("""
        Update the project with name 'Mobile App Redesign' to change its status to 'in_progress'
        and add a new team member 'Frank'
        """)
        print(f"Response: {response}\n")

        # Example 7: Find projects by priority
        print("7. Finding high priority projects:")
        response = await agent.run("Find all projects with priority 'high' in the projects collection")
        print(f"Response: {response}\n")

        # Example 8: Create tasks collection
        print("8. Creating tasks collection:")
        response = await agent.run("Create a collection called 'tasks' in the ProjectManagement database")
        print(f"Response: {response}\n")

        # Example 9: Insert sample tasks
        print("9. Inserting sample tasks:")
        response = await agent.run("""
        Insert multiple tasks into the tasks collection:
        1. Task: "Setup development environment" for project "AI Assistant Development", status: "completed"
        2. Task: "Design database schema" for project "AI Assistant Development", status: "in_progress"
        3. Task: "Create wireframes" for project "Mobile App Redesign", status: "pending"
        """)
        print(f"Response: {response}\n")

        print("✅ All operations completed successfully!")

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        print("\n🔌 Disconnecting from MongoDB...")
        await agent.disconnect()

async def interactive_mode():
    """Interactive mode for manual queries"""
    agent = MongoDBAgent()

    try:
        print("🔌 Connecting to MongoDB...")
        await agent.connect()

        print("🤖 MongoDB Agent Interactive Mode")
        print("Type 'exit' to quit")
        print("-" * 40)

        while True:
            query = input("\nEnter your query: ").strip()
            if query.lower() in ['exit', 'quit', 'q']:
                break

            if query:
                print("Processing...")
                response = await agent.run(query)
                print(f"Response: {response}")

    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Error: {str(e)}")
    finally:
        await agent.disconnect()

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        print("Starting interactive mode...")
        asyncio.run(interactive_mode())
    else:
        print("Running example operations...")
        asyncio.run(main())
