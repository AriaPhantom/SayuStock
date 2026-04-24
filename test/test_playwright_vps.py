import asyncio
from playwright.async_api import async_playwright

async def run():
    try:
        print("Initializing async_playwright...")
        async with async_playwright() as p:
            print("Launching chromium...")
            browser = await p.chromium.launch(headless=True)
            print("Chromium launch success!")
            await browser.close()
    except Exception as e:
        print(f"Launch failed: {e}")

if __name__ == "__main__":
    asyncio.run(run())
