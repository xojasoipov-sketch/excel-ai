import os
from typing import List, Dict, Any
from openai import OpenAI
from dotenv import load_dotenv
import json

from . import config

load_dotenv()

class ExcelAgent:
    def __init__(self):
        # Both DeepSeek/B.AI and Gemini expose an OpenAI-compatible Chat
        # Completions API, so both providers are just (client, model) pairs here.
        # DeepSeek/B.AI is primary; Gemini (if configured) is a fallback that
        # kicks in automatically when the primary call fails (e.g. the primary
        # account runs out of credit) — see _create_completion.
        self.providers = []

        primary_key = os.getenv("DEEPSEEK_API_KEY")
        if primary_key:
            self.providers.append({
                "name": "deepseek",
                "model": os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
                "client": OpenAI(
                    api_key=primary_key,
                    base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
                ),
            })

        # Gemini's settings also resolve from the app_config table, so this key
        # can be added/rotated without a redeploy (see app/config.py).
        fallback_key = config.get("GEMINI_API_KEY")
        if fallback_key:
            self.providers.append({
                "name": "gemini",
                "model": config.get("GEMINI_MODEL", "gemini-3.6-flash"),
                "client": OpenAI(
                    api_key=fallback_key,
                    base_url=config.get(
                        "GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/"
                    ),
                ),
            })

        if not self.providers:
            raise RuntimeError(
                "No AI provider configured. Set DEEPSEEK_API_KEY and/or GEMINI_API_KEY in backend/.env."
            )

        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "read_excel_range",
                    "description": "Read a range of cells from the Excel file.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "range": {"type": "string", "description": "Excel range (e.g., 'A1:B5')"}
                        },
                        "required": ["range"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "save_excel",
                    "description": "Save the current Excel file.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "read_cell",
                    "description": "Read a single cell from the Excel file.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "cell": {"type": "string", "description": "Excel cell reference (e.g., 'A1')"},
                            "row": {"type": "integer", "description": "Zero-based row index"},
                            "col": {"type": "integer", "description": "Zero-based column index"}
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "update_cell",
                    "description": "Update a single cell in the Excel file.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "value": {"type": "string", "description": "New value for the cell"},
                            "cell": {"type": "string", "description": "Excel cell reference (e.g., 'A1')"},
                            "row": {"type": "integer", "description": "Zero-based row index"},
                            "col": {"type": "integer", "description": "Zero-based column index"}
                        },
                        "required": ["value"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "update_range",
                    "description": "Update a range of cells in the Excel file.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "range": {"type": "string", "description": "Excel range (e.g., 'A1:B5')"},
                            "values": {
                                "type": "array",
                                "description": "2D array of values to set in the range",
                                "items": {
                                    "type": "array",
                                    "items": {"type": "string"}
                                }
                            }
                        },
                        "required": ["range", "values"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "find_and_replace",
                    "description": "Find and replace values in the Excel file.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "find": {"type": "string", "description": "Value to find"},
                            "replace": {"type": "string", "description": "Value to replace with"},
                            "range": {"type": "string", "description": "Optional Excel range (e.g., 'A1:B5')"}
                        },
                        "required": ["find", "replace"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "summarize_range",
                    "description": "Perform a summary operation on a range of cells.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "range": {"type": "string", "description": "Excel range (e.g., 'A1:B5')"},
                            "operation": {
                                "type": "string",
                                "description": "Summary operation to perform",
                                "enum": ["sum", "avg", "min", "max"]
                            }
                        },
                        "required": ["range", "operation"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "insert_row_or_col",
                    "description": "Insert rows or columns in the Excel file.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string", "description": "Type to insert", "enum": ["row", "column"]},
                            "index": {"type": "integer", "description": "Zero-based index to insert at"},
                            "count": {"type": "integer", "description": "Number of rows/columns to insert"}
                        },
                        "required": ["type", "index"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "delete_row_or_col",
                    "description": "Delete rows or columns from the Excel file.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string", "description": "Type to delete", "enum": ["row", "column"]},
                            "index": {"type": "integer", "description": "Zero-based index to delete from"},
                            "count": {"type": "integer", "description": "Number of rows/columns to delete"}
                        },
                        "required": ["type", "index"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "read_sheet_metadata",
                    "description": "Read metadata about the Excel sheet.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_column_values",
                    "description": "Get all values in a column.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "index": {"type": "integer", "description": "Zero-based column index"}
                        },
                        "required": ["index"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "filter_rows",
                    "description": "Filter rows where column matches a value.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "col_index": {"type": "integer", "description": "Column index to filter on"},
                            "value": {"type": "string", "description": "Value to match"}
                        },
                        "required": ["col_index", "value"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_last_filled_row_index",
                    "description": "Returns the index after the last filled row in the Excel sheet",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            }
        ]

    def _create_completion(self, **kwargs):
        """Tries each configured provider in order (DeepSeek/B.AI first, then
        Gemini) and returns the first one that succeeds. Only raises once every
        provider has failed, so a single account running dry or being briefly
        down doesn't take the whole assistant down with it."""
        last_error = None
        for provider in self.providers:
            try:
                return provider["client"].chat.completions.create(model=provider["model"], **kwargs)
            except Exception as e:
                print(f"AI provider '{provider['name']}' failed ({e}); trying next provider if configured.")
                last_error = e
        raise last_error

    def quick_chat(self, message_history: List[Dict[str, Any]]) -> str:
        """
        Plain formula-chat with no uploaded file and no tools: the user describes
        their columns in words and the model replies with a formula. Used by the
        fileless "Chat rejimi" described in the product concept.
        """
        response = self._create_completion(messages=message_history)
        return response.choices[0].message.content

    def call_agent(self, message_history: List[Dict[str, Any]], excel_utils):
        """
        Loop until the LLM completes all tool calls and gives a final assistant response.
        """
        write_functions = {"update_cell", "update_range", "insert_row_or_col", "delete_row_or_col", "find_and_replace"}
        all_messages = message_history.copy()
        excel_modified = False

        while True:
            response = self._create_completion(messages=all_messages, tools=self.tools, tool_choice="auto")
            msg = response.choices[0].message

            if msg.tool_calls:
                results = []
                for tool_call in msg.tool_calls:
                    fn_name = tool_call.function.name
                    args = json.loads(tool_call.function.arguments)
                    print(f"Function: {fn_name}, Args: {args}")

                    try:
                        result = getattr(excel_utils, fn_name)(**args)
                        if fn_name in write_functions:
                            excel_modified = True

                        # Ensure JSON serializable
                        if hasattr(result, 'isoformat'):
                            result = result.isoformat()
                        elif not isinstance(result, (str, int, float, bool, type(None))):
                            result = str(result)

                    except Exception as e:
                        print(f"Error: {str(e)}")
                        result = f"❌ Error executing {fn_name}: {str(e)}"

                    results.append({
                        "tool_call_id": tool_call.id,
                        "output": result
                    })

                # Add tool call and tool results to message history
                tool_messages = [{
                    "tool_call_id": r["tool_call_id"],
                    "role": "tool",
                    "name": msg.tool_calls[i].function.name,
                    "content": str(r["output"])
                } for i, r in enumerate(results)]

                all_messages.append(msg)  # tool call message
                all_messages.extend(tool_messages)

            else:
                # Assistant has responded with final message, no more tool calls
                return msg.content, excel_modified
