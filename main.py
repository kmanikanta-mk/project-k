
from model import ask_local_model, check_ollama
from tools import (
    add_task,
    list_tasks,
    complete_task,
    save_memory,
    list_memories,
    search_memory,
    delete_memory,
    summarize_file
)

SYSTEM_PROMPT = """
You are a helpful offline personal AI assistant.
Explain things simply. Help users with learning,
planning, project notes, and everyday questions.
Do not claim to have saved information unless a tool
confirms it.
"""


def main():
    print("\n================================")
    print("   OFFLINE AI PERSONAL ASSISTANT")
    print("================================")
    print("Type /help to see commands.")
    print("Type /exit to quit.\n")

    if check_ollama():
        print("Local AI: Connected\n")
    else:
        print("Local AI: Not connected. Check Ollama.\n")

    while True:
        try:
            message = input("You > ").strip()

            if not message:
                continue

            command = message.lower()

            if command == "/exit":
                print("Goodbye!")
                break

            elif command == "/help":
                print("""
Commands:
  /task add       Add a task
  /task list      Show tasks
  /task done      Complete a task
  /memory save    Save a memory
  /memory list    View memories
  /memory search  Search memories
  /memory delete  Delete a memory
  /summarize      Summarize a text or Markdown file
  /help           Show help
  /exit           Exit
""")

            elif command == "/task add":
                title = input("Task title: ").strip()
                due = input("Due date (optional): ").strip() or None
                priority = input(
                    "Priority (low/medium/high): "
                ).strip().lower() or "medium"

                print(add_task(title, due, priority))

            elif command == "/task list":
                tasks = list_tasks()

                if not tasks:
                    print("No tasks yet.")

                for task in tasks:
                    status = (
                        "DONE" if task["completed"] else "TODO"
                    )
                    print(
                        f'[{status}] ID {task["id"]}: '
                        f'{task["title"]} | '
                        f'Priority: {task["priority"]} | '
                        f'Due: {task["due_date"] or "None"}'
                    )

            elif command == "/task done":
                try:
                    task_id = int(input("Task ID: "))
                    print(complete_task(task_id))
                except ValueError:
                    print("Enter a valid numeric task ID.")

            elif command == "/memory save":
                content = input("Memory to save: ").strip()
                print(save_memory(content))

            elif command == "/memory list":
                memories = list_memories()

                if not memories:
                    print("No saved memories.")

                for memory in memories:
                    print(
                        f'ID {memory["id"]}: {memory["content"]}'
                    )

            elif command == "/memory search":
                query = input("Search for: ").strip()
                results = search_memory(query)

                if not results:
                    print("No matching memories.")

                for memory in results:
                    print(
                        f'ID {memory["id"]}: {memory["content"]}'
                    )

            elif command == "/memory delete":
                try:
                    memory_id = int(input("Memory ID: "))
                    print(delete_memory(memory_id))
                except ValueError:
                    print("Enter a valid numeric memory ID.")

            elif command == "/summarize":
                path = input("Full path to .txt or .md file: ")
                print(summarize_file(path))

            else:
                print("Assistant > ", end="", flush=True)
                answer = ask_local_model(message, SYSTEM_PROMPT)
                print(answer)

        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break


if __name__ == "__main__":
    main()
