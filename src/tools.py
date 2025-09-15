from strands import Agent, tool
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient
from mcp import stdio_client, StdioServerParameters
from strands_tools import shell, file_write, editor
from .prompts import CODE_ANALYSIS_PROMPT, CODE_WRITER_PROMPT

@tool
def code_reader(repo_path: str) -> str:
    """
    Code reader specialist that can search through a repository and find relevant content.
    
    Args:
        repo_path: The repository path of the repository to analyze
        
    Returns:
        Reading findings
    """
    bedrock_model = BedrockModel(model_id="us.anthropic.claude-sonnet-4-20250514-v1:0")

    try:
        env = {
            "FASTMCP_LOG_LEVEL": "DEBUG",
            "AWS_PROFILE": "eldimi-Admin",
            "AWS_REGION": "us-east-1",
        }

        git_repo_mcp_server = MCPClient(
            lambda: stdio_client(
                StdioServerParameters(
                    command="uvx",
                    args=["awslabs.git-repo-research-mcp-server@latest"],
                    env=env,
                )
            )
        )

        with git_repo_mcp_server:
            tools = git_repo_mcp_server.list_tools_sync()
            code_reader_agent = Agent(
                model=bedrock_model,
                system_prompt=CODE_ANALYSIS_PROMPT,
                tools=tools,
            )

            result = str(code_reader_agent(repo_path))
            return result
            
    except Exception as e:
        print(f"Exception in write_new_content: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return f"Error processing your query: {str(e)}"

@tool
def code_converter(data: str) -> str:
    """
    Converts PostgreSQL analytics queries to ClickHouse analytics queries.
    
    Args:
        data: the file paths, code and code description
        
    Returns:
        The converted queries
    """
    code_converter_agent = Agent(
        system_prompt="""You are a ClickHouse developer.
        I will give some existing postgres queries and 
        you need to convert them to ClickHouse queries""",
    )
    
    result = code_converter_agent(data)
    return str(result)

@tool
def code_writer(repo_path: str, converted_code: str) -> str:
    """
    Writes new code in the repository given the provided converted_code queries
    
    Args:
        repo_path: The path of the repository to write the code to
        converted_code: the converted queries
        
    Returns:
        The converted code diff
    """
    try:
        code_writer_agent = Agent(
            system_prompt=CODE_WRITER_PROMPT,
            tools=[shell, file_write, editor]
        )

        result = code_writer_agent(
            f"In the repository located in {repo_path}, replace the postgres queries with the following clickhouse queries: {converted_code}"
        )
        return str(result)
        
    except Exception as e:
        return f"Error processing your query: {str(e)}"