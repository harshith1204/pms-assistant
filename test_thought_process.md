# Testing Thought Process Messages

## Test Instructions

1. Open the application in your browser (typically http://localhost:5173)
2. Open the browser's Developer Console (F12) to see the debug logs
3. Send a message that would trigger a thought process, for example:
   - "How many work items are there in the Simpo project?"
   - "Show me detailed work item breakdown for Simpo project"

## What to Look For

1. **During Streaming**: You should see the thought process message appearing in a special "Thought Process" bubble while the response is being generated
2. **After Response**: The thought process message should remain visible (not disappear)
3. **Console Logs**: Check for logs showing:
   - "Adding thought message on </think>:" or "Adding thought message on llm_end:"
   - Message counts and types before and after adding thought messages
   - "All messages:" and "Filtered messages:" logs showing the current state

## Toggle Visibility

- Use the "Hide/Show Thinking" button at the bottom of the chat interface to toggle thought message visibility
- When hidden, thought messages should not be displayed but should still exist in the messages array (check console logs)

## Expected Behavior

1. Thought messages are wrapped in `<think>` and `</think>` tags by the LLM
2. The frontend parses these tags and displays the content in a special thought bubble
3. Thought messages persist after the response is complete
4. Thought messages can be toggled on/off without being lost

## Debugging

If thought messages are still disappearing:
1. Check if the LLM is actually generating `<think>` tags
2. Look for any console errors
3. Verify the message types in the console logs
4. Check if the showThinking state is changing unexpectedly