import asyncio

import httpx

from net_simulator.msgs.AgentRegistryRequest import AgentRegistryRequest

MANAGER_URL = 'http://localhost:9000'


async def main():
    # generate 5 random agents with random names and urls
    agents = [
        AgentRegistryRequest(name='Travel Agent', url='http://travel-agent.com'),
        AgentRegistryRequest(name='Weather Agent', url='http://weather-agent.com'),
        AgentRegistryRequest(name='News Agent', url='http://news-agent.com'),
        AgentRegistryRequest(name='Finance Agent', url='http://finance-agent.com'),
        AgentRegistryRequest(name='Sports Agent', url='http://sports-agent.com'),
    ]

    async with httpx.AsyncClient() as client:
        for agent in agents:
            response = await client.post(
                f"{MANAGER_URL}/register",
                json=agent.model_dump()
            )
            if response.status_code == 200:
                print(f"Registered agent: {agent.name} at {agent.url}")
            else:
                print(f"Failed to register agent: {agent.name} at {agent.url}, status code: {response.status_code}")

        response = await client.get(f"{MANAGER_URL}/agents")
        if response.status_code == 200:
            print("Current registered agents:")
            print(response.json())
        else:
            print(f"Failed to retrieve agents, status code: {response.status_code}")


if __name__ == '__main__':
    asyncio.run(main())
