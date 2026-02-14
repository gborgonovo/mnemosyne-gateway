import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def run():
    # Configure the server parameters
    server_params = StdioServerParameters(
        command="/home/giorgio/Projects/Mnemosyne gateway/.venv/bin/python3",
        args=["/home/giorgio/Projects/Mnemosyne gateway/gateway/mcp_server.py"],
        env={**dict(os.environ), "PYTHONPATH": "/home/giorgio/Projects/Mnemosyne gateway"}
    )

    print("🚀 Connecting to Mnemosyne MCP Server...")
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize
            await session.initialize()
            
            # List Tools
            print("\n🛠️  Available Tools:")
            tools = await session.list_tools()
            for tool in tools.tools:
                print(f"- {tool.name}: {tool.description}")

            # Test add_observation
            print("\n📝 Adding Observation: 'Sto lavorando al progetto Mnemosyne su Arch Linux.'")
            obs_res = await session.call_tool("add_observation", {"content": "Sto lavorando al progetto Mnemosyne su Arch Linux."})
            print(f"Result: {obs_res.content[0].text}")

            # Test query_knowledge
            print("\n🔍 Querying Knowledge: 'Mnemosyne'")
            query_res = await session.call_tool("query_knowledge", {"query": "Mnemosyne"})
            print(f"Result:\n{query_res.content[0].text}")

            # Test get_memory_briefing
            print("\n💡 Getting Memory Briefing")
            brief_res = await session.call_tool("get_memory_briefing", {})
            print(f"Result:\n{brief_res.content[0].text}")

            # Test Helper: Diagnostic Tools
            print("\n🩺 Testing Diagnostic Tools...")
            
            # 1. System Status
            print("  - get_system_status:")
            status_res = await session.call_tool("get_system_status", {})
            print(f"    {status_res.content[0].text}")
            
            # 2. Inspect Node
            print("  - inspect_node_details (Mnemosyne):")
            node_res = await session.call_tool("inspect_node_details", {"name": "Mnemosyne"})
            print(f"    {node_res.content[0].text}")
            
            # 3. Recent Logs
            print("  - get_recent_logs (last 5 lines):")
            logs_res = await session.call_tool("get_recent_logs", {"lines": 5})
            print(f"    ---\n{logs_res.content[0].text}\n    ---")

if __name__ == "__main__":
    import os
    try:
        asyncio.run(run())
    except Exception as e:
        print(f"❌ Error: {e}")
