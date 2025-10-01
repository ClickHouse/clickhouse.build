# 💬 Chat UI - Interactive Migration Assistant

The Chat UI provides a modern, conversational interface for the ClickHouse Migration Assistant. It combines real-time step tracking with natural language interaction and inline file approval.

## 🎯 Features

### 📊 **Dual-Panel Layout**
```
┌─────────────────────────────────────────────────────────────┐
│ ClickHouse Migration Assistant - Chat Interface            │
├─────────────────┬───────────────────────────────────────────┤
│ Migration Steps │ Interactive Chat                          │
│                 │                                           │
│ ✅ 1. Install   │ 🤖 Assistant: I found 4 PostgreSQL      │
│    ClickHouse   │    queries in your expense analytics.     │
│                 │    Should I convert them to ClickHouse?   │
│ 🔄 2. Analyze   │                                           │
│    Repository   │ 👤 You: Yes, please show me the diffs    │
│                 │                                           │
│ ⏳ 3. Convert   │ 🤖 Assistant: Here's the conversion:     │
│    Queries      │    📝 File Change Request: route.ts      │
│                 │    - COUNT(*)                             │
│ ⏳ 4. Write     │    + COUNT()                              │
│    Files        │                                           │
│                 │    💬 Type 'y' to approve, 'n' to reject │
│ ⏳ 5. Generate  │                                           │
│    Config       │ 👤 You: y                                 │
│                 │                                           │
│                 │ > Type your message...                    │
└─────────────────┴───────────────────────────────────────────┘
```

### 🚀 **Key Capabilities**

- **📈 Live Step Tracking** - Visual progress indicators for each migration phase
- **💬 Natural Conversation** - Chat directly with the migration orchestrator
- **🔍 Inline Diff Approvals** - See file changes and approve/reject in chat
- **🎨 Rich Formatting** - Syntax highlighting, emojis, and structured content
- **⚡ Real-time Updates** - Steps and chat update simultaneously
- **🎮 Interactive Commands** - Simple text commands for all operations

## 🚀 Getting Started

### Launch Chat UI

```bash
# Start the chat interface
uv run main.py --chat

```

### Basic Commands

Once the chat UI is running, try these commands:

```
migrate     - Start full migration process  
status      - Show current migration progress
help        - Show all available commands
clear       - Clear chat history
```

### Approval System

When the assistant finds files to modify, it will show you:

1. **📝 File Change Request** with the file path
2. **📋 Diff Display** showing before/after changes
3. **💬 Approval Prompt** asking for your decision

**Approve changes:**
- Type: `y`, `yes`, `approve`, `ok`, or `apply`

**Reject changes:**
- Type: `n`, `no`, `reject`, `skip`, or `cancel`

**Approva all following changes:**
- Type: `all`

## 🎮 Interactive Examples

### Example 1: Repository Analysis
```
👤 You: analyze

🤖 Assistant: 🔍 Starting repository analysis...
              I'll scan your codebase for PostgreSQL queries.

ℹ️ System: Scanning TypeScript files...
ℹ️ System: Found PostgreSQL queries in 2 files

🤖 Assistant: 🎯 Analysis Results:
              
              I found 4 PostgreSQL queries that need conversion:
              
              📄 app/api/expenses/route.ts
              • 1 COUNT(*) query for expense totals
              
              📄 app/api/expenses/stats/route.ts  
              • 3 analytics queries with aggregations
              
              Ready to start the migration? Type migrate to begin!
```

### Example 2: File Approval Flow
```
👤 You: migrate

🤖 Assistant: 🔄 Converting Queries
              
              I found a PostgreSQL query that needs conversion:

📝 File Change Request: app/api/expenses/route.ts
Converting COUNT(*) to COUNT() for ClickHouse compatibility

--- a/app/api/expenses/route.ts
+++ b/app/api/expenses/route.ts
@@ -1,4 +1,4 @@
 SELECT 
-  COUNT(*) as count, 
+  COUNT() as count, 
   COALESCE(SUM(amount), 0) as total 
 FROM expenses 

💬 Type 'y' or 'yes' to approve, 'n' or 'no' to reject

👤 You: y

✅ System: Applied changes to app/api/expenses/route.ts

🤖 Assistant: Great! Moving to the next file...
```

## ⌨️ Keyboard Shortcuts

- **Ctrl+L** - Clear chat history
- **Ctrl+Q** - Quit application
- **Escape** - Focus input field
- **Enter** - Send message

## 🎨 Visual Elements

### Step Status Indicators
- Pending - Step not yet started
- Running - Step currently in progress
- Completed - Step finished successfully
- Failed - Step encountered an error
- Skipped - Step was skipped

### Message Types
- **👤 You:** - Your messages (blue styling)
- **🤖 Assistant:** - AI responses (green styling)  
- **ℹ️ System:** - Status updates (cyan styling)
- **📝 File Change Request** - Approval requests (yellow styling)

### Progress Tracking
```
📊 Progress: 3/5 completed
🎯 60% complete
```

## 🔧 Advanced Features

### Status Checking
```
👤 You: status

🤖 Assistant: 📊 Migration Status
              
              📁 Repository: pg-expense-direct
              🎯 Progress: 2/5 steps completed
              🔄 Current Step: 3. Convert Queries
              
              Waiting for approval: Yes
              Pending approvals: 1
```

## 🛠️ Technical Details

### Architecture
- **ChatScreen** - Main screen coordinating panels
- **StepsWidget** - Top panel showing migration progress
- **LogWidget** - Right panel with logs
- **ApprovalWidget** - Inline diff display and approval handling

### Integration Points
- Connects to existing `WorkflowOrchestrator`
- Uses `approval_integration.py` for file operations
- Streams events to both chat and status panels
- Handles approval requests through chat interface

### Error Handling
- Connection errors show in chat with retry options
- File operation errors display inline with suggestions  
- Orchestrator errors provide graceful degradation
- All errors logged for debugging

## 🎯 Use Cases

### Perfect For:
- **Interactive Migration** - When you want control over each change
- **Learning ClickHouse** - See exactly what changes and why
- **Code Review** - Examine diffs before applying changes
- **Selective Migration** - Choose which files to convert

### Workflow:
1. **Start** with `analyze` to see what needs conversion
2. **Review** the analysis results and file list
3. **Begin** migration with `migrate` command
4. **Approve/Reject** each file change as presented
5. **Monitor** progress in the steps panel
6. **Complete** migration with generated config

## 🚀 Next Steps

The Chat UI provides an intuitive way to interact with the migration process. Try it out with:
```bash
uv run main.py
```
or 

```bash
uv run main.py --chat
```

Then type `help` to see all available commands, or `test` to try the approval system!